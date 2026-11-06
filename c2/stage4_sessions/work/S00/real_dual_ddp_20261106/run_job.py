"""One real DDP entry: common840s execution, bounded30s cleanup,30s closing."""
import time
START_NS = time.monotonic_ns()
START = START_NS/1e9
import ctypes
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import traceback
from prepare import check_root, verify_prepared, save
from review_gate import check_review
from owned_processes import Owned, run_phase, cleanup


def interrupted(signum, frame):
    raise InterruptedError('outer signal '+str(signum))


def application_command(root, pins):
    training = root/'payload/training'
    return [pins['python'], '-B', str(training/'candidate/train_ddp.py'), 'run',
            '--config', str(training/'training_config.json'), '--allocation', str(root/'allocation.json'),
            '--reference-root', str(root/'payload/reference'), '--reference-ready', str(root/'REFERENCE_READY.json'),
            '--descriptor', str(root/'ENGINEERING_DESCRIPTOR.json'), '--output', str(root/'training_output'),
            '--job-start-ns', str(START_NS)]


def ddr_command(root, argv, reference_check=False):
    allocation = json.loads((root/'job_evidence/verified_allocation.json').read_text(encoding='utf-8'))
    nodes = sorted({receipt['node'] for receipt in allocation['ranks']})
    if len(nodes) != 2: raise ValueError('two current CPU-bearing DDR nodes required')
    if reference_check:
        rank0 = allocation['ranks'][0]
        return ['/usr/bin/numactl', '--physcpubind='+','.join(map(str,rank0['selected'])),
                '--membind='+str(rank0['node']), *argv]
    return ['/usr/bin/numactl', '--membind='+','.join(map(str,nodes)), *argv]


def main(root):
    check_root(root)
    out = root/'job_evidence'
    out.mkdir(exist_ok=False)
    owner = Owned(os.getpid())
    code = 1
    summary = dict(status='FAIL_STOP_NO_RETRY', job_id=os.environ.get('CCS_JOB_ID'), host=socket.gethostname(),
                   common_start_ns=START_NS, execution_deadline_ns=START_NS+840_000_000_000,
                   cleanup_deadline_ns=START_NS+870_000_000_000, job_deadline_ns=START_NS+900_000_000_000,
                   attempts=1, engineering_only=True, formal_split_status='UNKNOWN', subject_mapping_status='UNKNOWN',
                   training_started=False, stages=[])
    try:
        if sys.platform != 'linux' or not os.environ.get('CCS_JOB_ID') or socket.gethostname().startswith('login'):
            raise ValueError('native Linux compute job required')
        if sys.flags.optimize or os.environ.get('PYTHONOPTIMIZE'): raise ValueError('assertions must remain active')
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36,1,0,0,0) != 0: raise OSError(ctypes.get_errno(), 'cannot own orphaned descendants')
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM): signal.signal(sig, interrupted)
        signal.setitimer(signal.ITIMER_REAL, max(.001, START+840-time.monotonic()))
        check_review(root, os.environ['S00_REVIEW_SHA'])
        pins = verify_prepared(root)
        summary['stages'].append(run_phase(root, owner, 'gate', ['/usr/bin/python3', '-B', str(root/'gate.py'),
                                                               str(root), str(START+30)], START+30))
        # This environment is set only after native authority and actual runtime
        # library identities pass. No Torch/model imports occur in this launcher.
        os.environ.update(pins['training_environment'])
        os.environ.update(S07_PY=pins['python'], S07_RUN=str(root/'payload/training'),
                          S07_ALLOCATION=str(root/'allocation.json'), S02_REFERENCE_ROOT=str(root/'payload/reference'),
                          S02_REFERENCE_READY=str(root/'REFERENCE_READY.json'),
                          S02_ENGINEERING_DESCRIPTOR=str(root/'ENGINEERING_DESCRIPTOR.json'),
                          S02_ENGINEERING_DESCRIPTOR_SHA256=pins['descriptor_sha256'],
                          S07_OUTPUT=str(root/'training_output'), JOB_START_MONOTONIC_NS=str(START_NS),
                          S07_TEST_ALLOCATION=str(root/'allocation.json'),
                          S07_REFERENCE_ROOT=str(root/'payload/reference'), S07_REFERENCE_READY=str(root/'REFERENCE_READY.json'))
        for check in pins['linux_checks']:
            label = Path(check['path']).stem
            summary['stages'].append(run_phase(root, owner, label,
                ddr_command(root, [pins['python'], '-B', str(root/'payload'/check['package']/check['path'])],
                            reference_check=check['package']=='reference'), START+840))
            log = (out/(label+'.log')).read_text()
            if (not re.search(r'Ran '+str(check['methods'])+r' tests?\b', log) or
                    not re.search(r'^OK\s*$', log, re.MULTILINE) or 'skipped=' in log or '... skipped' in log):
                raise ValueError('exact Linux test methods/no skips required: '+label)
        summary['training_started'] = True
        save(out/'SUMMARY.json', summary)
        record = run_phase(root, owner, 'training', ddr_command(root, application_command(root, pins)), START+840,
                           allowed=(0,1,2,3,124,137,143))
        summary['stages'].append(record)
        code = record['returncode']
        summary['status'] = 'APPLICATION_EXIT0_PENDING_RESULT_AUDIT' if code == 0 else 'FAIL_STOP_NO_RETRY'
        verify_prepared(root)
    except BaseException as exc:
        summary.update(status='INCOMPLETE_STOP_NO_RETRY' if isinstance(exc, (TimeoutError,InterruptedError))
                       else 'FAIL_STOP_NO_RETRY', error=repr(exc), traceback=traceback.format_exc())
        code = 124 if isinstance(exc, (TimeoutError,InterruptedError)) else 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, signal.SIG_IGN)
        try:
            clean = cleanup(owner, min(time.monotonic()+30, START+870))
            save(out/'cleanup.json', clean)
            if not clean['all_reaped']:
                summary.update(status='FAIL_STOP_NO_RETRY', cleanup_incomplete=True)
                code = 1
        except BaseException as exc:
            summary.update(status='FAIL_STOP_NO_RETRY', cleanup_error=repr(exc))
            code = 1
        summary.update(finished_ns=time.monotonic_ns(), exit_code=code)
        save(out/'SUMMARY.json', summary)
    return code


if __name__ == '__main__': raise SystemExit(main(Path(sys.argv[1]).resolve()))
