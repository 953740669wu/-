"""Return complete R6 diagnostic evidence with original nanosecond mtimes."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.name.startswith('DIAG_CPU36_R6_')
job_id = (root / 'job_id.txt').read_text().strip()
query = subprocess.run(['djob', '-J', '-l', job_id], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, check=True)
final = json.loads(query.stdout)
job = final['data']['successData'][0]
assert job['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'), job['state']
(root / 'djob_final.json').write_text(json.dumps(final, indent=2) + '\n')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pre = json.loads((root / 'pre_submit_checks.json').read_text())
changed = [name for name, digest in pre['payload_files'].items()
           if sha(root / 'payload' / name) != digest]
files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix != '.zip'
               and p.name not in ('COLLECTION_S00.json', 'bundle_receipt.json'))
collection = {}
for path in files:
    before = path.stat()
    digest = sha(path)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), path
    collection[str(path.relative_to(root))] = dict(sha256=digest, bytes=after.st_size,
                                                 mtime_ns=after.st_mtime_ns)
metadata = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                job_id=job_id, scheduler_state=job['state'], job_exit_code=job.get('jobExitCode'),
                changed_payload_files=changed, files=collection,
                scope='Complete diagnostic payload/results/logs/receipts with original remote mtime_ns',
                full_model='NOT_RUN', S02='NOT_SUBMITTED', training_memory='NOT_RUN')
(root / 'COLLECTION_S00.json').write_text(json.dumps(metadata, indent=2) + '\n')
files.append(root / 'COLLECTION_S00.json')
bundle = root / ('CPU36_R6_' + job_id + '_full_evidence.zip')
assert not bundle.exists()
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in files:
        z.write(path, str(path.relative_to(root)))
receipt = dict(bundle=str(bundle), sha256=sha(bundle), bytes=bundle.stat().st_size,
               file_count=len(files), state=job['state'], exit_code=job.get('jobExitCode'))
(root / 'bundle_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
print('SHA256_CHUNKS', [receipt['sha256'][i:i+16] for i in range(0, 64, 16)])
