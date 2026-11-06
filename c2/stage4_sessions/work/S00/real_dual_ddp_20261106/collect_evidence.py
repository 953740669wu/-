"""Collect terminal raw evidence, including corrupt reports; leave weights remote."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from prepare import check_root, verify_prepared, sha, save


def remote_weight(path):
    # Includes interrupted .checkpoint.pt.tmp files. Raw bytes stay remote;
    # their size/SHA and residue path are still indexed.
    return bool(set(path.suffixes) & {'.pt', '.pth', '.npz'})


def collect(root):
    check_root(root)
    job = (root/'job_id.txt').read_text().strip()
    bundle = root/('JOB_'+job+'_full_evidence.zip')
    if bundle.exists() or (root/'COLLECTION_S00.json').exists(): raise FileExistsError('already collected')
    command = ['djob', '-J', '-l', job]
    query = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    (root/'djob_final.json').write_bytes(query.stdout)
    (root/'djob_final.stderr').write_bytes(query.stderr)
    if query.returncode: raise RuntimeError('terminal scheduler query failed; originals saved')
    rows = json.loads(query.stdout)['data']['successData']
    if len(rows) != 1 or str(rows[0]['jobId']) != job or rows[0]['state'] not in ('SUCCEEDED','FAILED','CANCELLED'):
        raise ValueError('exact terminal job required; monitor existing job')
    row = rows[0]
    try:
        verify_prepared(root)
        source_status = 'UNCHANGED'
    except Exception as exc:
        source_status = repr(exc)
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.name not in (bundle.name, 'bundle_receipt.json'))
    metadata = {}
    remote_only = []
    archived = []
    # Snapshot each small file once, hash those exact bytes, then write those
    # bytes to ZIP. A partial/empty report is preserved, never repaired here.
    with zipfile.ZipFile(bundle, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in files:
            name = path.relative_to(root).as_posix()
            omit = remote_weight(path)
            try:
                before = path.stat()
                if omit:
                    digest = sha(path)
                    remote_only.append(name)
                else:
                    data = path.read_bytes()
                    import hashlib
                    digest = hashlib.sha256(data).hexdigest()
                after = path.stat()
                metadata[name] = dict(path=str(path), bytes=after.st_size, mtime_ns=after.st_mtime_ns,
                    sha256=digest, archive_payload=not omit,
                    changed_during_read=(before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns))
                if not omit:
                    z.writestr(name, data)
                    archived.append(name)
            except OSError as exc:
                metadata[name] = dict(path=str(path), archive_payload=False, error=repr(exc))
        missing = [name for name in ('job.log','scheduler_allocation.json','job_evidence/cleanup.json',
                   'job_evidence/SUMMARY.json','training_output/summary.json','training_output/rank0.json',
                   'training_output/rank1.json') if not (root/name).is_file()]
        index = dict(job_id=job, state=row['state'], job_exit_code=row.get('jobExitCode'), query_command=command,
            scheduler_pids_cleared=all(n['pids']=='-' for g in row['resGroups'] for n in g['nodeResUsages']),
            source_status=source_status, files=metadata, remote_only=remote_only, missing=missing,
            start_time=row.get('startTime'), end_time=row.get('endTime'), engineering_only=True,
            formal_split_status='UNKNOWN', subject_mapping_status='UNKNOWN', retries=0,
            note='Raw partial/missing/in-flight evidence is not proof of no exposure; no reconstructed reports.')
        save(root/'COLLECTION_S00.json', index)
        z.write(root/'COLLECTION_S00.json', 'COLLECTION_S00.json')
        archived.append('COLLECTION_S00.json')
    receipt = dict(bundle=str(bundle), bytes=bundle.stat().st_size, sha256=sha(bundle),
                   archived_files=len(archived), remote_only=remote_only)
    save(root/'bundle_receipt.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__': collect(Path(sys.argv[1]).resolve())
