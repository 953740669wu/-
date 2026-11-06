"""One watchdog-only Python dump and one owned, bounded /proc reader."""
import ast
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import cpu36_contract as cpu36

PROC = Path('/proc')
PROC_SECONDS = 2
_RETAINED_FILES = []


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def guard_cpu(selected):
    actual = sorted(os.sched_getaffinity(0))
    if not actual or not set(actual) <= set(selected):
        raise ValueError('diagnostic thread outside selected36')
    snapshot = cpu36.snapshot_threads(os.getpid())
    cpu36.validate_snapshot(selected, snapshot)
    return dict(calling_affinity=actual, snapshot=snapshot)


class StackDump:
    def __init__(self, directory, spec, rank, emit):
        self.directory, self.spec, self.rank, self.emit = directory, spec, rank, emit
        self.stream, self.armed, self.attempted = None, False, False
        self.state = dict(status='DISABLED', rank=rank, pid=os.getpid(),
                          run_id=spec.get('run_id'), job_id=spec.get('job_id'))

    def _publish(self):
        try:
            save(self.directory / f'rank{self.rank}.stack_status.json', self.state)
        except OSError as exc:
            self.emit('stack_status_error', error=str(exc))

    def arm(self):
        if self.attempted:
            return
        self.attempted = True
        if self.spec.get('case') != 'watchdog':
            return
        try:
            if not self.spec.get('job_id') or self.spec['job_id'] != os.environ.get('CCS_JOB_ID'):
                raise ValueError('stack observer native job mismatch')
            target = int(os.environ['S07_CASE_DEADLINE_NS']) - 5_000_000_000
            self.state['target_ns'] = target
            if time.monotonic_ns() >= target:
                self.state['status'] = 'MISSED'
                return
            selected = self.spec['allocation']['ranks'][self.rank]['selected']
            self.state['before_timer_cpu'] = guard_cpu(selected)
            self.stream = (self.directory / f'rank{self.rank}.python_stack.txt').open('xb', buffering=0)
            now = time.monotonic_ns()
            if now >= target:
                self.stream.close(); self.stream = None
                self.state['status'] = 'MISSED'
                return
            faulthandler.dump_traceback_later((target - now) / 1e9, repeat=False, file=self.stream, exit=False)
            self.armed = True
            self.state.update(status='ARMED', armed_at_ns=now)
            self.state['after_timer_cpu'] = guard_cpu(selected)
            self.emit('stack_dump_armed', target_ns=target, armed_at_ns=now)
        except Exception as exc:
            self.state.update(status='ERROR', error=repr(exc))
            self.cancel('arm_error')
            self.emit('stack_dump_error', error=repr(exc))
        finally:
            self._publish()

    def cancel(self, reason):
        if self.armed:
            try:
                faulthandler.cancel_dump_traceback_later()
                self.armed = False
                self.state['cancelled_at_ns'] = time.monotonic_ns()
            except Exception as exc:
                self.state.update(status='CANCEL_ERROR_FILE_RETAINED', cancel_error=repr(exc))
                if self.stream is not None and self.stream not in _RETAINED_FILES:
                    _RETAINED_FILES.append(self.stream)
                self._publish()
                return
        if self.stream is not None:
            try:
                self.stream.close()
                if self.stream in _RETAINED_FILES:
                    _RETAINED_FILES.remove(self.stream)
                self.stream = None
                if self.state['status'] not in ('ERROR', 'MISSED'):
                    self.state['status'] = 'CANCELLED_OR_DUMP_FINISHED'
            except OSError as exc:
                self.state['close_error'] = repr(exc)
        self.state.setdefault('cancel_reason', reason)
        self._publish()


def installed_sources(directory, rank):
    result = dict(status='RECORDED', files=[])
    for name in ('torch.distributed.distributed_c10d', 'torch.distributed.rendezvous'):
        item = dict(module=name)
        try:
            path = Path(sys.modules[name].__file__).resolve()
            before = path.stat()
            with path.open('rb') as stream:
                raw = stream.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError('not a small Python source')
            after = path.stat()
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                raise ValueError('installed source changed during read')
            calls = []
            for function in ast.parse(raw, filename=str(path)).body:
                if not isinstance(function, ast.FunctionDef) or function.name not in (
                        'init_process_group', '_new_process_group_helper', '_file_rendezvous_handler'):
                    continue
                for node in ast.walk(function):
                    if isinstance(node, ast.Call):
                        func = node.func
                        call = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')
                        if call in ('rendezvous', 'next', 'set_timeout', '_new_process_group_helper', 'ProcessGroupGloo', 'FileStore'):
                            calls.append(dict(function=function.name, call=call, line=node.lineno))
            item.update(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                        mtime_ns=after.st_mtime_ns, calls=sorted(calls, key=lambda x: x['line']))
        except Exception as exc:
            result['status'] = 'INCOMPLETE'
            item['error'] = repr(exc)
        result['files'].append(item)
    try:
        save(directory / f'rank{rank}.installed_python.json', result)
    except OSError as exc:
        result.update(status='INCOMPLETE', output_error=repr(exc))
    return result


def read_identity(pid):
    text = (PROC / str(pid) / 'stat').read_text()
    if int(text.split(' ', 1)[0]) != pid:
        raise ValueError('wrong /proc PID')
    fields = text[text.rfind(')') + 2:].split()
    return dict(pid=pid, ppid=int(fields[1]), sid=int(fields[3]), start_ticks=int(fields[19]))


def check_target(expected, selected):
    current = read_identity(expected['pid'])
    if current != expected:
        raise ValueError('target PID/start_ticks/parent/session changed')
    affinity = sorted(os.sched_getaffinity(expected['pid']))
    if not affinity or not set(affinity) <= set(selected):
        raise ValueError('target outside selected36')
    return dict(identity=current, affinity=affinity)


def bind_helper(selected, inherited):
    if not set(selected) <= set(inherited):
        raise ValueError('helper must not expand inherited CPU authority')
    os.sched_setaffinity(0, selected)
    return guard_cpu(selected)


def proc_field(path):
    try:
        with path.open('rb') as stream:
            raw = stream.read(65_537)
        return dict(status='TRUNCATED' if len(raw) > 65_536 else ('OK' if raw else 'EMPTY'),
                    text=raw[:65_536].decode('utf-8', errors='replace'))
    except TimeoutError:
        raise
    except OSError as exc:
        return dict(status='ERROR', error=repr(exc))


def run_proc(context, directory):
    result = dict(status='STARTED', target_ns=context['target_ns'],
                  sample_stop_ns=context['sample_stop_ns'], helper_pid=os.getpid(), ranks=[])
    try:
        if sys.platform != 'linux':
            result['status'] = 'UNSUPPORTED_PLATFORM'
            return result
        if (context.get('case') != 'watchdog' or len(context['pids']) != 2
                or len(set(context['pids'])) != 2
                or not context['target_ns'] < context['sample_stop_ns'] <= context['target_ns'] + 2_000_000_000):
            raise ValueError('watchdog only; two owned PIDs and at most two shared seconds required')
        if context['identity']['job_id'] != os.environ.get('CCS_JOB_ID') or context['parent_pid'] != os.getppid():
            raise ValueError('helper native job/owning parent mismatch')
        inherited = set(os.sched_getaffinity(0))
        for receipt in context['receipts']:
            cpu36.validate_receipt(receipt)
        bind_helper(context['receipts'][0]['selected'], inherited)
        baseline = []
        for pid in context['pids']:
            identity = read_identity(pid)
            if pid == os.getpid() or identity['ppid'] != os.getppid() or identity['sid'] != pid:
                raise ValueError('target is not a worker session created by owning parent')
            baseline.append(identity)
        save(directory / 'proc_identity.json', dict(identity=context['identity'], targets=baseline,
             inherited_affinity=sorted(inherited), captured_ns=time.monotonic_ns()))
        if time.monotonic_ns() >= context['target_ns']:
            result['status'] = 'MISSED'
            return result
        while True:
            remaining = (context['target_ns'] - time.monotonic_ns()) / 1e9
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))
        if time.monotonic_ns() >= context['sample_stop_ns']:
            result['status'] = 'MISSED_WINDOW'
            return result

        def alarm(*_):
            raise TimeoutError('shared two-second /proc budget reached')

        previous = signal.signal(signal.SIGALRM, alarm)
        try:
            signal.setitimer(signal.ITIMER_REAL, (context['sample_stop_ns'] - time.monotonic_ns()) / 1e9)
            result['sample_started_ns'] = time.monotonic_ns()
            with (directory / 'proc_fields.jsonl').open('x', encoding='utf-8') as stream:
                for rank, expected in enumerate(baseline):
                    if time.monotonic_ns() >= context['sample_stop_ns']:
                        raise TimeoutError('shared /proc deadline')
                    selected = context['receipts'][rank]['selected']
                    record = dict(rank=rank, pid=expected['pid'], sampled_ns=time.monotonic_ns())
                    try:
                        record['target'] = check_target(expected, selected)
                        record['helper_cpu'] = bind_helper(selected, inherited)
                        root = PROC / str(expected['pid'])
                        for name in ('wchan', 'syscall', 'stack', 'mountinfo'):
                            if time.monotonic_ns() >= context['sample_stop_ns']:
                                raise TimeoutError('shared /proc deadline')
                            field = dict(rank=rank, pid=expected['pid'], field=name, **proc_field(root / name))
                            stream.write(json.dumps(field) + '\n'); stream.flush()
                        fds = []
                        try:
                            for path in sorted((root / 'fd').iterdir(), key=lambda p: int(p.name))[:16]:
                                if time.monotonic_ns() >= context['sample_stop_ns']:
                                    raise TimeoutError('shared /proc deadline')
                                try:
                                    stat = path.stat()
                                    fds.append(dict(fd=int(path.name), link=os.readlink(path), dev=stat.st_dev, inode=stat.st_ino))
                                except TimeoutError:
                                    raise
                                except OSError as exc:
                                    fds.append(dict(fd=path.name, error=repr(exc)))
                        except TimeoutError:
                            raise
                        except OSError as exc:
                            record['fd_error'] = repr(exc)
                        record['fds_first16'] = fds
                        record['identity_after'] = check_target(expected, selected)
                        record['status'] = 'RECORDED'
                    except TimeoutError:
                        raise
                    except (OSError, ValueError) as exc:
                        record.update(status='REJECTED_OR_UNAVAILABLE', error=repr(exc))
                    result['ranks'].append(record)
            result['status'] = 'RECORDED_AVAILABLE_FIELDS_ONLY'
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    except Exception as exc:
        result.update(status='INCOMPLETE', error=repr(exc))
    finally:
        result['finished_ns'] = time.monotonic_ns()
        save(directory / 'proc_summary.json', result)
    return result


class ProcObserver:
    def __init__(self, directory, spec, processes, stop_ns, environment):
        self.directory, self.spec, self.processes, self.environment = directory, spec, processes, environment
        self.target_ns = stop_ns - 5_000_000_000
        self.stop_ns = self.target_ns + int(PROC_SECONDS * 1e9)
        self.process, self.log, self.attempted = None, None, False
        self.state = dict(status='DISABLED', target_ns=self.target_ns, sample_stop_ns=self.stop_ns)

    def start(self):
        if self.attempted:
            return
        self.attempted = True
        if self.spec.get('case') != 'watchdog':
            return
        if time.monotonic_ns() >= self.target_ns:
            self.state['status'] = 'MISSED'
            return
        try:
            context = dict(case='watchdog', identity={k: self.spec[k] for k in ('run_id', 'job_id', 'ready_token')},
                           parent_pid=os.getpid(), pids=[p.pid for p in self.processes],
                           receipts=self.spec['allocation']['ranks'], target_ns=self.target_ns,
                           sample_stop_ns=self.stop_ns)
            self.log = (self.directory / 'proc_helper.log').open('xb')
            self.process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), str(self.directory)],
                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=(os.name == 'posix'),
                env=dict(self.environment, S07_PROC_TASK=json.dumps(context), PYTHONDONTWRITEBYTECODE='1'))
            self.state.update(status='STARTED', helper_pid=self.process.pid)
        except Exception as exc:
            self.state.update(status='ERROR', error=repr(exc))

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def poll(self):
        if self.process is None:
            return
        code = self.process.poll()
        if code is not None:
            self.state.update(status='EXITED', returncode=code, reaped=True)
        elif time.monotonic_ns() >= self.stop_ns:
            self.state['timed_out'] = True
            self.stop()

    def stop(self):
        if self.running and not self.state.get('kill_sent'):
            try:
                self.process.kill()
                self.state.update(status='KILL_REQUESTED', kill_sent=True, kill_at_ns=time.monotonic_ns())
            except OSError as exc:
                self.state['kill_error'] = repr(exc)

    def receipt(self):
        self.poll()
        self.state['reaped'] = not self.running
        if not self.state['reaped']:
            self.state['status'] = 'UNREAPED'
        if self.log is not None:
            try:
                self.log.close()
            except OSError as exc:
                self.state['log_close_error'] = repr(exc)
            self.log = None
        return dict(self.state)


if __name__ == '__main__':
    run_proc(json.loads(os.environ['S07_PROC_TASK']), Path(sys.argv[1]))
