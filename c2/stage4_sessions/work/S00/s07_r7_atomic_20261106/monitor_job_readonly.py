"""Foreground read-only monitor of the one R7 job; never resubmits."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S07_ATOMIC_R7_20261106T073004Z_P1');job=(root/'job_id.txt').read_text().strip();stop=time.monotonic()+350
while time.monotonic()<stop:
    record=dict(utc=datetime.now(timezone.utc).isoformat(),job_id=job,cases={},finished_steps={})
    try:
        row=json.loads(subprocess.run(['djob','-J','-l',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5).stdout)['data']['successData'][0]
        if str(row['jobId'])!=job:raise ValueError('wrong job')
        record.update(state=row['state'],job_exit_code=row.get('jobExitCode'),start_time=row.get('startTime'),end_time=row.get('endTime'),nodes=row.get('taskExecNodes'))
        for path in (root/'job_evidence').glob('*.json'):
            if path.name.endswith('_cleanup.json'):continue
            value=json.loads(path.read_text());record['finished_steps'][path.stem]={k:value.get(k) for k in ('returncode','status','error')}
        for case in ('normal','crash','collective-timeout','watchdog'):
            d=root/'payload/checks_current_job'/case
            if not d.exists():continue
            info={}
            for rank in (0,1):
                p=d/f'rank{rank}.events.jsonl'
                if p.is_file():
                    lines=p.read_bytes().splitlines()
                    if lines:
                        e=json.loads(lines[-1]);info['rank'+str(rank)+'_last']={k:e.get(k) for k in ('event','stage','monotonic_ns')}
            p=d/'summary.json'
            if p.is_file():
                s=json.loads(p.read_text());info.update(status=s.get('status'),supervisor=s.get('supervisor'))
            record['cases'][case]=info
    except Exception as exc:record['monitor_error']=repr(exc)
    print(json.dumps(record,sort_keys=True),flush=True)
    if record.get('state') in ('SUCCEEDED','FAILED','CANCELLED'):break
    time.sleep(30)
