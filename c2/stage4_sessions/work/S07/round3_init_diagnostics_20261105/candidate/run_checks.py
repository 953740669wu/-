"""Run once inside an already authorized two-domain job; never submits jobs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from comm_probe import write_json


def check_case(case, code, directory):
    summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    state = summary.get('supervisor', {})
    if not state.get('all_reaped') or len(state.get('pids', [])) != 2:
        raise ValueError(f'{case}: no complete child cleanup evidence')
    reports = [json.loads((directory / f'rank{rank}.json').read_text(encoding='utf-8'))
               for rank in range(2)]
    if case == 'normal':
        if code != 0 or summary['status'] != 'PASS':
            raise ValueError('normal communication failed')
    else:
        if code == 0 or summary['status'] != 'FAIL':
            raise ValueError(f'{case}: injected failure was accepted')
        if case == 'crash':
            if state['reason'] != 'child_failed' or state['exit_codes'][1] != 17:
                raise ValueError('crash did not propagate the injected rank1 exit17')
            if reports[1]['stage'] != 'injected_crash':
                raise ValueError('crash injection was not reached')
        elif case == 'collective-timeout':
            error = reports[0].get('error', '').lower()
            if (state['reason'] != 'child_failed' or reports[0]['stage'] != 'broadcast'
                    or not ('timed out' in error or 'timeout' in error)
                    or reports[1]['stage'] != 'injected_hang'):
                raise ValueError('no real Gloo collective timeout evidence')
        elif case == 'watchdog':
            if (code != 124 or state['reason'] != 'deadline'
                    or any(row['stage'] != 'injected_hang' for row in reports)):
                raise ValueError('watchdog injection/deadline evidence missing')
    return dict(case=case, expected_behavior='PASS', probe_exit=code, summary=summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allocation', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    probe = Path(__file__).with_name('comm_probe.py').resolve()
    results = []
    try:
        for case in ('normal', 'crash', 'collective-timeout', 'watchdog'):
            command = [sys.executable, '-B', str(probe), 'run', '--allocation',
                       str(args.allocation.resolve()), '--output', str(directory / case), '--case', case]
            # The probe owns its deadline and child sessions. Do not kill just its parent.
            code = subprocess.run(command).returncode
            results.append(check_case(case, code, directory / case))
        write_json(directory / 'checks.json', dict(status='PASS_PROBE_CHECKS_ONLY', cases=results))
        return 0
    except Exception as exc:
        write_json(directory / 'checks.json', dict(status='FAIL', cases=results, error=str(exc)))
        return 1


if __name__ == '__main__':
    sys.exit(main())
