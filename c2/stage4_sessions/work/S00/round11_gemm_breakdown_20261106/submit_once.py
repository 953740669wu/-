"""Login only: S01 bound review then durable single attempt; no automatic retry."""
import json
from pathlib import Path
import subprocess
import sys
import time
from prepare import check_root,verify_prepared,save
from review_gate import check_review
from scheduler_handoff import publish


def command(root,review_sha):
    return ['dsub','-J','-q','q_hpcai','-x','job','-R','cpu=38,mem=24576MB','-RL','mem=24576MB',
      '-a','numa[count=1,distribution=pack]','-T','900','--env','none','--cwd',str(root),
      '-oo',str(root/'job.log'),'bash',str(root/'run_job.sh'),review_sha]


def submit(root):
    check_root(root);verify_prepared(root);review_sha=check_review(root)
    with (root/'submit_once.marker').open('x') as f:f.write('one engineering job attempt including ambiguous failures; no retry\n')
    argv=command(root,review_sha);save(root/'submission.command.json',dict(command=argv,review_sha256=review_sha,attempts=1))
    try:p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    except subprocess.TimeoutExpired as exc:
        (root/'submission.stdout').write_bytes(exc.stdout or b'');(root/'submission.stderr').write_bytes(exc.stderr or b'')
        save(root/'submission.result.json',dict(timed_out=True,ambiguous_job_id=True,retry=False));raise
    (root/'submission.stdout').write_bytes(p.stdout);(root/'submission.stderr').write_bytes(p.stderr)
    save(root/'submission.result.json',dict(returncode=p.returncode,timed_out=False,retry=False))
    if p.returncode:raise RuntimeError('submission failed; do not retry')
    job=str(json.loads(p.stdout)['data']['jobId']);(root/'job_id.txt').write_text(job+'\n')
    began=time.monotonic()
    while True:
        q=subprocess.run(['djob','-J','-l',job],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        (root/'scheduler_observed.json').write_bytes(q.stdout);(root/'scheduler_observed.stderr').write_bytes(q.stderr)
        if q.returncode:raise RuntimeError('observation failed; monitor same job, never resubmit')
        row=json.loads(q.stdout)['data']['successData'][0]
        if str(row['jobId'])!=job:raise ValueError('wrong observed job')
        if row['state']=='RUNNING':publish(root,job);print('PUBLISHED_ONCE',job,flush=True);return
        if row['state'] in ('SUCCEEDED','FAILED','CANCELLED'):raise RuntimeError('terminal before publication; collect')
        if time.monotonic()-began>=3600:
            # Caller may cancel ONLY this own not-started job after rechecking state.
            raise TimeoutError('own job queued60min; verify still not RUNNING then cancel only it; no retry')
        time.sleep(0.5)


if __name__=='__main__':submit(Path(sys.argv[1]).resolve())
