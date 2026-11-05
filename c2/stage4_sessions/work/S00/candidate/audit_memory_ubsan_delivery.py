"""Read-only data checks on returned jobs; no models, compiler, or Linux probes."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import runpy
import zipfile

work = Path(__file__).resolve().parent.parent
root = work / 'evidence/r6_memory_ubsan_20261105'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
policy = runpy.run_path(str(work / 'candidate/s03_cpu36_contract_frozen.py'))
request = load(root / 'ROUND_REQUEST.json')
for name, identity in request['protected_files'].items():
    p = root / (name[:-3] + '_before.md') if name in ('SESSION_STATUS.md', 'ROUND_DELTA.md') else work / name
    assert sha(p) == identity['sha256'] and p.stat().st_size == identity['bytes'], name

jobs = {}
for kind, job_id, digest, count, archive in [
    ('S02', '2037434', 'd2dd91be74c2bba01f529f926d07ab38b184d88b6389bcbae0a1283fd1f51881', 90, 'S02_CKPT64_R6_CODE.zip'),
    ('S03', '2037491', '08410627941e6249cb10fed875c9204891f6ad9cdc93364880051ae3b9a22754', 49, 'S03_ROUND2_C_VALIDATION.zip'),
]:
    received = root / kind / 'received'
    bundle = root / ('JOB_' + job_id + '_full_evidence.zip')
    assert sha(bundle) == digest
    with zipfile.ZipFile(bundle) as z:
        assert len(z.namelist()) == count and not any(n.endswith('.pt') for n in z.namelist())
    collection = load(received / 'COLLECTION_S00.json')
    assert collection['job_id'] == job_id and collection['changed_payload_files'] == []
    assert collection['retries'] == 0 and not collection['real_HBM'] and not collection['real_S06_S07_probes']
    for name, row in collection['files'].items():
        p = received / name
        assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], name
        assert type(row['mtime_ns']) is int and row['mtime_ns'] > 0
    pre = load(received / 'pre_submit_checks.json')
    assert pre['status'] == 'PASS_REMOTE_SHA_LF_LINUX_SYNTAX'
    assert sha(work / 'execution_packages' / archive) == pre['package_sha256']
    with zipfile.ZipFile(work / 'execution_packages' / archive) as z:
        expected = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/')}
    assert pre['payload_files'] == expected
    assert all(sha(received / 'payload' / n) == h for n, h in expected.items())
    assert all(sha(received / n) == h for n, h in pre['wrapper_files'].items())
    job = load(received / 'djob_final.json')['data']['successData'][0]
    assert str(job['jobId']) == job_id and job['jobWallClockLimit'] == (900 if kind == 'S02' else 300)
    assert job['retryPolicy']['currentRetryTimes'] == job['retryPolicy']['maxRetryCnt'] == 0
    assert len(job['resGroups']) == 1
    group = job['resGroups'][0]
    assert group['resReq']['cpu'] == 38 and group['resReq']['mem'] == group['resLimit']['mem'] == 24576
    usage = group['nodeResUsages'][0]
    assert usage['pids'] == '-' and usage['hwThreads'] == '0-37'
    duration = (datetime.fromisoformat(job['endTime'].replace('Z', '+00:00')) -
                datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))).total_seconds()
    jobs[kind] = dict(job_id=job_id, state=job['state'], exit_code=job['jobExitCode'],
        start_utc=job['startTime'], end_utc=job['endTime'], elapsed_wall_seconds=duration,
        host=usage['execNode'], allocated_cores=38, selected_cores=36, memory_MB=24576,
        bundle_sha256=digest, bundle_bytes=bundle.stat().st_size, file_count=count)

mem = root / 'S02/received'
base = mem / 'payload/evidence/memory_2037434_ckpt64'
assert jobs['S02']['state'] == 'SUCCEEDED' and jobs['S02']['exit_code'] == 0
gate = load(mem / 'memory_gate_before_submit.json')
strict = load(mem / 'strict_reference_result.json')
assert gate['status'] == 'STRICT_CANDIDATE_PASS_REFERENCE_ONLY'
assert gate['sha256'] == sha(mem / 'strict_reference_result.json')
assert strict['status'] == 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
assert len(strict['metrics']) == 1063 and strict['failures'] == [] and all(m['passed'] for m in strict['metrics'])
assert load(base / 'strict_gate.json') == gate
measurements = []
for ckpt in (0, 1):
    directory = base / ('ckpt' + str(ckpt))
    d = load(directory / 'result.json')
    assert (directory / 'exit_code.txt').read_text().strip() == '0'
    assert d['status'] == 'DDR_ONE_STEP_DIAGNOSTIC_ONLY_NOT_BENEFIT_ACCEPTANCE'
    assert d['config'] == dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
        checkpoint=bool(ckpt), history='fresh', precision='fp32', threads=36, loss='original_mean',
        hbm=False, training_steps=1, warmup_steps=0)
    assert d['case_file_sha256'] == strict['case_file_sha256'] and d['case_identity'] == strict['case_identity']
    assert d['case_file_bytes'] == 271979513 and d['checkpoint_wrapped_layers'] == 12 * ckpt
    assert d['optimizer_steps'] == 1 and d['initial_weights_released_before_training']
    assert not d['comparison_snapshots_retained']
    assert d['parameter_counts'] == dict(enc=37995777, dec=29416449)
    assert all(sha(mem / 'payload' / n) == h for n, h in d['source_sha256'].items())
    state = d['cpu36']
    assert state['job_id'] == '2037434' and state['host'] == jobs['S02']['host'] and state['errors'] == []
    assert [x['name'] for x in state['checkpoints']] == ['before_framework', 'after_framework',
        'after_backend', 'initialized', 'before_training', 'after_training', 'publish']
    policy['validate_receipt'](state['receipt'])
    assert state['receipt']['allocated'] == list(range(38))
    assert state['receipt']['selected'] == list(range(36)) and state['receipt']['reserved'] == [36, 37]
    for cp in state['checkpoints']:
        assert cp['pid'] == state['pid']
        policy['validate_checkpoint'](cp, state['receipt'])
    runtime = d['runtime']
    assert runtime['backend'] == 'kml' and runtime['torch_threads'] == 36
    assert runtime['kml_gemm_calls'] == (149 if ckpt == 0 else 197)
    assert {x['sha256'] for x in runtime['libraries']} == {x['sha256'] for x in runtime['libraries_after']}
    for label in ('initialization', 'training_start', 'training'):
        row = d[label]
        assert row['hugetlb_bytes'] == 0 and row['peak_rss_bytes'] >= row['rss_bytes'] > 0
        assert row['rss_MiB'] == row['rss_bytes'] / 2**20
        assert row['peak_rss_MiB'] == row['peak_rss_bytes'] / 2**20
    assert d['peak_reset']['available'] is True
    assert d['training_start']['peak_rss_bytes'] == d['training_start']['rss_bytes'] < d['initialization']['peak_rss_bytes']
    assert 0 < d['training']['elapsed_seconds'] < 360
    measurements.append(dict(checkpoint=ckpt, pid=state['pid'], initialization=d['initialization'],
        peak_reset=d['peak_reset'], training_start=d['training_start'], training=d['training'],
        loss=d['loss'], optimizer_steps=1, cpu_checkpoints=7, kml_calls=runtime['kml_gemm_calls']))
assert measurements[0]['pid'] != measurements[1]['pid']
assert measurements[0]['loss'] == measurements[1]['loss']
before = load(mem / 'pre_submit_checks.json')
after = load(mem / 'case_identity_after.json')
assert after['sha256'] == before['case_sha256'] and after['bytes'] == before['case_bytes']
assert after['mtime_ns'] == before['case_mtime_ns']

croot = root / 'S03/received'
out = croot / 'payload/linux_evidence'
summary = load(out / 'SUMMARY.json')
assert jobs['S03']['state'] == 'FAILED' and jobs['S03']['exit_code'] == 1
assert summary['status'] == 'BLOCKED_UBSAN_OR_C_FAILURE'
assert summary['blocker'] == 'NO_EXISTING_UBSAN_RUNTIME_IN_FINITE_ALLOWED_LOCATIONS'
assert summary['finished_affinity'] == list(range(36))
receipt = load(out / 'cpu_receipt.json')
assert receipt['job_id'] == '2037491' and receipt['clean_environment']
policy['validate_receipt'](receipt['contract'])
assert receipt['actual_affinity'] == receipt['contract']['selected'] == list(range(36))
steps = load(out / 'steps.json')
assert all(s['exit_code'] == 0 and not s.get('timed_out') and s['affinity'] == list(range(36)) for s in steps)
assert not any(s['label'].startswith(('control_', 'build_')) for s in steps)
assert not (out / 'previous_cases.json').exists() and not (out / 'candidate_cases.json').exists()
assert not any(n.startswith(('payload/build/', 'ubsan_link/')) for n in load(croot / 'COLLECTION_S00.json')['files'])
assert 'AArch64' in (out / 'compiler_elf.txt').read_text()
assert load(out / 'runtime_locations.json')['checked'] == []
jobs['S02'].update(status='DDR_ONE_STEP_DIAGNOSTIC_ONLY_NOT_BENEFIT_ACCEPTANCE', measurements=measurements)
jobs['S03'].update(status=summary['status'], blocker=summary['blocker'],
    ubsan_controls='NOT_RUN_NO_RUNTIME', previous_50='NOT_RUN', candidate_50='NOT_RUN', independent_library='NOT_RUN',
    compiler_sha256='NOT_CAPTURED_EARLY_NO_RUNTIME_BLOCK', runtime_sha256='NOT_AVAILABLE_NO_RUNTIME')
assert jobs['S02']['end_utc'] < jobs['S03']['start_utc']
review = dict(status='COMPLETE_MEMORY_DIAGNOSTIC_UBSAN_RECOVERY_BLOCKED', jobs=jobs,
    new_jobs=2, retries=0, real_HBM=False, S06_S07_probes=False, old_protected_evidence_unchanged=True,
    node_seconds_this_round=sum(j['elapsed_wall_seconds'] for j in jobs.values()),
    scientific_memory_benefit_acceptance=False, production_integration=False,
    presubmit_helper_fix='Streaming hash only; preserved original mismatch; no job retry or candidate edit',
    clean_terminal_pids=True)
(root / 'review.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in review.items() if k != 'jobs'}, indent=2))
for key, job in jobs.items():
    print(key, job['job_id'], job['state'], job['exit_code'], job['status'])
