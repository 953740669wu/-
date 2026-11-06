"""Owned descendants and bounded2s TERM/10s KILL, original15s cleanup cap; no frameworks."""
import time
import json
import os
from pathlib import Path
import signal
import subprocess
from prepare import save

def process_table():
    rows = {}
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            text = p.read_text(); f = text[text.rfind(')') + 2:].split()
            rows[int(p.parent.name)] = dict(state=f[0], ppid=int(f[1]), session=int(f[3]), start=int(f[19]))
        except (FileNotFoundError, ProcessLookupError): pass
    return rows


class Owned:
    """Subreaper owns orphaned descendants, including children that call setsid."""
    def __init__(self, parent):
        self.parent = parent
        self.identities = {}

    def update(self, rows):
        parents = {self.parent} | {p for p, start in self.identities.items()
                                  if p in rows and rows[p]['start'] == start}
        while True:
            new = {p for p, row in rows.items() if row['ppid'] in parents}
            if new <= parents: break
            parents.update(new)
        for p in parents - {self.parent}:
            if p in rows: self.identities[p] = rows[p]['start']

    def live(self, rows):
        return sorted(p for p, start in self.identities.items() if p in rows
                      and rows[p]['start'] == start and rows[p]['state'] != 'Z')


def reap():
    results = []
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0: return results
            results.append(dict(pid=pid, wait_status=status, exit_code=os.waitstatus_to_exitcode(status)))
        except ChildProcessError: return results


def cleanup(owner, deadline):
    started = time.monotonic()
    actions = []
    reaped = []
    sent = set()
    # These are absolute shared windows, never another timeout per descendant.
    term_end = min(started + 2, deadline)
    for name, sig, end in [('TERM', signal.SIGTERM, term_end),
                           ('KILL', signal.SIGKILL, min(started + 12, deadline))]:
        while True:
            rows = process_table(); owner.update(rows)
            live = owner.live(rows)
            for pid in live:
                identity = (pid, rows[pid]['start'], name)
                if identity in sent: continue
                # Recheck start ticks immediately before signalling; no unrelated groups.
                current = process_table().get(pid)
                if not current or current['start'] != identity[1]: continue
                try:
                    os.kill(pid, sig)
                    actions.append(dict(pid=pid, start_ticks=identity[1], signal=name, at=time.monotonic()))
                except ProcessLookupError: pass
                sent.add(identity)
            reaped.extend(reap())
            if not live or time.monotonic() >= end: break
            time.sleep(min(0.02, max(0, end - time.monotonic())))
    reaped.extend(reap())
    rows = process_table(); owner.update(rows)
    remaining = sorted(p for p, start in owner.identities.items() if p in rows and rows[p]['start'] == start)
    return dict(started=started, finished=time.monotonic(), deadline=deadline,
                actions=actions, owned=owner.identities, reaped=reaped,
                remaining_live=owner.live(rows), remaining_processes=remaining, all_reaped=not remaining,
                method='PR_SET_CHILD_SUBREAPER; descendants across sessions; PID/start-ticks checked')


def run_phase(root, owner, label, argv, deadline, allowed=(0,)):
    receipt = dict(command=argv, cwd=str(root), deadline=deadline, started=time.monotonic(), returncode=None)
    proc = None
    try:
        if receipt['started'] >= deadline: raise TimeoutError(label + ' budget exhausted before spawn')
        with (root / 'job_evidence' / (label + '.log')).open('xb') as log:
            proc = subprocess.Popen(argv, cwd=str(root), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            receipt['pid'] = proc.pid
            while True:
                owner.update(process_table())
                code = proc.poll()
                if code is not None:
                    receipt['returncode'] = code
                    if code not in allowed: raise RuntimeError(label + ' failed; no retry')
                    return receipt
                if time.monotonic() >= deadline: raise TimeoutError(label + ' timeout; no retry')
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
    finally:
        if proc is not None: receipt['returncode'] = proc.poll()
        receipt['finished'] = time.monotonic()
        save(root / 'job_evidence' / (label + '.json'), receipt)

