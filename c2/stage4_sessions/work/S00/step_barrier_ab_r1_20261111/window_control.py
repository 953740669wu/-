"""Common fixed window, plus the A-only per-step rendezvous."""
import fcntl
import json
import os
import time

WINDOW_NS = 600_000_000_000
PER_ARM_CAP = 2000


class Window:
    def __init__(self, args, result, write):
        self.args, self.write = args, write
        self.arm = args.arm
        self.events = result['barrier_waits'] = []
        self.record = result['window'] = {}

    def closed(self):
        return bool(self.record) and time.monotonic_ns() >= self.record['close_ns']

    def rendezvous(self, step):
        if step > 6 and self.arm == 'B':
            return None if self.closed() else 0
        d = self.args.phase_root/'barriers'
        begin = time.monotonic_ns()
        self.write(d/f'{step}.{self.args.output.name}.ready',
                   dict(pid=os.getpid(), arrived=begin))
        path = d/f'{step}.release'
        release = None
        while time.monotonic() < self.args.deadline and not self.closed():
            if path.is_file():
                release = json.loads(path.read_bytes())['release_at_ns']
                if step == 6:
                    self.record.update(open_ns=release, close_ns=release+WINDOW_NS)
                time.sleep(max(0,(release-time.monotonic_ns())/1e9))
                break
            time.sleep(.01)
        end = time.monotonic_ns()
        if self.closed():
            release = None
        self.events.append(dict(step=step, start_ns=begin, end_ns=end, release_ns=release))
        if release is None and not self.closed():
            raise TimeoutError(f'barrier {step} deadline')
        return release

    def reserve_update(self):
        # Common to both arms and local to the one allocated host. No peer rendezvous.
        with self.args.counter.open('r+b', buffering=0) as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            if self.closed():
                return False
            used = int(f.read())
            if used >= PER_ARM_CAP:
                raise RuntimeError('shared 2000-update arm cap reached before the fixed window ended')
            f.seek(0)
            f.write(f'{used+1:04d}'.encode())
        return True
