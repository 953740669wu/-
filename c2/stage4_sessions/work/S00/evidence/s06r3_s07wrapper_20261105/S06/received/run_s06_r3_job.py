"""First bounded S06 R3 job: exact tests, then exact six-stage original entry."""
import json
import os
from pathlib import Path
import re
import runpy
import signal
import socket
import sys
import time
import traceback
from bounded_step_s06 import run_step, save, sha
from scheduler_handoff import live_context, create_request, await_handoff

PY = '/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3'


def main(root):
    assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
    assert root.name.startswith('S06_R3_FIRST_') and not socket.gethostname().startswith('login')
    out = root / 'job_evidence'
    out.mkdir()
    payload = root / 'payload'
    deadline = time.monotonic() + 640
    summary = dict(status='STARTED', job_id=os.environ.get('CCS_JOB_ID'), host=socket.gethostname(),
        stages_expected=['imports', 'pointwise', 'conv', 'block', 'kml-explain', 'kml'], steps=[],
        full_model=False, formal_training=False, real_HBM=False)
    try:
        context = live_context()
        request = create_request(root, context)
        authority = await_handoff(root, request, context, 38, 8192, 660, timeout=30)
        assert live_context() == context
        save(out / 'scheduler_handoff_receipt.json', authority)
        pre = json.loads((root / 'pre_submit_checks.json').read_text())
        assert all(sha(root / name) == h for name, h in pre['payload_files'].items())
        policy = runpy.run_path(str(payload / 'candidate/cpu36_contract.py'))
        contracts = policy['discover_contracts'](context['allowed'], 1)
        node, contract = next(iter(contracts.items()))
        assert contract['allocated'] == context['allowed'] and len(contract['allocated']) == 38
        policy['validate_receipt'](contract)
        meminfo = Path('/sys/devices/system/node/node' + str(node) + '/meminfo').read_text()
        assert int(re.search(r'MemTotal:\s+(\d+)\s+kB', meminfo).group(1)) >= 8192 * 1024
        (out / 'selected_ddr_node_meminfo.txt').write_text(meminfo)
        save(out / 'cpu_ddr_receipt.json', dict(**context, contract=contract, DDR_node=node,
            source='current job raw allocation plus CPU-bearing sysfs domain; HBM=0'))
        expected = json.loads((payload / 'baseline/environment_expected.json').read_text())
        dependencies = dict(expected['library_sha256'])
        checked = {}
        for name, digest in dependencies.items():
            assert sha(name) == digest, 'runtime library identity: ' + name
            checked[name] = digest
        for path in [PY, '/usr/bin/g++', '/usr/bin/numactl', '/usr/bin/timeout']:
            assert os.access(path, os.X_OK), 'required executable: ' + path
        for path in [expected['torch']['file'], expected['numpy']['file']]:
            assert Path(path).is_file(), path
        save(out / 'dependency_identity.json', dict(library_sha256=checked, interpreter=PY,
            interpreter_resolved=str(Path(PY).resolve()), compiler='/usr/bin/g++', compiler_sha256=sha('/usr/bin/g++')))
        os.chdir(payload)
        for label, flags in [('ordinary_tests', ['-B']), ('isolated_tests', ['-I', '-S', '-B'])]:
            summary['steps'].append(run_step(out, label, [PY, *flags, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], deadline))
            log = (out / (label + '.txt')).read_text()
            assert re.search(r'Ran 26 tests?', log) and '\nOK' in log
            assert 'skipped=' not in log and '... skipped' not in log
        summary['standard_library_tests'] = dict(each_total=26, each_passed=26, each_skipped=0, launches=2)
        save(out / 'SUMMARY.json', summary)
        os.environ.update(S06_CPUSET=','.join(map(str, contract['selected'])), S06_MEMNODE=str(node))
        command = ['timeout', '--signal=TERM', '--kill-after=10s', '640s', 'bash', 'candidate/run_linux.sh']
        summary['steps'].append(run_step(out, 'original_six_stage_probe', command, deadline))
        runs = sorted((payload / 'evidence').glob('c2_' + context['job_id'] + '_*'))
        assert len(runs) == 1
        probe = json.loads((runs[0] / 'summary.json').read_text())
        summary['original_probe_summary'] = probe
        assert probe['status'] == 'PASS_DIAGNOSTIC_ONLY' and probe['not_run'] == []
        summary['status'] = 'PASS_S06_R3_SIX_STAGE_TINY_DIAGNOSTIC_ONLY'
        return 0
    except BaseException as exc:
        summary.update(status='FAIL_STOP_NO_RETRY', error=repr(exc), traceback=traceback.format_exc())
        return 1
    finally:
        save(out / 'SUMMARY.json', summary)


def interrupted(signum, frame):
    raise InterruptedError('signal ' + str(signum))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
