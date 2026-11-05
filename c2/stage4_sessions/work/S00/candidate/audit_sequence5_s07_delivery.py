"""Read-only validation of archived five-step and failed communication evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

s00 = Path(__file__).resolve().parents[1]
request = json.loads((s00 / 'tmp/CURRENT_SEQUENCE_ROUND.json').read_bytes())
root = Path(request['local_evidence'])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())
outer = root / 'ROUND_RESULTS.zip'
outer_receipt = load(root / 'ROUND_RESULTS_receipt.json')
assert outer.stat().st_size == outer_receipt['bytes'] and sha(outer) == outer_receipt['sha256']
review = dict(status='PASS_ARCHIVED_EVIDENCE_AUDIT', task_results={}, retries=0,
              five_step_memory_run=False, S06_run=False, formal_training=False, real_HBM=False)
jobs = {}
for task, job_id, expected_state, expected_code, count, cpu, wall in [
        ('S02', '2040203', 'SUCCEEDED', 0, 66, 38, 900),
        ('S07', '2040233', 'FAILED', 1, 101, 76, 300)]:
    folder = root / 'downloaded' / task
    received = folder / 'received'
    receipt = load(folder / 'bundle_receipt.json')
    bundle = folder / Path(receipt['bundle']).name
    assert sha(bundle) == receipt['sha256'] and bundle.stat().st_size == receipt['bytes']
    with zipfile.ZipFile(bundle) as z:
        assert len(z.namelist()) == count
        assert all(z.read(n) == (received / n).read_bytes() for n in z.namelist())
    collection = load(received / 'COLLECTION_S00.json')
    assert len(collection['files']) == count - 1 and collection['changed_files'] == []
    for name, info in collection['files'].items():
        p = received / name
        assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256'], name
        assert isinstance(info['mtime_ns'], int) and info['mtime_ns'] > 0
    pre = load(received / 'pre_submit_checks.json')
    for name, digest in pre['payload_files'].items(): assert sha(received / name) == digest
    for name, digest in pre.get('wrapper_files', {}).items(): assert sha(received / name) == digest
    for name, info in load(received / 'execution_layer_identity.json').items():
        assert sha(received / name) == info['sha256']
    job = load(received / 'djob_final_collection.json')['data']['successData'][0]
    assert str(job['jobId']) == job_id and job['state'] == expected_state and job['jobExitCode'] == expected_code
    assert job['retryPolicy']['maxRetryCnt'] == job['retryPolicy']['currentRetryTimes'] == 0
    assert job['jobWallClockLimit'] == wall and len(job['resGroups']) == 1
    group = job['resGroups'][0]
    assert group['resReq']['cpu'] == cpu and group['resReq']['mem'] == group['resLimit']['mem'] == 24576
    assert len(group['nodeResUsages']) == 1
    node = group['nodeResUsages'][0]
    assert node['pids'] == '-' and node['execNode'] == 'cn21339'
    package = next(p for p in request['packages'] if p['task'] == task)
    local_package = Path(package['path'])
    assert sha(local_package) == package['sha256'] == sha(received / local_package.name)
    jobs[task] = job
    review['task_results'][task] = dict(job_id=job_id, state=expected_state, exit_code=expected_code,
        host=node['execNode'], scheduler_pids=node['pids'], source_unchanged=True,
        original_mtime_preserved_as_metadata=True, archive_files=count, metadata_entries=count-1,
        bundle=receipt, wall_seconds_from_utc=collection['actual_node_seconds_from_utc'],
        scheduler_wallclock_seconds=collection['scheduler_wallclock_seconds'])

r02 = root / 'downloaded/S02/received'
payload = r02 / 'payload'
result_path = payload / 'evidence/sequence5_2040203_strict/checker/result.json'
result = load(result_path)
assert result['status'] == 'PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY' and result['completed_steps'] == 5
assert result['comparison_failures'] == 0
assert [len(s['metrics']) for s in result['steps']] == [1063] * 5
assert all(m['passed'] is True for step in result['steps'] for m in step['metrics'])
assert result['cpu36']['job_id'] == '2040203' and result['cpu36']['host'] == 'cn21339'
assert result['cpu36']['receipt']['allocated'] == list(range(38))
assert result['cpu36']['receipt']['selected'] == list(range(36))
assert result['cpu36']['receipt']['reserved'] == [36, 37]
assert len(result['cpu36']['checkpoints']) == 24 and result['cpu36']['errors'] == []
assert result['runtime']['torch_threads'] == 36 and result['runtime']['backend'] == 'kml'
assert result['runtime']['torch'] == '2.7.1+cpu' and result['runtime']['numpy'] == '1.26.4'
actual_libraries = {x['path']: x['sha256'] for x in result['runtime']['libraries']}
expected_libraries = load(s00 / 'evidence/s06r3_s07wrapper_20261105/S06/received/payload/baseline/environment_expected.json')['library_sha256']
for path, digest in expected_libraries.items():
    if path in actual_libraries: assert actual_libraries[path] == digest
assert all(any(path.endswith(name) and digest == expected_libraries[path] for path, digest in actual_libraries.items())
           for name in ('libkml_sgemm_shim.so', 'libomp.so', 'libkblas.so.1.26.0.RC1'))
assert all(s['kml_calls'] == dict(reference=149, candidate=197) for s in result['steps'])
case_before = load(r02 / 'pre_submit_checks.json')
case_after = load(r02 / 'case_identity_after.json')
assert case_before['case_sha256'] == case_after['sha256'] == result['case_file_sha256']
assert case_before['case_bytes'] == case_after['bytes'] == 271979513
assert case_before['case_mtime_ns'] == case_after['mtime_ns']
assert load(r02 / 'sequence_gate_receipt.json')['exit_code'] == 0
# Re-evaluate the original standard-library gate against the archived sources; no Torch runs.
command = [sys.executable, '-B', str(payload / 'sequence_gate.py'), str(result_path)]
p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
(root / 'S02_sequence_gate_local.stdout').write_bytes(p.stdout)
(root / 'S02_sequence_gate_local.stderr').write_bytes(p.stderr)
assert p.returncode == 0, p.stderr.decode(errors='replace')
cpp = load(r02 / 'cpp_readonly/identity.json')
assert cpp['job_id'] == '2040203' and not cpp['compiled'] and not cpp['installed']
assert cpp['identities'] == [] and all(cpp['lookup'][n] is None for n in ('g++', 'c++', 'clang++'))
assert not list((payload / 'evidence').glob('*_memory'))
review['task_results']['S02'].update(metrics_passed=5315, metrics_per_step=[1063]*5,
    cpu36_ordered_checkpoints=24, KML_each_step=dict(reference=149, candidate=197),
    optimizer_steps=[1, 2, 3, 4, 5], remote_original_gate_exit=0, local_original_gate_exit=p.returncode,
    strict_checker_RSS_is_not_training_memory=True, compiler_readonly=cpp)

r07 = root / 'downloaded/S07/received'
summary = load(r07 / 'job_evidence/SUMMARY.json')
assert summary['status'] == 'FAIL_STOP_NO_RETRY'
assert summary['standard_library_tests'] == dict(passed=22, skipped=0, linux_group_cleanup='PASSED')
assert [s['label'] for s in summary['steps']] == ['job_identity_tests', 'probe_tests', 'environment']
assert all(s['exit_code'] == 0 and s['remaining_live'] == [] for s in summary['steps'])
assert load(r07 / 'login_publish_receipt.json')['exit_code'] == 0
authority = load(r07 / 'job_evidence/scheduler_handoff_receipt.json')
ready, req = load(r07 / 'scheduler_ready.json'), load(r07 / 'scheduler_request.json')
encode = lambda data: (json.dumps(data, sort_keys=True, indent=2) + '\n').encode('utf-8')
assert ready['job_id'] == authority['job_id'] == req['context']['job_id'] == '2040233'
assert ready['nonce'] == authority['nonce'] == req['nonce']
assert ready['request_sha256'] == hashlib.sha256(encode(req)).hexdigest()
assert ready['raw_sha256'] == authority['scheduler_sha256'] == sha(r07 / 'scheduler_allocation.json')
assert req['created_at'] <= ready['generated_at'] <= authority['verified_at']
assert authority['verified_at'] - ready['generated_at'] <= 30
assert jobs['S07']['exclusive'] is True
raw_job = load(r07 / 'scheduler_allocation.json')['data']['successData'][0]
assert str(raw_job['jobId']) == '2040233' and raw_job['state'] == 'RUNNING' and raw_job['exclusive'] is True
assert raw_job['jobWallClockLimit'] == 300 and len(raw_job['resGroups']) == 1
raw_group = raw_job['resGroups'][0]
assert raw_group['resReq']['cpu'] == 76 and raw_group['resReq']['mem'] == raw_group['resLimit']['mem'] == 24576
assert len(raw_group['nodeResUsages']) == 1 and raw_group['nodeResUsages'][0]['execNode'] == 'cn21339'
assert raw_group['nodeResUsages'][0]['hwThreads'] == '0-75'
assert authority['allowed'] == list(range(76))
allocation = load(r07 / 'job_evidence/verified_allocation.json')
assert allocation['job_id'] == '2040233' and allocation['inherited_allowed'] == list(range(76))
assert [r['node'] for r in allocation['ranks']] == [0, 1]
assert [r['selected'] for r in allocation['ranks']] == [list(range(36)), list(range(38, 74))]
assert [r['reserved'] for r in allocation['ranks']] == [[36, 37], [74, 75]]
environment = load(r07 / 'payload/environment_current.json')
assert environment['distributed'] and environment['gloo'] and environment['torch_version'] == '2.7.1+cpu'
assert not environment['environment']['LD_PRELOAD']
checks_folder = r07 / 'payload/checks_current_job'
checks = load(checks_folder / 'checks.json')
assert checks == dict(status='FAIL', cases=[], error='normal communication failed')
normal = load(checks_folder / 'normal/summary.json')
state = normal['supervisor']
assert normal['status'] == 'FAIL' and state['reason'] == 'child_failed'
assert state['exit_codes'] == [-15, 1] and state['all_reaped'] is True and len(state['pids']) == 2
ranks = [load(checks_folder / ('normal/rank' + str(rank) + '.json')) for rank in (0, 1)]
assert ranks[0]['stage'] == 'before_framework' and ranks[1]['stage'] == 'init_process_group'
assert ranks[1]['torch_intraop'] == 36 and ranks[1]['error'] == 'RuntimeError: Wait timeout'
receipt = load(r07 / 'job_evidence/run_checks_receipt.json')
assert receipt['exit_code'] == 1 and receipt['remaining_live'] == [] and not receipt.get('timed_out')
assert all(not (checks_folder / n).exists() for n in ('crash', 'collective-timeout', 'watchdog'))
review['task_results']['S07'].update(standard_library_passed=22, standard_library_skipped=0,
    scheduler_handoff='PASS_SINGLE_ACTUAL_JOB', actual_torch36_ranks=[1], rank0_torch36_measured=False,
    normal_case='FAIL_AT_PROCESS_GROUP_INITIALIZATION', rank1_error=ranks[1]['error'],
    rank0_last_recorded_stage=ranks[0]['stage'], normal_exit_codes=state['exit_codes'],
    direct_workers_reaped=True, outer_remaining_live=[], broadcast_and_all_reduce_reached=False,
    not_run=['crash', 'collective-timeout', 'watchdog'], communication_accepted=False)
assert jobs['S02']['endTime'] <= jobs['S07']['startTime']
review.update(sequential_no_overlap=True, actual_node_seconds=132,
              cumulative_known_S00_jobs=19, cumulative_node_seconds_from_utc=898,
              active_S00_jobs=[], SSH_and_SCP_closed=True)
for path, info in load(root / 'PROTECTED_BEFORE.json').items():
    p = Path(path); assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256']
(root / 'REVIEW.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(status=review['status'], S02='5315_PASS', S07='NORMAL_INIT_FAIL_NO_RETRY',
                     node_seconds=132, active_jobs=[])))
