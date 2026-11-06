"""Exactly one engineering entry: gate+training<=840, cleanup<=30, closing30."""
import time
START=time.monotonic()
import ctypes
import json
import os
from pathlib import Path
import signal
import sys
import traceback
from prepare import check_root,save,sha,verify_prepared
from review_gate import check_review
from owned_processes import Owned,run_phase,cleanup


def interrupted(signum,frame):raise InterruptedError('outer signal '+str(signum))


def main(root):
    check_root(root);out=root/'job_evidence';out.mkdir(exist_ok=False)
    owner=Owned(os.getpid());code=2
    summary=dict(status='FAIL_STOP_NO_RETRY',engineering_only=True,protocol='ENGINEERING_REAL_CORPUS_PILOT_V1',
        formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
        job_id=os.environ.get('CCS_JOB_ID'),started=START,execution_seconds=840,cleanup_seconds=30,closing_seconds=30,job_seconds=900,attempts=1)
    try:
        if sys.platform!='linux' or not os.environ.get('CCS_JOB_ID'):raise ValueError('native Linux compute job required')
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(36,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'cannot own orphaned descendants')
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM):signal.signal(sig,interrupted)
        signal.setitimer(signal.ITIMER_REAL,max(.001,START+840-time.monotonic()))
        check_review(root,os.environ['S00_REVIEW_SHA']);pins=verify_prepared(root)
        run_phase(root,owner,'gate',['/usr/bin/python3','-B',str(root/'gate.py'),str(root),str(START+30)],START+30)
        os.environ.update(S02_ENGINEERING_DESCRIPTOR=str(root/'ENGINEERING_DESCRIPTOR.json'),S02_ENGINEERING_DESCRIPTOR_SHA256=pins['descriptor_sha256'])
        record=run_phase(root,owner,'training',['/bin/bash',str(root/'payload'/pins['entrypoint'])],START+840,allowed=(0,3))
        result_paths=list((root/'payload/outputs').glob('*/result.json'))
        if len(result_paths)!=1:raise ValueError('one original engineering result required')
        app=json.loads(result_paths[0].read_text());summary['application_result']=str(result_paths[0]);summary['application_status']=app.get('status')
        if app.get('protocol')!='ENGINEERING_REAL_CORPUS_PILOT_V1' or app.get('engineering_only') is not True:raise ValueError('application scope drift')
        if record['returncode']==0:
            if app.get('status')!='ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE':raise ValueError('missing original engineering completion')
            if app.get('completed_updates',0)<2:raise ValueError('multiple real optimizer batches required')
            summary['status']=app['status'];code=0
        else:summary['status']='INCOMPLETE';code=3
        verify_prepared(root)
    except BaseException as exc:summary.update(error=repr(exc),traceback=traceback.format_exc())
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,signal.SIG_IGN)
        try:
            clean=cleanup(owner,min(time.monotonic()+30,START+870));save(out/'cleanup.json',clean)
            if not clean['all_reaped']:summary.update(status='FAIL_STOP_NO_RETRY',cleanup_incomplete=True);code=2
        except BaseException as exc:summary.update(status='FAIL_STOP_NO_RETRY',cleanup_error=repr(exc));code=2
        summary.update(finished=time.monotonic(),exit_code=code);save(out/'SUMMARY.json',summary)
    return code


if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]).resolve()))
