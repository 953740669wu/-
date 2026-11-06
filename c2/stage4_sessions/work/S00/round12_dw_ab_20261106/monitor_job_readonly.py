"""Foreground read-only monitoring of this one job; never submit/retry."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z')
job=(root/'job_id.txt').read_text().strip();deadline=time.monotonic()+1000
while time.monotonic()<deadline:
    record=dict(utc=datetime.now(timezone.utc).isoformat(),job_id=job,phases={})
    try:
        query=subprocess.run(['djob','-J','-l',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        row=json.loads(query.stdout)['data']['successData'][0]
        if str(row['jobId'])!=job:raise ValueError('wrong job')
        record.update(state=row['state'],job_exit_code=row.get('jobExitCode'),start_time=row.get('startTime'),end_time=row.get('endTime'),nodes=row.get('taskExecNodes'))
        for phase in ('target','strict','perf_baseline','perf_candidate'):
            directory=root/'payload/outputs'/(phase+'_'+job);info={}
            result=directory/('screen_result.json' if phase=='target' else 'result.json')
            if result.is_file():
                app=json.loads(result.read_text());info.update({k:app.get(k) for k in ('status','completed_updates','planned_updates','error')})
            log=directory/'steps.jsonl'
            if log.is_file():
                lines=log.read_text().splitlines();info['step_records']=len(lines)
                if lines:
                    last=json.loads(lines[-1]);info['last']={k:last.get(k) for k in ('step','role','step_seconds','kml_calls','native_sgemm_calls')}
            ledger=directory/'EXPOSURE_LEDGER.json'
            if ledger.is_file():
                exp=json.loads(ledger.read_text());info['confirmed_updates']=len(exp.get('confirmed_updates',[]));info['in_flight']=exp.get('in_flight') is not None
            if directory.exists():record['phases'][phase]=info
    except Exception as exc:record['monitor_error']=repr(exc)
    print(json.dumps(record,sort_keys=True),flush=True)
    if record.get('state') in ('SUCCEEDED','FAILED','CANCELLED'):break
    time.sleep(30)
