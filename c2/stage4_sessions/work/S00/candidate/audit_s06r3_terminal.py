"""Audit downloaded terminal evidence only; never run models or submit jobs."""
import datetime
import hashlib
import json
from pathlib import Path
import zipfile

s00 = Path(__file__).resolve().parents[1]
evidence = s00 / 'evidence/s06r3_s07wrapper_20261105'
folder = evidence / 'S06'
sha = lambda data: hashlib.sha256(data).hexdigest()
receipt = json.loads((folder / 'bundle_resume_receipt.json').read_bytes())
bundle = folder / 'JOB_2039859_full_evidence.zip'
assert bundle.stat().st_size == receipt['bytes'] and sha(bundle.read_bytes()) == receipt['sha256']
received = folder / 'received'
received.mkdir(exist_ok=True)
with zipfile.ZipFile(bundle) as z:
    assert len(z.namelist()) == receipt['file_count'] == 47
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(received)
    assert all((received / n).read_bytes() == z.read(n) for n in z.namelist())

load = lambda name: json.loads((received / name).read_bytes())
collection = load('COLLECTION_S00_RESUME.json')
assert len(collection['files']) == 46
for name, info in collection['files'].items():
    data = (received / name).read_bytes()
    assert len(data) == info['bytes'] and sha(data) == info['sha256'], name
pre = load('pre_submit_checks.json')
for section in ('payload_files', 'wrapper_files'):
    for name, digest in pre[section].items():
        assert sha((received / name).read_bytes()) == digest, name
assert len(pre['payload_files']) == 14
original = s00 / 'execution_packages/S06_R3_PAYLOAD.zip'
assert (received / 'S06_R3_PAYLOAD.zip').read_bytes() == original.read_bytes()
assert sha(original.read_bytes()) == pre['package_sha256']
with zipfile.ZipFile(original) as z:
    assert len(z.namelist()) == 14
    assert all(z.read(n) == (received / n).read_bytes() for n in z.namelist())
for name, digest in json.loads((evidence / 'EXECUTION_FILES.json').read_bytes()).items():
    assert sha((received / name).read_bytes()) == digest, name

job = load('djob_final.json')['data']['successData'][0]
assert str(job['jobId']) == load('submission.json')['data']['jobId'] == '2039859'
assert (received / 'job_id.txt').read_text().strip() == '2039859'
assert job['state'] == 'FAILED' and job['jobExitCode'] == 1
assert job['exclusive'] is True and job['jobWallClockLimit'] == 660
assert job['retryPolicy']['maxRetryCnt'] == job['retryPolicy']['currentRetryTimes'] == 0
assert len(job['resGroups']) == 1
group = job['resGroups'][0]
assert group['resReq']['cpu'] == 38
assert group['resReq']['mem'] == group['resLimit']['mem'] == 8192
assert len(group['nodeResUsages']) == 1
node = group['nodeResUsages'][0]
assert node['execNode'] == 'cn21341' and node['hwThreads'] == '0-37' and node['pids'] == '-'
cpu = load('job_evidence/cpu_ddr_receipt.json')
assert cpu['job_id'] == '2039859' and cpu['host'] == 'cn21341' and cpu['DDR_node'] == 0
assert cpu['allowed'] == cpu['contract']['allocated'] == list(range(38))
assert cpu['contract']['selected'] == list(range(36))
assert cpu['contract']['reserved'] == [36, 37]
assert all(siblings == [int(core)] for core, siblings in cpu['contract']['physical_siblings'].items())
request = load('scheduler_request.json')
ready = load('scheduler_ready.json')
authority = load('job_evidence/scheduler_handoff_receipt.json')
encode = lambda data: (json.dumps(data, sort_keys=True, indent=2) + '\n').encode('utf-8')
assert ready['job_id'] == authority['job_id'] == request['context']['job_id'] == '2039859'
assert ready['nonce'] == authority['nonce'] == request['nonce']
assert ready['request_sha256'] == sha(encode(request))
assert ready['raw_sha256'] == authority['scheduler_sha256'] == sha((received / 'scheduler_allocation.json').read_bytes())
assert request['created_at'] <= ready['generated_at'] <= authority['verified_at']
assert authority['verified_at'] - ready['generated_at'] <= 30
raw_job = load('scheduler_allocation.json')['data']['successData'][0]
assert str(raw_job['jobId']) == '2039859' and raw_job['state'] == 'RUNNING'
assert raw_job['exclusive'] is True and raw_job['jobWallClockLimit'] == 660
assert len(raw_job['resGroups']) == 1
raw_group = raw_job['resGroups'][0]
assert raw_group['resReq']['cpu'] == 38
assert raw_group['resReq']['mem'] == raw_group['resLimit']['mem'] == 8192
assert len(raw_group['nodeResUsages']) == 1
assert raw_group['nodeResUsages'][0]['execNode'] == authority['host'] == request['context']['host'] == 'cn21341'
assert raw_group['nodeResUsages'][0]['hwThreads'] == '0-37'
assert authority['allowed'] == request['context']['allowed'] == cpu['allowed']
assert load('scheduler_query_receipt.json')['exit_code'] == 0
summary = load('job_evidence/SUMMARY.json')
assert summary['status'] == 'FAIL_STOP_NO_RETRY' and summary['steps'] == []
assert summary['error'] == "AssertionError('required executable: /usr/bin/g++')"
assert not (received / 'job_evidence/dependency_identity.json').exists()
assert not list((received / 'payload').glob('evidence/c2_*'))
assert not any(p.name.endswith('_receipt.json') for p in (received / 'job_evidence').iterdir()
               if p.name not in ('scheduler_handoff_receipt.json', 'cpu_ddr_receipt.json'))
start, end = [datetime.datetime.fromisoformat(job[k].replace('Z', '+00:00')) for k in ('startTime', 'endTime')]
elapsed = (end - start).total_seconds()
assert elapsed == 2
for name, info in json.loads((evidence / 'ROUND_REQUEST.json').read_bytes())['protected_files'].items():
    data = (s00 / name).read_bytes()
    assert len(data) == info['bytes'] and sha(data) == info['sha256'], name
review = dict(status='PASS_TERMINAL_EVIDENCE_AUDIT_NOT_PROBE_PASS', job_id='2039859',
    scheduler_state=job['state'], job_exit_code=1, host=node['execNode'], job_pids=node['pids'],
    source_files_unchanged=14, wrapper_files_unchanged=len(pre['wrapper_files']),
    original_metadata_entries=46, archive_files=47, original_mtime_preserved_as_metadata=True,
    resource_authority_verified=True, selected_cpu_count=36, actual_torch_cpu36_measured=False,
    stop_reason=summary['error'], standard_library_tests_run=False,
    stages=[dict(name=n, status='NOT_RUN', reason='S00 dependency preflight stopped before tests')
            for n in summary['stages_expected']],
    thread_snapshots_run=False, model_or_probe_subprocesses_started=0,
    scheduler_terminal_pids_cleared=True, new_session_submissions=0, retries=0,
    actual_node_seconds_from_utc=elapsed, scheduler_wallclock_seconds=node['wallclockDuration'],
    cumulative_known_S00_jobs=17, cumulative_node_seconds_from_utc=764 + elapsed,
    bundle=receipt, S07_job_submitted=False, real_HBM=False, formal_training=False)
(evidence / 'TERMINAL_REVIEW.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(status=review['status'], job_id='2039859', bundle_sha256=receipt['sha256'],
                     files=47, stop_reason=summary['error'], elapsed_seconds=elapsed)))
