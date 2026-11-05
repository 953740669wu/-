"""Login-side terminal collection: retain every raw file even for incomplete traces."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from prepare import BASE, PREFIX, sha
from trace_inventory import inspect


def collect(root):
    if root.parent != BASE or not root.name.startswith(PREFIX): raise ValueError('new S00 R4 directory required')
    job_id = (root / 'job_id.txt').read_text().strip()
    bundle = root / ('JOB_' + job_id + '_full_evidence.zip')
    if bundle.exists() or (root / 'COLLECTION_S00.json').exists(): raise FileExistsError('evidence already collected')
    command = ['djob', '-J', '-l', job_id]
    query = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if query.returncode: raise RuntimeError('terminal scheduler query failed')
    job = json.loads(query.stdout)['data']['successData'][0]
    if str(job['jobId']) != job_id or job['state'] not in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
        raise ValueError('exact current job must be terminal')
    if any(n['pids'] != '-' for g in job['resGroups'] for n in g['nodeResUsages']):
        raise ValueError('job PID fields are not cleared')
    (root / 'djob_final.json').write_bytes(query.stdout)
    (root / 'djob_final.stderr').write_bytes(query.stderr)
    inventory = inspect(root)
    (root / 'DIAGNOSTIC_INVENTORY.json').write_text(json.dumps(inventory, indent=2) + '\n')
    pre = json.loads((root / 'pre_submit_checks.json').read_text())
    changed = [name for name, digest in dict(pre['payload_files'], **pre['wrapper_files']).items()
               if not (root / name).is_file() or sha(root / name) != digest]
    # Do not reject/discard failure evidence when candidate or log integrity is incomplete.
    paths = sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'bundle_receipt.json')
    metadata = {}
    for p in paths:
        before = p.stat(); digest = sha(p); after = p.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError('file changed during terminal collection: ' + str(p))
        metadata[p.relative_to(root).as_posix()] = dict(bytes=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest)
    start, end = [datetime.datetime.fromisoformat(job[k].replace('Z', '+00:00')) for k in ('startTime', 'endTime')]
    index = root / 'COLLECTION_S00.json'
    index.write_text(json.dumps(dict(job_id=job_id, state=job['state'], job_exit_code=job.get('jobExitCode'),
        query_command=command, files=metadata, changed_source_files=changed, diagnostics=inventory,
        node_seconds=(end-start).total_seconds(), communication_verdict_not_reinterpreted=True,
        retries=0, real_HBM=False, formal_training=False), indent=2) + '\n')
    paths.append(index)
    with zipfile.ZipFile(bundle, 'x', zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p, p.relative_to(root).as_posix())
    receipt = dict(bundle=str(bundle), bytes=bundle.stat().st_size, sha256=sha(bundle), file_count=len(paths))
    (root / 'bundle_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__': collect(Path(sys.argv[1]).resolve())
