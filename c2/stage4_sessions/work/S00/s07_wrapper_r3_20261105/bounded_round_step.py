"""S00 orchestration only: bounded commands and cleanup of their own sessions."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def process_rows():
    rows = {}
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = p.read_text().rsplit(')', 1)[1].split()
            rows[int(p.parent.name)] = dict(state=fields[0], ppid=int(fields[1]),
                pgid=int(fields[2]), sid=int(fields[3]), start_ticks=int(fields[19]))
        except (OSError, ValueError, IndexError):
            continue
    return rows


def run_step(out, label, command, deadline, limit=None, allowed=(0,)):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('outer execution deadline reached before ' + label)
    stop = time.monotonic() + min(remaining, limit if limit is not None else remaining)
    record = dict(label=label, command=command, started=time.time(), inherited_affinity=sorted(os.sched_getaffinity(0)))
    sessions = set()
    with (out / (label + '.txt')).open('wb') as log:
        p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record['pid'] = p.pid
        sessions.add(p.pid)
        try:
            while p.poll() is None:
                rows = process_rows()
                children = {p.pid}
                while True:
                    expanded = children | {pid for pid, row in rows.items() if row['ppid'] in children}
                    if expanded == children:
                        break
                    children = expanded
                sessions.update(row['sid'] for pid, row in rows.items() if pid in children)
                if time.monotonic() >= stop:
                    record['timed_out'] = True
                    raise TimeoutError(label)
                time.sleep(0.1)
        finally:
            # Includes descendant sessions created by the unchanged S07 supervisor.
            cleanup_started = time.monotonic()
            cleanup = []
            for sig, grace in ((signal.SIGTERM, 2), (signal.SIGKILL, 10)):
                rows = process_rows()
                groups = sorted({row['pgid'] for row in rows.values()
                                 if row['sid'] in sessions and row['state'] != 'Z'})
                for pgid in groups:
                    try:
                        os.killpg(pgid, sig)
                        cleanup.append(dict(pgid=pgid, signal=int(sig)))
                    except ProcessLookupError:
                        pass
                until = min(cleanup_started + 15, time.monotonic() + grace)
                while time.monotonic() < until:
                    p.poll()
                    if not any(row['sid'] in sessions and row['state'] != 'Z' for row in process_rows().values()):
                        break
                    time.sleep(0.1)
            record.update(exit_code=p.wait(timeout=max(0.1, 15 - (time.monotonic() - cleanup_started))),
                          finished=time.time(), cleanup_actions=cleanup, owned_sessions=sorted(sessions),
                          remaining_live=[pid for pid, row in process_rows().items()
                                          if row['sid'] in sessions and row['state'] != 'Z'])
            save(out / (label + '_receipt.json'), record)
    if record['exit_code'] not in allowed or record.get('timed_out') or record['remaining_live']:
        raise RuntimeError('step failed: ' + json.dumps(record))
    return record
