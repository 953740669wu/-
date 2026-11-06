"""Own two sessions; use absolute shared application/cleanup deadlines."""
import os
from pathlib import Path
import signal
import subprocess
import time

from runtime_guard import publish_json, record_event


def check_deadline(deadline_ns):
    if time.monotonic_ns() >= deadline_ns:
        raise TimeoutError('shared job application deadline reached')


def supervise(commands, directory, deadline_ns, cleanup_deadline_ns, environment, ready_context=None):
    processes, logs = [], []
    started_ns = time.monotonic_ns()
    state = dict(reason='complete', errors=[])
    events = directory / 'supervisor.events.jsonl'
    record_event(events, 'supervisor_begin', deadline_ns=deadline_ns,
                 cleanup_deadline_ns=cleanup_deadline_ns)
    try:
        check_deadline(deadline_ns)
        for rank, command in enumerate(commands):
            check_deadline(deadline_ns)
            log = (directory / f'rank{rank}.log').open('x', encoding='utf-8')
            logs.append(log)
            process = subprocess.Popen(command, env=environment, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
            processes.append(process)
            record_event(events, 'spawned', rank=rank, child_pid=process.pid)
        if ready_context is not None:
            publish_json(directory / 'participants.json', dict(ready_context,
                         pids=[p.pid for p in processes], deadline_ns=deadline_ns))
        while True:
            codes = [p.poll() for p in processes]
            if any(code is not None and code != 0 for code in codes):
                state['reason'] = 'child_failed'
                break
            if all(code == 0 for code in codes):
                break
            if time.monotonic_ns() >= deadline_ns:
                state['reason'] = 'deadline'
                break
            time.sleep(.05)
    except TimeoutError as exc:
        state.update(reason='deadline', errors=[str(exc)])
    except Exception as exc:
        state.update(reason='launch_failed', errors=[str(exc)])
    finally:
        record_event(events, 'cleanup_begin', reason=state['reason'])

        def send(process, sig):
            try:
                if os.name == 'posix':
                    os.killpg(process.pid, sig)
                elif process.poll() is None:
                    process.terminate() if sig == signal.SIGTERM else process.kill()
                record_event(events, 'signal_sent', child_pid=process.pid, signal=int(sig))
            except ProcessLookupError:
                pass

        for process in processes:
            send(process, signal.SIGTERM)
        grace = min(cleanup_deadline_ns, time.monotonic_ns() + 2 * 10**9)
        while any(p.poll() is None for p in processes) and time.monotonic_ns() < grace:
            time.sleep(.01)
        for process in processes:
            # SIGKILL is unavailable on Windows; kill() is the corresponding owned-child action.
            send(process, getattr(signal, 'SIGKILL', signal.SIGTERM + 1))
        while any(p.poll() is None for p in processes) and time.monotonic_ns() < cleanup_deadline_ns:
            time.sleep(.01)
        for process in processes:
            if process.poll() is not None:
                process.wait(timeout=0)
                record_event(events, 'child_reaped', child_pid=process.pid, exit_code=process.returncode)
        for log in logs:
            log.close()
    state.update(pids=[p.pid for p in processes], exit_codes=[p.returncode for p in processes],
                 all_reaped=all(p.returncode is not None for p in processes),
                 wall_seconds=(time.monotonic_ns()-started_ns)/1e9)
    if not state['all_reaped']:
        state['errors'].append('UNREAPED: outer owned cleanup must retain failure')
    record_event(events, 'supervisor_end', **state)
    return state
