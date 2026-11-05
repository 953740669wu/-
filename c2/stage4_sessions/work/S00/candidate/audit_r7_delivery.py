"""Audit R7 returned evidence and summarize a copy with genuine remote mtimes."""
from pathlib import Path
import datetime
import hashlib
import importlib
import json
import math
import os
import shutil
import sys
import tempfile
import zipfile

work = Path(__file__).resolve().parents[1]
base = work / 'evidence/r7_cpu36_2034247'
received = base / 'received'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
expected_zip = 'cf5db0ce6ac812c719b5879e26c68955f26fbfa23154a6bea96f31962bcb9755'
assert sha(base / 'full_evidence.zip') == expected_zip
collection = json.loads((received / 'COLLECTION_S00.json').read_text())
with zipfile.ZipFile(base / 'full_evidence.zip') as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(collection['files']) | {'COLLECTION_S00.json'}
for name, info in collection['files'].items():
    path = received / name
    assert sha(path) == info['sha256'] and path.stat().st_size == info['bytes'], name
    assert type(info['mtime_ns']) is int
assert collection['changed_payload_files'] == []
request = json.loads((work / 'evidence/r7_cpu36_startup_request.json').read_text())
for name, digest in request['prior_evidence_sha256'].items():
    assert sha(work / name) == digest, name
for name, digest in request['expected_payload_files'].items():
    assert sha(received / 'payload' / name) == digest, name
pre = json.loads((received / 'pre_submit_checks.json').read_text())
assert len(pre['shell_checks']) == 3 and len(pre['python_syntax']) == 4
assert all(x['cr_bytes'] == 0 and x['bash_n_exit'] == 0 for x in pre['shell_checks'])
job = json.loads((received / 'djob_final.json').read_text())['data']['successData'][0]
assert job['jobId'] == '2034247' and job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0
resource = job['resGroups'][0]
assert resource['resAlloc']['cpu'] == 38 and resource['resAlloc']['mem'] == 24576
assert resource['resLimit']['mem'] == 24576 and job['jobWallClockLimit'] == 900
root = received / 'payload/output/reports/s01_cpu36_2034247'
summary = json.loads((root / 'summary.json').read_text())
manifest = json.loads((root / 'manifest.json').read_text())
assert summary['status'] == 'PASS' and summary['errors'] == []
assert manifest['rounds'] == 3 and manifest['domains'] == [0]
receipt = manifest['cpu_contracts']['0']
assert receipt['selected'] == list(range(36)) and receipt['reserved'] == [36, 37]
reference_files = list((received / 'payload/evidence').glob('CPU36_PREFLIGHT_*.json'))
assert len(reference_files) == 1
reference = json.loads(reference_files[0].read_text())
assert reference['status'] == 'PASS_IMPORT_ONLY' and reference['job_id'] == job['jobId']
assert reference['torch_intraop'] == 36 and reference['host'] == job['taskExecNodes']
rounds = []
for rid in range(1, 4):
    data = json.loads((root / f'r{rid}_d0.json').read_text())
    state = json.loads((root / f'r{rid}_d0.status.json').read_text())
    monitor = state['thread_monitor']
    assert state['exit_code'] == 0 and state['timed_out'] is False
    assert monitor['incomplete_samples'] == 0 and monitor['violations'] == []
    checkpoints = data['run']['cpu36']['checkpoints']
    assert len(checkpoints) == 6
    for point in checkpoints:
        assert point['snapshot']['complete'] and point['snapshot']['threads']
        if point['name'] != 'before_framework':
            assert point['torch_intraop'] == 36
        for thread in point['snapshot']['threads']:
            assert thread['affinity'] and set(thread['affinity']) <= set(receipt['selected'])
    count = 0
    with (root / f'sync_r{rid}/rank0.threads.jsonl').open() as stream:
        for line in stream:
            sample = json.loads(line)['snapshot']
            assert sample['complete'] and sample['threads']
            for thread in sample['threads']:
                assert thread['affinity'] and set(thread['affinity']) <= set(receipt['selected'])
            count += 1
    assert count == monitor['snapshots']
    rounds.append(dict(round=rid, child_exit_code=0, timed_out=False, monitor_samples=count,
                       checkpoints=len(checkpoints), actual_torch_intraop=36,
                       calling_affinity=data['run']['affinity'], measurements=data['16_adjacent']))
# Received originals stay untouched. Restore only an independent verification copy.
copy = Path(tempfile.mkdtemp(prefix='r7_offline_', dir=work / 'tmp')) / 'received'
shutil.copytree(received, copy)
rounding = 0
for name, info in collection['files'].items():
    path = copy / name
    os.utime(path, ns=(info['mtime_ns'], info['mtime_ns']))
    rounding = max(rounding, abs(path.stat().st_mtime_ns - info['mtime_ns']))
sys.path.insert(0, str(copy / 'payload/candidate'))
runner = importlib.import_module('runner')
offline = runner.summarize(copy / 'payload/output/reports/s01_cpu36_2034247')
assert offline['status'] == summary['status'] == 'PASS', offline
for key, metric in summary['metrics'].items():
    assert math.isclose(offline['metrics'][key]['spread'], metric['spread'], abs_tol=1e-12)
    assert offline['metrics'][key]['sums'] == metric['sums']
(base / 'offline_summary.json').write_bytes((json.dumps(offline, indent=2) + '\n').encode())
for name, info in collection['files'].items():
    assert sha(received / name) == info['sha256'], name
seconds = (datetime.datetime.fromisoformat(job['endTime'].replace('Z', '+00:00'))
           - datetime.datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))).total_seconds()
result = dict(status='PASS_R7_BOUNDED_STARTUP_EVIDENCE_REVIEW_PENDING', job_id=job['jobId'],
              host=job['taskExecNodes'], scheduler_state=job['state'], job_exit_code=0,
              start_utc=job['startTime'], end_utc=job['endTime'], node_seconds=seconds,
              node_hours=seconds / 3600, cumulative_s00_node_seconds=266 + seconds,
              selected_cpus=receipt['selected'], reserved_cpus=receipt['reserved'],
              allocated_cpus=receipt['allocated'], rounds=rounds, summary=summary,
              full_evidence_files=len(collection['files']) + 1, bundle_sha256=expected_zip,
              source_package_sha256=request['package_sha256'], preflight='PASS_IMPORT_ONLY_SAME_JOB',
              offline_summary='PASS', offline_copy=str(copy),
              offline_max_mtime_rounding_ns=rounding, received_original_bytes_unchanged=True,
              prior_evidence_unchanged=True, S02='NOT_SUBMITTED', training_memory_test='NOT_RUN',
              numerical_equivalence='NOT_TESTED', formal_performance='NOT_ACCEPTED', production_deployment='NOT_DONE')
(base / 'review.json').write_bytes((json.dumps(result, indent=2) + '\n').encode())
print(json.dumps({key: result[key] for key in ['status', 'job_id', 'host', 'node_seconds',
      'full_evidence_files', 'offline_summary', 'offline_max_mtime_rounding_ns']}))
