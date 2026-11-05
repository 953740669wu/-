"""Collect complete S02-R6 or S03-R2-C terminal evidence, excluding fixed .pt inputs."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.name.startswith(('S02_CKPT64_R6_', 'S03_R2_C_'))
job_id = (root / 'job_id.txt').read_text().strip()
query = subprocess.run(['djob', '-J', '-l', job_id], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, check=True)
final = json.loads(query.stdout)
job = final['data']['successData'][0]
assert job['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED')
assert all(x.get('pids') == '-' for group in job['resGroups'] for x in group['nodeResUsages'])
(root / 'djob_final.json').write_text(json.dumps(final, indent=2) + '\n')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pre = json.loads((root / 'pre_submit_checks.json').read_text())
changed = [name for name, digest in pre['payload_files'].items()
           if sha(root / 'payload' / name) != digest]
for name, digest in pre.get('wrapper_files', {}).items():
    if sha(root / name) != digest:
        changed.append(name)
if root.name.startswith('S02_'):
    case = Path(pre['case_path'])
    digest = hashlib.sha256()
    with case.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == pre['case_sha256'] and case.stat().st_size == pre['case_bytes']
    (root / 'case_identity_after.json').write_text(json.dumps(dict(sha256=digest.hexdigest(),
        bytes=case.stat().st_size, mtime_ns=case.stat().st_mtime_ns, case_not_downloaded=True), indent=2) + '\n')
self_copy = root / 'collect_r6_r2_evidence.py'
if Path(__file__).resolve() != self_copy:
    shutil.copyfile(__file__, self_copy)
files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix not in ('.zip', '.pt')
               and p.name not in ('COLLECTION_S00.json', 'bundle_receipt.json'))
metadata = {}
for path in files:
    before = path.stat()
    digest = sha(path)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    metadata[str(path.relative_to(root))] = dict(sha256=digest, bytes=after.st_size, mtime_ns=after.st_mtime_ns)
collection = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), job_id=job_id,
    scheduler_state=job['state'], job_exit_code=job.get('jobExitCode'), changed_payload_files=changed,
    files=metadata, fixed_case_pt_not_downloaded=True, real_HBM=False, training_memory_test=False)
(root / 'COLLECTION_S00.json').write_text(json.dumps(collection, indent=2) + '\n')
files.append(root / 'COLLECTION_S00.json')
bundle = root / ('JOB_' + job_id + '_full_evidence.zip')
assert not bundle.exists()
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, str(path.relative_to(root)))
receipt = dict(bundle=str(bundle), sha256=sha(bundle), bytes=bundle.stat().st_size,
               file_count=len(files), state=job['state'], exit_code=job.get('jobExitCode'))
(root / 'bundle_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
for i in range(0, 64, 16):
    print('HASH_PART_' + str(i // 16 + 1), receipt['sha256'][i:i + 16])
