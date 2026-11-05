"""One authorized diagnostic-only two-domain probe, preserving original case verdicts."""
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import time
import traceback
from bounded_round_step import run_step, save, sha
from scheduler_handoff import live_context, create_request, await_handoff
from prepare import ARCHIVE, INNER_SHA


CONSUMER_SECONDS = 270
CHECKS = [('diagnostic_tests', 'test_diagnostics.py', 6, 30),
          ('job_identity_tests', 'test_job_identity.py', 6, 45),
          ('probe_tests', 'test_probe.py', 16, 45)]


def main(root):
    assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
    assert root.name.startswith('S07_INIT_DIAG_R4_') and os.environ.get('CCS_JOB_ID')
    assert not socket.gethostname().startswith('login')
    assert not os.environ.get('LD_PRELOAD') and not os.environ.get('KML_BLAS_LIB')
    out = root / 'job_evidence'
    out.mkdir()
    payload = root / 'payload'
    sys.path.insert(0, str(payload / 'candidate'))
    import cpu36_contract as cpu36
    deadline = time.monotonic() + CONSUMER_SECONDS
    summary = dict(status='STARTED', job_id=os.environ['CCS_JOB_ID'], host=socket.gethostname(),
        inherited_affinity=sorted(os.sched_getaffinity(0)), real_HBM=False, formal_training=False, steps=[])
    try:
        pre = json.loads((root / 'pre_submit_checks.json').read_text())
        assert pre['package_name'] == ARCHIVE and pre['package_sha256'] == INNER_SHA
        assert sha(root / ARCHIVE) == INNER_SHA and len(pre['payload_files']) == 12
        assert all(sha(root / name) == h for name, h in pre['payload_files'].items())
        context = live_context()
        request = create_request(root, context)
        authority = await_handoff(root, request, context, 76, 24576, 300, timeout=30)
        if live_context() != context:
            raise ValueError('native context changed during scheduler handoff')
        save(out / 'scheduler_handoff_receipt.json', authority)
        raw = Path(authority['scheduler_evidence'])
        allowed = authority['allowed']
        contracts = cpu36.discover_contracts(allowed, 2)
        assert set(allowed) == set().union(*(set(x['allocated']) for x in contracts.values()))
        assert all(len(x['allocated']) == 38 for x in contracts.values())
        allocation = dict(job_id=os.environ['CCS_JOB_ID'], scheduler_evidence=str(raw), ranks={
            str(rank): dict(node=node, allocated=receipt['allocated'])
            for rank, (node, receipt) in enumerate(contracts.items())})
        save(payload / 'allocation.json', allocation)
        # The unchanged R2 loader checks the live identity and all per-core topology.
        import comm_probe
        receipt = comm_probe.load_allocation(payload / 'allocation.json')
        save(out / 'verified_allocation.json', receipt)
        py = os.environ['S07_PY']
        for label, script, count, limit in CHECKS:
            summary['steps'].append(run_step(out, label, [py, '-B', str(payload / 'tests' / script)], deadline, limit=limit))
            log = (out / (label + '.txt')).read_text()
            assert re.search(r'Ran ' + str(count) + r' tests?', log) and 'OK' in log
            assert 'skipped=' not in log and '... skipped' not in log
        summary['standard_library_tests'] = dict(passed=28, skipped=0, linux_group_cleanup='PASSED')
        summary['steps'].append(run_step(out, 'environment', [py, '-B', str(payload / 'candidate/comm_probe.py'),
            'environment', '--output', str(payload / 'environment_current.json')], deadline, limit=60))
        env = json.loads((payload / 'environment_current.json').read_text())
        assert env['status'] == 'AVAILABLE_BUILT_NOT_COMM_TESTED' and env['distributed'] and env['gloo']
        assert env['torch_version'] == '2.7.1+cpu'
        assert env['executable'] == py and env['torch_path'] == '/home/share/songzhenlong/eitfm/sw/torch_kml/torch/__init__.py'
        assert not env['environment']['LD_PRELOAD'] and env['loaded_torch_libraries']
        summary['steps'].append(run_step(out, 'run_checks', [py, '-B', str(payload / 'candidate/run_checks.py'),
            '--allocation', str(payload / 'allocation.json'), '--output', str(payload / 'checks_current_job')], deadline))
        checks = json.loads((payload / 'checks_current_job/checks.json').read_text())
        assert checks['status'] == 'PASS_PROBE_CHECKS_ONLY' and [c['case'] for c in checks['cases']] == [
            'normal', 'crash', 'collective-timeout', 'watchdog']
        summary.update(status='PASS_S07_DIAGNOSTIC_FIXED_TWO_RANK_TENSOR_PROBE_ONLY', cases=checks['cases'])
        return 0
    except BaseException as exc:
        summary.update(status='FAIL_STOP_NO_RETRY', error=repr(exc), traceback=traceback.format_exc())
        return 1
    finally:
        save(out / 'SUMMARY.json', summary)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError('TERM')))
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
