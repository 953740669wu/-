"""Terminal raw snapshots, including partial/empty/proc-denied files and residues."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from prepare import check_root,save,sha
from trace_inventory import inspect
from readiness_inventory import inspect as readiness
from stack_inventory import inspect as stacks
from rank_report_inventory import inspect as rank_reports

def collect(root):
    check_root(root);job=(root/'job_id.txt').read_text().strip();bundle=root/('JOB_'+job+'_full_evidence.zip')
    if bundle.exists() or (root/'COLLECTION_S00.json').exists():raise FileExistsError('already collected; preserve original')
    command=['djob','-J','-l',job];query=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    (root/'djob_final.json').write_bytes(query.stdout);(root/'djob_final.stderr').write_bytes(query.stderr)
    if query.returncode:raise RuntimeError('raw terminal query saved; cannot establish terminal')
    row=json.loads(query.stdout)['data']['successData'][0]
    if str(row['jobId'])!=job or row['state'] not in ('SUCCEEDED','FAILED','CANCELLED'):raise ValueError('exact terminal job required')
    traces=inspect(root);ready=readiness(root);stack=stacks(root);reports=rank_reports(root)
    save(root/'DIAGNOSTIC_INVENTORY.json',traces);save(root/'READINESS_INVENTORY.json',ready);save(root/'STACK_INVENTORY.json',stack)
    save(root/'RANK_REPORT_INVENTORY.json',reports)
    pre=json.loads((root/'pre_submit_checks.json').read_text(encoding='utf-8'))
    source=dict(pre['payload_files'],**json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')))
    changed=[name for name,digest in source.items() if not (root/name).is_file() or sha(root/name)!=digest]
    paths=sorted(p for p in root.rglob('*') if p.is_file() and p.name not in ('bundle_receipt.json',bundle.name))
    metadata={};snapshots={}
    for path in paths:
        before=path.stat();raw=path.read_bytes();after=path.stat();name=path.relative_to(root).as_posix();snapshots[name]=raw
        metadata[name]=dict(path=str(path),bytes=len(raw),mtime_ns=before.st_mtime_ns,sha256=hashlib.sha256(raw).hexdigest(),changed_during_read=(before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns),stat_after_bytes=after.st_size,stat_after_mtime_ns=after.st_mtime_ns)
    begin,end=[datetime.fromisoformat(row[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
    checks_path=root/'payload/checks_current_job/checks.json'
    try:communication=json.loads(checks_path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:communication=dict(status='MISSING_OR_PARTIAL',error=repr(exc))
    index=dict(job_id=job,state=row['state'],job_exit_code=row.get('jobExitCode'),query_command=command,files=metadata,changed_source_files=changed,
        scheduler_pids_cleared=all(n['pids']=='-' for g in row['resGroups'] for n in g['nodeResUsages']),diagnostics=traces,readiness=ready,stack_observation=stack,rank_reports=reports,
        original_communication_result=communication,communication_passed=communication.get('status')=='PASS_PROBE_CHECKS_ONLY',node_seconds=(end-begin).total_seconds(),communication_verdict_not_reinterpreted=True,retries=0,real_HBM=False,formal_training=False)
    save(root/'COLLECTION_S00.json',index)
    with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as z:
        for name,raw in snapshots.items():z.writestr(name,raw)
        z.write(root/'COLLECTION_S00.json','COLLECTION_S00.json')
    receipt=dict(bundle=str(bundle),bytes=bundle.stat().st_size,sha256=sha(bundle),file_count=len(snapshots)+1)
    save(root/'bundle_receipt.json',receipt);print(json.dumps(receipt));return receipt
if __name__=='__main__':collect(Path(sys.argv[1]).resolve())
