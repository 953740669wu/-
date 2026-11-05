"""Collect a terminal reviewed job and its exact sources; no experimental reruns."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.name.startswith(('S02_SEQUENCE5_R7_', 'S07_R2_TWODOMAIN_R3_'))
task = 'S02' if root.name.startswith('S02') else 'S07'
job_id = (root / 'job_id.txt').read_text().strip()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


p = subprocess.run(['djob', '-J', '-l', job_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
assert p.returncode == 0
job = json.loads(p.stdout)['data']['successData'][0]
assert str(job['jobId']) == job_id and job['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED')
assert all(n['pids'] == '-' for g in job['resGroups'] for n in g['nodeResUsages'])
(root / 'djob_final_collection.json').write_bytes(p.stdout)
pre = json.loads((root / 'pre_submit_checks.json').read_text())
changed = [name for name, digest in pre['payload_files'].items() if sha(root / name) != digest]
for name, digest in pre.get('wrapper_files', {}).items():
    if sha(root / name) != digest: changed.append(name)
for name, info in json.loads((root / 'execution_layer_identity.json').read_text()).items():
    if sha(root / name) != info['sha256']: changed.append(name)
assert not changed, changed
if task == 'S02':
    case = Path(pre['case_path'])
    actual = dict(path=str(case), bytes=case.stat().st_size, sha256=sha(case), mtime_ns=case.stat().st_mtime_ns)
    assert actual['bytes'] == pre['case_bytes'] and actual['sha256'] == pre['case_sha256']
    save(root / 'case_identity_after.json', actual)
    result = root / 'payload/evidence' / ('sequence5_' + job_id + '_strict/checker/result.json')
    if result.exists():
        command = ['/usr/bin/python3', '-B', str(root / 'payload/sequence_gate.py'), str(result)]
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        (root / 'sequence_gate.stdout').write_bytes(p.stdout)
        (root / 'sequence_gate.stderr').write_bytes(p.stderr)
        save(root / 'sequence_gate_receipt.json', dict(command=command, exit_code=p.returncode, memory_submitted=False))
    else:
        save(root / 'sequence_gate_receipt.json', dict(status='NOT_RUN_MISSING_STRICT_RESULT', memory_submitted=False))
    assert not list((root / 'payload/evidence').glob('*_memory'))
start, end = [datetime.datetime.fromisoformat(job[k].replace('Z', '+00:00')) for k in ('startTime', 'endTime')]
paths = sorted(p for p in root.rglob('*') if p.is_file()
               and p.name not in ('COLLECTION_S00.json', 'bundle_receipt.json', 'JOB_' + job_id + '_full_evidence.zip'))
metadata = {}
for path in paths:
    before = path.stat(); digest = sha(path); after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    metadata[path.relative_to(root).as_posix()] = dict(bytes=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest)
collection = dict(task=task, captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), job_id=job_id,
    state=job['state'], job_exit_code=job.get('jobExitCode'), source_unchanged=True, changed_files=changed, files=metadata,
    actual_node_seconds_from_utc=(end-start).total_seconds(),
    scheduler_wallclock_seconds=[n['wallclockDuration'] for g in job['resGroups'] for n in g['nodeResUsages']],
    retries=0, five_step_memory_run=False, S06_run=False, formal_training=False, real_HBM=False)
index = root / 'COLLECTION_S00.json'
assert not index.exists()
save(index, collection); paths.append(index)
bundle = root / ('JOB_' + job_id + '_full_evidence.zip')
with zipfile.ZipFile(bundle, 'x', zipfile.ZIP_DEFLATED) as z:
    for path in paths: z.write(path, path.relative_to(root).as_posix())
receipt = dict(task=task, job_id=job_id, state=job['state'], job_exit_code=job.get('jobExitCode'),
    bundle=str(bundle), bytes=bundle.stat().st_size, sha256=sha(bundle), file_count=len(paths),
    actual_node_seconds_from_utc=(end-start).total_seconds())
save(root / 'bundle_receipt.json', receipt)
print(json.dumps(receipt))
