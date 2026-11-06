"""Terminal logs/source/data identities; checkpoint stays remote with bytes/SHA."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from prepare import check_root,sha,save,verify_prepared


def exposure(root):
    path=root/'payload/outputs/EXPOSURE_LEDGER.json'
    if path.is_file():
        try:return dict(status='RAW_RUNTIME_LEDGER_PRESERVED',path=str(path),sha256=sha(path),raw=json.loads(path.read_text()))
        except ValueError as exc:return dict(status='INVALID_RAW_RUNTIME_LEDGER_PRESERVED',path=str(path),error=repr(exc),future_test_exclusion_review_required=True)
    initial=json.loads((root/'EXPOSURE_LEDGER_INITIAL.json').read_text())
    attempted=(root/'job_evidence/training.json').exists()
    return dict(status='RUNTIME_LEDGER_MISSING',training_entry_attempted=attempted,
        initial_selected_units=initial['units'],actual_optimizer_consumption='UNKNOWN' if attempted else 'NOT_STARTED',
        future_test_exclusion_review_required=attempted,
        note='Do not fabricate consumed units; conservatively review all reserved subjects if execution stage unknown')


def collect(root):
    check_root(root);job=(root/'job_id.txt').read_text().strip();bundle=root/('JOB_'+job+'_evidence.zip')
    if bundle.exists() or (root/'COLLECTION_S00.json').exists():raise FileExistsError('already collected')
    command=['djob','-J','-l',job]
    q=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    (root/'djob_final.json').write_bytes(q.stdout);(root/'djob_final.stderr').write_bytes(q.stderr)
    if q.returncode:raise RuntimeError('raw query saved; terminal query failed')
    rows=json.loads(q.stdout)['data']['successData']
    if len(rows)!=1 or str(rows[0]['jobId'])!=job or rows[0]['state'] not in ('SUCCEEDED','FAILED','CANCELLED'):raise ValueError('exact terminal job required')
    row=rows[0]
    try:verify_prepared(root);source_status='UNCHANGED'
    except Exception as exc:source_status=repr(exc)
    recon=exposure(root);save(root/'EXPOSURE_RECONCILIATION.json',recon)
    files=sorted(p for p in root.rglob('*') if p.is_file() and p.name not in ('bundle_receipt.json',bundle.name))
    metadata={};archived=[];remote_only=[]
    for p in files:
        before=p.stat();digest=sha(p);after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('terminal file changing: '+str(p))
        name=p.relative_to(root).as_posix();omit=p.suffix.lower() in ('.pt','.pth','.npz')
        metadata[name]=dict(path=str(p),bytes=after.st_size,mtime_ns=after.st_mtime_ns,sha256=digest,archive_payload=not omit)
        if omit:remote_only.append(name)
        else:archived.append(p)
    results=list((root/'payload/outputs').glob('*/result.json'))
    app=None
    if len(results)==1:
        try:app=json.loads(results[0].read_text())
        except ValueError:pass
    missing=[]
    if len(results)!=1:missing.append('exactly_one_application_result')
    for name in ('job.log','scheduler_allocation.json','job_evidence/cleanup.json','job_evidence/SUMMARY.json','payload/outputs/EXPOSURE_LEDGER.json'):
        if not (root/name).is_file():missing.append(name)
    index=root/'COLLECTION_S00.json'
    save(index,dict(job_id=job,state=row['state'],job_exit_code=row.get('jobExitCode'),query_command=command,
      scheduler_pids_cleared=all(n['pids']=='-' for g in row['resGroups'] for n in g['nodeResUsages']),
      source_status=source_status,files=metadata,remote_only=remote_only,missing=missing,
      application_status=app.get('status') if app else None,exposure_reconciliation=recon,
      start_time=row.get('startTime'),end_time=row.get('endTime'),engineering_only=True,
      formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',retries=0))
    archived.append(index)
    with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as z:
        for p in archived:z.write(p,p.relative_to(root).as_posix())
    receipt=dict(bundle=str(bundle),bytes=bundle.stat().st_size,sha256=sha(bundle),archived_files=len(archived),remote_only=remote_only)
    save(root/'bundle_receipt.json',receipt);print(json.dumps(receipt));return receipt


if __name__=='__main__':collect(Path(sys.argv[1]).resolve())
