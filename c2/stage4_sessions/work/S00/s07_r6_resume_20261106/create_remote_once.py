"""Read current/old scheduler state and markers before new S00 directory only."""
import json
from pathlib import Path
import subprocess
base=Path('/home/share/dengqingtian/opt/stage4_sessions/S00');root=base/'S07_STACK_R6_20261106T062352Z'
for pattern in ('S07_STACK_R6_*/submit_once.marker','S07_STACK_R6_*/job_id.txt'):
    paths=list(base.glob(pattern));print('EXISTING_R6_RECORDS',pattern,[str(p) for p in paths],flush=True)
    if paths:raise ValueError('existing R6 attempt: query original, do not create or submit')
queue=subprocess.run(['djob','-J'],check=True,stdout=subprocess.PIPE,timeout=10).stdout
old=subprocess.run(['djob','-J','-l','2041919'],check=True,stdout=subprocess.PIPE,timeout=10).stdout
row=json.loads(old)['data']['successData'][0]
if str(row['jobId'])!='2041919' or row['state'] not in ('SUCCEEDED','FAILED','CANCELLED'):raise ValueError('old S07 job not confirmed terminal')
old_root=base/'S07_READY_WRAP_R5_20261105T123530Z'
if (old_root/'job_id.txt').read_text().strip()!='2041919':raise ValueError('old directory job record differs')
print(queue.decode(),flush=True);print('OLD_S07_JOB',row['jobId'],row['state'],row.get('jobExitCode'),str(old_root),flush=True)
root.mkdir(exist_ok=False)
(root/'queue_before_deploy.raw').write_bytes(queue);(root/'old_2041919_state.raw').write_bytes(old)
print('NEW_R6_DIRECTORY_CREATED',str(root),flush=True)
