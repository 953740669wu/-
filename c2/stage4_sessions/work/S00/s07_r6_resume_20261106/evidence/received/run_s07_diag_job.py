"""One real two-domain R6 diagnostic; original frozen communication rules."""
import time
START=time.monotonic()
import ctypes
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import traceback
from bounded_round_step import run_step
from owned_processes import Owned,cleanup
from scheduler_handoff import live_context,create_request,await_handoff
from prepare import save,verify_prepared
from review_gate import check_review

CONSUMER_SECONDS=270
CLEANUP_SECONDS=15
CLOSING_SECONDS=15
CHECKS=[('stack_observer_tests','test_stack_observer.py',27,30),('readiness_tests','test_readiness.py',16,30),('diagnostic_tests','test_diagnostics.py',6,30),('job_identity_tests','test_job_identity.py',6,45),('probe_tests','test_probe.py',16,45)]
def interrupted(signum,_):raise InterruptedError('outer signal '+str(signum))
def main(root):
    out=root/'job_evidence';out.mkdir(exist_ok=False);owner=Owned(os.getpid());code=1
    summary=dict(status='FAIL_STOP_NO_RETRY',job_id=os.environ.get('CCS_JOB_ID'),host=socket.gethostname(),consumer_seconds=270,cleanup_seconds=15,closing_seconds=15,job_seconds=300,execution_deadline=START+270,real_HBM=False,formal_training=False,communication_passed=False,steps=[])
    try:
        if root.parent!=Path('/home/share/dengqingtian/opt/stage4_sessions/S00') or not root.name.startswith('S07_STACK_R6_'):raise ValueError('fresh owned R6 deployment required')
        if sys.platform!='linux' or not os.environ.get('CCS_JOB_ID') or socket.gethostname().startswith('login'):raise ValueError('native compute job required')
        if sys.flags.optimize or os.environ.get('PYTHONOPTIMIZE') or os.environ.get('LD_PRELOAD') or os.environ.get('KML_BLAS_LIB'):raise ValueError('original non-optimized S07 environment required')
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(36,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'cannot own descendants')
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM):signal.signal(sig,interrupted)
        signal.setitimer(signal.ITIMER_REAL,max(.001,START+270-time.monotonic()))
        check_review(root,os.environ['S00_REVIEW_SHA']);verify_prepared(root)
        payload=root/'payload';sys.path.insert(0,str(payload/'candidate'))
        import cpu36_contract as cpu36
        context=live_context();summary['inherited_affinity']=context['allowed'];request=create_request(root,context)
        authority=await_handoff(root,request,context,76,24576,300,timeout=30)
        if live_context()!=context:raise ValueError('native context changed')
        save(out/'scheduler_handoff_receipt.json',authority)
        contracts=cpu36.discover_contracts(authority['allowed'],2)
        if set(authority['allowed'])!=set().union(*(set(c['allocated']) for c in contracts.values())) or any(len(c['allocated'])!=38 for c in contracts.values()):raise ValueError('two full physical domains required')
        save(payload/'allocation.json',dict(job_id=context['job_id'],scheduler_evidence=authority['scheduler_evidence'],ranks={str(rank):dict(node=node,allocated=receipt['allocated']) for rank,(node,receipt) in enumerate(contracts.items())}))
        import comm_probe
        save(out/'verified_allocation.json',comm_probe.load_allocation(payload/'allocation.json'))
        py=os.environ['S07_PY'];deadline=START+270
        for label,script,count,limit in CHECKS:
            summary['steps'].append(run_step(root,owner,label,[py,'-B',str(payload/'tests'/script)],deadline,limit))
            log=(out/(label+'.log')).read_text()
            if not re.search(r'Ran '+str(count)+r' tests?',log) or 'OK' not in log or 'skipped=' in log or '... skipped' in log:raise ValueError('exact Linux test count/no skips required: '+label)
        summary['standard_library_tests']=dict(passed=71,skipped=0)
        summary['steps'].append(run_step(root,owner,'environment',[py,'-B',str(payload/'candidate/comm_probe.py'),'environment','--output',str(payload/'environment_current.json')],deadline,60))
        env=json.loads((payload/'environment_current.json').read_text())
        if not (env['status']=='AVAILABLE_BUILT_NOT_COMM_TESTED' and env['distributed'] and env['gloo'] and env['torch_version']=='2.7.1+cpu' and env['executable']==py and env['torch_path']=='/home/share/songzhenlong/eitfm/sw/torch_kml/torch/__init__.py' and not env['environment']['LD_PRELOAD'] and env['loaded_torch_libraries']):raise ValueError('original Gloo environment identity mismatch')
        summary['steps'].append(run_step(root,owner,'run_checks',[py,'-B',str(payload/'candidate/run_checks.py'),'--allocation',str(payload/'allocation.json'),'--output',str(payload/'checks_current_job')],deadline))
        checks=json.loads((payload/'checks_current_job/checks.json').read_text())
        if checks['status']!='PASS_PROBE_CHECKS_ONLY' or [c['case'] for c in checks['cases']]!=['normal','crash','collective-timeout','watchdog']:raise ValueError('original four-case gate failed')
        verify_prepared(root);summary.update(status='PASS_S07_R6_FIXED_TWO_RANK_TENSOR_PROBE_ONLY',communication_passed=True,cases=checks['cases']);code=0
    except BaseException as exc:summary.update(error=repr(exc),traceback=traceback.format_exc(),status='INCOMPLETE_STOP_NO_RETRY' if isinstance(exc,(TimeoutError,InterruptedError)) else 'FAIL_STOP_NO_RETRY')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,signal.SIG_IGN)
        try:
            clean=cleanup(owner,min(time.monotonic()+15,START+285));save(out/'cleanup.json',clean)
            if not clean['all_reaped']:summary.update(status='FAIL_STOP_NO_RETRY',cleanup_incomplete=True);code=1
        except BaseException as exc:summary.update(cleanup_error=repr(exc));code=1
        summary.update(finished=time.monotonic(),exit_code=code);save(out/'SUMMARY.json',summary)
    return code
if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]).resolve()))
