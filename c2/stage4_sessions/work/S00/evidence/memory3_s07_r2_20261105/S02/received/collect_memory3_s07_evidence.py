"""Collect the memory-three-pair or two-domain S07 terminal job, without reruns."""
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
assert root.name.startswith(('S02_R6_MEMORY3_', 'S07_R2_TWODOMAIN_'))
job_id = (root / 'job_id.txt').read_text().strip()
query = subprocess.run(['djob', '-J', '-l', job_id], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, check=True)
final = json.loads(query.stdout)
job = final['data']['successData'][0]
assert job['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED')
assert all(x.get('pids') == '-' for group in job['resGroups'] for x in group['nodeResUsages'])
(root / 'djob_final.json').write_text(json.dumps(final, indent=2) + '\n')
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
pre = json.loads((root / 'pre_submit_checks.json').read_text())
changed = [name for name, digest in pre['payload_files'].items()
           if sha(root / name) != digest]
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
if root.name.startswith('S02_'):
    strict = Path(pre['strict_result_path'])
    assert sha(strict) == pre['strict_result_sha256']
    shutil.copyfile(strict, root / 'strict_reference_result.json')
    (root / 'strict_reference_identity.json').write_text(json.dumps(dict(path=str(strict), sha256=sha(strict), bytes=strict.stat().st_size, mtime_ns=strict.stat().st_mtime_ns), indent=2) + '\n')
self_copy = root / 'collect_memory3_s07_evidence.py'
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
    symlinks={str(p.relative_to(root)):str(p.resolve()) for p in root.rglob('*') if p.is_symlink()},
    files=metadata, fixed_case_pt_not_downloaded=True, real_HBM=False, training_memory_test=root.name.startswith('S02_'),
    memory_scope='three pairs of independent fresh B64 steps; diagnostic only',
    retries=0, real_S06_probe=False, real_S07_probe=root.name.startswith('S07_'), formal_training=False)
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
