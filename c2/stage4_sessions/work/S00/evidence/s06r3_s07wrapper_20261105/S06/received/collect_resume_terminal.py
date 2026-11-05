"""S00 terminal evidence collection only; no compute, submissions or retries."""
import datetime, hashlib, json
from pathlib import Path
import zipfile
root = Path(__file__).resolve().parent
assert root == Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S06_R3_FIRST_20261105T084500Z')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
job = json.loads((root / 'djob_final.json').read_bytes())['data']['successData'][0]
assert str(job['jobId']) == (root / 'job_id.txt').read_text().strip() == '2039859'
assert job['state'] == 'FAILED' and job['jobExitCode'] == 1
assert all(n['pids'] == '-' for g in job['resGroups'] for n in g['nodeResUsages'])
pre = json.loads((root / 'pre_submit_checks.json').read_bytes())
for section in ('payload_files', 'wrapper_files'):
    assert all(sha(root / n) == h for n, h in pre[section].items()), section
assert sha(root / 'S06_R3_PAYLOAD.zip') == pre['package_sha256']
summary = json.loads((root / 'job_evidence/SUMMARY.json').read_bytes())
assert summary['status'] == 'FAIL_STOP_NO_RETRY' and summary['steps'] == []
assert summary['error'] == "AssertionError('required executable: /usr/bin/g++')"
assert not list((root / 'payload').glob('evidence/c2_*'))
paths = sorted(p for p in root.rglob('*') if p.is_file() and p.name not in ('COLLECTION_S00_RESUME.json', 'bundle_resume_receipt.json', 'JOB_2039859_full_evidence.zip'))
files = {}
for p in paths:
    a = p.stat(); digest = sha(p); b = p.stat()
    assert (a.st_size,a.st_mtime_ns) == (b.st_size,b.st_mtime_ns)
    files[p.relative_to(root).as_posix()] = dict(bytes=b.st_size, mtime_ns=b.st_mtime_ns, sha256=digest)
meta = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id='2039859',state=job['state'],job_exit_code=job['jobExitCode'],files=files,source_unchanged=True,retries=0,new_job_submitted_on_resume=False,standard_library_tests_run=False,actual_torch_or_compile_run=False,real_HBM=False,formal_training=False,start_utc=job['startTime'],end_utc=job['endTime'],scheduler_wallclock_seconds=job['resGroups'][0]['nodeResUsages'][0]['wallclockDuration'],not_run=summary['stages_expected'],not_run_reason=summary['error'])
m = root / 'COLLECTION_S00_RESUME.json'
assert not m.exists()
m.write_text(json.dumps(meta,indent=2)+'\n')
paths.append(m)
bundle = root / 'JOB_2039859_full_evidence.zip'
assert not bundle.exists()
with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as z:
    for p in paths: z.write(p,p.relative_to(root).as_posix())
receipt = dict(bundle=str(bundle),bytes=bundle.stat().st_size,sha256=sha(bundle),file_count=len(paths),state=job['state'],job_exit_code=job['jobExitCode'])
(root / 'bundle_resume_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
