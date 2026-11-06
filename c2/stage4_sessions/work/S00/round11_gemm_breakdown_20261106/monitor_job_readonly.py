"""Foreground read-only monitoring of the one submitted job; no retry/submit."""
import datetime
import json
from pathlib import Path
import subprocess
import time

root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_20261106T041202Z')
job=(root/'job_id.txt').read_text().strip()
deadline=time.monotonic()+1000
while time.monotonic()<deadline:
    record=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=job)
    try:
        q=subprocess.run(['djob','-J','-l',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        record.update(query_returncode=q.returncode,raw_scheduler=q.stdout.decode(errors='replace'),query_stderr=q.stderr.decode(errors='replace'))
        row=json.loads(q.stdout)['data']['successData'][0]
        if str(row['jobId'])!=job:raise ValueError('wrong observed job')
        record.update(state=row['state'],job_exit_code=row.get('jobExitCode'),start_time=row.get('startTime'),end_time=row.get('endTime'))
        runs=list((root/'payload/outputs').glob('gemm_*'))
        if len(runs)==1:
            steps=runs[0]/'steps.jsonl'
            if steps.is_file():
                lines=steps.read_text().splitlines();record['step_records']=len(lines)
                if lines:
                    last=json.loads(lines[-1]);record['last_step']={k:last.get(k) for k in ('step','batch_size','cursor','losses','step_seconds','kml_calls','adamw_step')}
            result=runs[0]/'result.json'
            if result.is_file():
                app=json.loads(result.read_text());record['application']={k:app.get(k) for k in ('status','completed_updates','planned_updates','consumed_frames','stop_reason','error','recovery','checkpoint')}
        exp=root/'payload/outputs'/('gemm_'+job)/'EXPOSURE_LEDGER.json'
        if exp.is_file():
            ledger=json.loads(exp.read_text());record['exposure']=dict(confirmed_updates=len(ledger.get('confirmed_updates',[])),in_flight=ledger.get('in_flight') is not None,unit_usage={x['unit']:x['usage_status'] for x in ledger.get('units',[])})
    except Exception as exc:record['monitor_error']=repr(exc)
    print(json.dumps(record,sort_keys=True),flush=True)
    if record.get('state') in ('SUCCEEDED','FAILED','CANCELLED'):break
    time.sleep(30)
