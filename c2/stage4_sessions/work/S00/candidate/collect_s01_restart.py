"""Collect only this S00 run's complete generated logs/results after terminal state."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.name.startswith('PILOT_S01_') and root.name.endswith('_LF_RESTART')
job_id = (root / 'job_id.txt').read_text().strip()
job_query = subprocess.run(['djob', '-J', '-l', job_id], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, check=True)
final = json.loads(job_query.stdout)
job = final['data']['successData'][0]
assert job['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'), job['state']
(root / 'djob_final.json').write_text(json.dumps(final, indent=2) + '\n')
checked = json.loads((root / 'pre_submit_checks.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
changed = [name for name, digest in checked['all_payload_files_sha256'].items()
           if sha(root / 'payload' / name) != digest]
files = [p for p in root.iterdir() if p.is_file() and p.suffix != '.zip']
for folder in ('payload/evidence', 'payload/output/reports'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file())
files = sorted(set(files))
manifest = {str(p.relative_to(root)): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in files}
status = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              job_id=job_id, scheduler_state=job['state'], job_exit_code=job.get('jobExitCode'),
              start_time=job['startTime'], end_time=job['endTime'], host=job['taskExecNodes'],
              changed_payload_files=changed, complete_generated_evidence_files=manifest,
              scope='All generated job/runner/rank/preflight logs and results, not raw NPZ or shared source',
              s02='NOT_SUBMITTED', training_memory='NOT_RUN')
(root / 'collection_status.json').write_text(json.dumps(status, indent=2) + '\n')
files.append(root / 'collection_status.json')
bundle = root / ('S01_LF_RESTART_' + job_id + '_full_evidence.zip')
assert not bundle.exists()
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in files:
        z.write(p, str(p.relative_to(root)))
result = dict(bundle=str(bundle), sha256=sha(bundle), bytes=bundle.stat().st_size,
              file_count=len(files), status=status['scheduler_state'], exit_code=status['job_exit_code'],
              changed_payload_files=changed)
(root / 'bundle_receipt.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
