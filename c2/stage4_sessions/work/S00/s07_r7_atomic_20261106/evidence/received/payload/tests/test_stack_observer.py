"""Absolute-clock diagnostics; no real Torch/Gloo or cluster resources."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'candidate'))
import stack_observer as observer
import comm_probe as probe
from test_readiness import fake_worker


class StackObserverChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BASE / 'evidence')
        self.directory = Path(self.temp.name).resolve()
        assert self.directory.is_relative_to(BASE / 'evidence')
        self.addCleanup(self.temp.cleanup)
        self.spec = dict(case='watchdog', run_id='watchdog', job_id='synthetic',
                         allocation=dict(ranks=[dict(selected=[0])] * 2))
        self.emit = Mock()

    @contextlib.contextmanager
    def timer_context(self, now=3_000_000_000):
        with patch.dict(os.environ, CCS_JOB_ID='synthetic', S07_CASE_DEADLINE_NS='30000000000'), \
                patch.object(observer.time, 'monotonic_ns', return_value=now), \
                patch.object(observer, 'guard_cpu', return_value={'checked': True}), \
                patch.object(observer.faulthandler, 'dump_traceback_later') as dump, \
                patch.object(observer.faulthandler, 'cancel_dump_traceback_later') as cancel:
            yield dump, cancel

    def test_absolute_target_and_no_rearm(self):
        with self.timer_context() as (dump, cancel):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit)
            timer.arm(); timer.arm()
            dump.assert_called_once()
            self.assertEqual(dump.call_args.args, (22.0,))
            self.assertEqual(dump.call_args.kwargs['repeat'], False)
            self.assertEqual(dump.call_args.kwargs['exit'], False)
            stream = dump.call_args.kwargs['file']
            self.assertFalse(stream.closed)
            timer.cancel('init_end'); timer.cancel('finally')
            cancel.assert_called_once()
            self.assertTrue(stream.closed)
            self.assertEqual(timer.state['target_ns'], 25_000_000_000)
            self.assertEqual(timer.state['cancel_reason'], 'init_end')

    def test_cancel_happens_before_file_close(self):
        with self.timer_context() as (dump, cancel):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            stream = dump.call_args.kwargs['file']
            cancel.side_effect = lambda: self.assertFalse(stream.closed)
            timer.cancel('finally')
            self.assertTrue(stream.closed)

    def test_missed_target_is_not_reset(self):
        with self.timer_context(now=25_000_000_000) as (dump, _):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            self.assertEqual(timer.state['status'], 'MISSED')
            dump.assert_not_called()

    def test_file_open_delay_can_miss_target(self):
        with self.timer_context() as (dump, _), \
                patch.object(observer.time, 'monotonic_ns', side_effect=[3_000_000_000, 26_000_000_000]):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            self.assertEqual(timer.state['status'], 'MISSED')
            dump.assert_not_called()
            self.assertIsNone(timer.stream)

    def test_only_watchdog(self):
        self.spec['case'] = 'normal'
        with self.timer_context() as (dump, _):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            self.assertEqual(timer.state['status'], 'DISABLED')
            dump.assert_not_called()

    def test_timer_error_does_not_escape_cleanup(self):
        with self.timer_context() as (dump, _):
            dump.side_effect = RuntimeError('timer unavailable')
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm(); timer.cancel('finally')
            self.assertEqual(timer.state['status'], 'ERROR')
            self.assertIsNone(timer.stream)

    def test_cancel_error_keeps_descriptor_open(self):
        with self.timer_context() as (dump, cancel):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            stream = dump.call_args.kwargs['file']; cancel.side_effect = RuntimeError('cancel failed')
            timer.cancel('finally')
            self.assertFalse(stream.closed)
            self.assertEqual(timer.state['status'], 'CANCEL_ERROR_FILE_RETAINED')
            cancel.side_effect = None; timer.cancel('test cleanup')
            self.assertTrue(stream.closed)

    def test_wrong_job_or_cpu_never_arms(self):
        for mode in ('job', 'cpu'):
            with self.subTest(mode=mode), self.timer_context() as (dump, _):
                if mode == 'job':
                    with patch.dict(os.environ, CCS_JOB_ID='old'):
                        timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
                else:
                    with patch.object(observer, 'guard_cpu', side_effect=ValueError('outside CPU boundary')):
                        timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
                dump.assert_not_called(); self.assertEqual(timer.state['status'], 'ERROR')

    def test_real_local_timer_dumps_once_and_keeps_file(self):
        deadline = time.monotonic_ns() + 5_080_000_000
        with patch.dict(os.environ, CCS_JOB_ID='synthetic', S07_CASE_DEADLINE_NS=str(deadline)), \
                patch.object(observer, 'guard_cpu', return_value={'scope': 'test stub'}):
            timer = observer.StackDump(self.directory, self.spec, 0, self.emit); timer.arm()
            self.assertEqual(timer.state['status'], 'ARMED')
            time.sleep(0.20)
            timer.cancel('test completion')
        raw = (self.directory / 'rank0.python_stack.txt').read_text()
        self.assertEqual(raw.count('Timeout ('), 1)

    def test_installed_source_hashes_and_call_positions(self):
        c10d = self.directory / 'distributed_c10d.py'
        c10d.write_text('def init_process_group():\n    next(rendezvous())\n    store.set_timeout(timeout)\n', encoding='utf-8')
        rendezvous = self.directory / 'rendezvous.py'
        rendezvous.write_text('def _file_rendezvous_handler():\n    store = FileStore(path, size)\n    yield store\n', encoding='utf-8')
        with patch.dict(sys.modules, {'torch.distributed.distributed_c10d': types.SimpleNamespace(__file__=str(c10d)),
                                     'torch.distributed.rendezvous': types.SimpleNamespace(__file__=str(rendezvous))}):
            data = observer.installed_sources(self.directory, 0)
        self.assertEqual(data['status'], 'RECORDED')
        self.assertEqual(len(data['files']), 2)
        self.assertTrue(all(len(item['sha256']) == 64 for item in data['files']))
        self.assertTrue(any(call['call'] == 'set_timeout' for call in data['files'][0]['calls']))

    def test_missing_installed_source_is_recorded(self):
        with patch.dict(sys.modules, {'torch.distributed.distributed_c10d': None, 'torch.distributed.rendezvous': None}):
            data = observer.installed_sources(self.directory, 0)
        self.assertEqual(data['status'], 'INCOMPLETE')

    def test_permission_and_empty_proc_fields_preserved(self):
        path = self.directory / 'field'; path.write_text('', encoding='utf-8')
        self.assertEqual(observer.proc_field(path)['status'], 'EMPTY')
        with patch.object(Path, 'open', side_effect=PermissionError('denied')):
            self.assertEqual(observer.proc_field(path)['status'], 'ERROR')

    def test_proc_alarm_is_not_swallowed_as_permission_error(self):
        with patch.object(Path, 'open', side_effect=TimeoutError('shared deadline')), self.assertRaises(TimeoutError):
            observer.proc_field(self.directory / 'blocked')

    def fake_proc(self):
        root = self.directory / 'proc'; root.mkdir()
        for pid in (101, 102):
            directory = root / str(pid); directory.mkdir(); (directory / 'fd').mkdir()
            fields = ['S', '100', str(pid), str(pid)] + ['0'] * 15 + [str(pid + 500), '0']
            (directory / 'stat').write_text(f'{pid} (fake process) ' + ' '.join(fields), encoding='utf-8')
            for name in ('wchan', 'syscall', 'stack', 'mountinfo'):
                (directory / name).write_text('fixture ' + name, encoding='utf-8')
        return root

    @contextlib.contextmanager
    def proc_context(self, root, now, sleeping):
        with patch.object(observer, 'PROC', root), patch.object(observer.sys, 'platform', 'linux'), \
                patch.dict(os.environ, CCS_JOB_ID='synthetic'), patch.object(observer.os, 'getppid', return_value=100), \
                patch.object(observer.os, 'sched_getaffinity', create=True, return_value={0}), \
                patch.object(observer.os, 'sched_setaffinity', create=True), \
                patch.object(observer.cpu36, 'validate_receipt'), patch.object(observer, 'guard_cpu', return_value={}), \
                patch.object(observer.time, 'monotonic_ns', side_effect=now), \
                patch.object(observer.time, 'sleep', side_effect=sleeping), \
                patch.object(observer.signal, 'SIGALRM', create=True, new=14), \
                patch.object(observer.signal, 'ITIMER_REAL', create=True, new=0), \
                patch.object(observer.signal, 'signal'), \
                patch.object(observer.signal, 'setitimer', create=True) as alarm:
            yield alarm

    def proc_task(self):
        return dict(case='watchdog', identity=dict(run_id='watchdog', job_id='synthetic', ready_token='nonce'),
                    parent_pid=100, pids=[101, 102], receipts=[dict(selected=[0])] * 2,
                    target_ns=25_000_000_000, sample_stop_ns=27_000_000_000)

    def test_proc_capture_uses_remaining_shared_budget(self):
        root = self.fake_proc(); clock = [3_000_000_000]
        with self.proc_context(root, lambda: clock[0], lambda _: clock.__setitem__(0, 26_000_000_000)) as alarm:
            result = observer.run_proc(self.proc_task(), self.directory)
        self.assertEqual(result['status'], 'RECORDED_AVAILABLE_FIELDS_ONLY')
        self.assertEqual([x['status'] for x in result['ranks']], ['RECORDED', 'RECORDED'])
        self.assertEqual(alarm.call_args_list[0].args, (0, 1.0))
        self.assertEqual(result['sample_stop_ns'], 27_000_000_000)
        rows = [json.loads(x) for x in (self.directory / 'proc_fields.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 8)

    def test_proc_missed_before_arming_has_no_new_window(self):
        root = self.fake_proc()
        with self.proc_context(root, lambda: 25_000_000_000, lambda _: None) as alarm:
            result = observer.run_proc(self.proc_task(), self.directory)
        self.assertEqual(result['status'], 'MISSED')
        alarm.assert_not_called()
        self.assertFalse((self.directory / 'proc_fields.jsonl').exists())

    def test_proc_rejects_wrong_job_or_oversized_budget(self):
        root = self.fake_proc()
        for mode in ('budget', 'job', 'parent'):
            with self.subTest(mode=mode), self.proc_context(root, lambda: 3_000_000_000, lambda _: None), \
                    patch.object(observer, 'read_identity') as identity:
                task = self.proc_task()
                if mode == 'budget':
                    task['sample_stop_ns'] += 1
                elif mode == 'job':
                    task['identity']['job_id'] = 'old'
                else:
                    task['parent_pid'] = 999
                result = observer.run_proc(task, self.directory)
                self.assertEqual(result['status'], 'INCOMPLETE')
                identity.assert_not_called()

    def test_old_pid_and_wrong_parent_rejected(self):
        expected = dict(pid=100, ppid=10, sid=100, start_ticks=123)
        for changed in (dict(expected, start_ticks=124), dict(expected, ppid=11), dict(expected, sid=1)):
            with self.subTest(changed=changed), patch.object(observer, 'read_identity', return_value=changed), \
                    self.assertRaises(ValueError):
                observer.check_target(expected, [0])

    def test_target_cpu_boundary_rejected(self):
        expected = dict(pid=100, ppid=10, sid=100, start_ticks=123)
        with patch.object(observer, 'read_identity', return_value=expected), \
                patch.object(observer.os, 'sched_getaffinity', create=True, return_value={99}), \
                self.assertRaises(ValueError):
            observer.check_target(expected, [0])

    def test_helper_binding_never_expands_inherited_authority(self):
        with patch.object(observer.os, 'sched_setaffinity', create=True) as bind, self.assertRaises(ValueError):
            observer.bind_helper([2], {0, 1})
        bind.assert_not_called()

    def test_helper_clock_is_absolute_and_missed_not_restarted(self):
        context = dict(case='watchdog')
        with patch.object(observer.time, 'monotonic_ns', return_value=25_000_000_000), \
                patch.object(observer.subprocess, 'Popen') as popen:
            helper = observer.ProcObserver(self.directory, context, [], 30_000_000_000, {})
            helper.start()
            self.assertEqual(helper.state['status'], 'MISSED')
            popen.assert_not_called()

    def test_nonblocking_timeout_and_cancel_do_not_wait(self):
        process = Mock(pid=123, returncode=None); process.poll.return_value = None
        spec = dict(self.spec, ready_token='nonce')
        with patch.object(observer.time, 'monotonic_ns', return_value=0), \
                patch.object(observer.subprocess, 'Popen', return_value=process), \
                patch.dict(os.environ, CCS_JOB_ID='synthetic'):
            helper = observer.ProcObserver(self.directory, spec, [Mock(pid=10), Mock(pid=11)], 30_000_000_000, os.environ.copy())
            helper.start()
            with patch.object(observer.time, 'monotonic_ns', return_value=27_000_000_000):
                helper.poll()
            process.kill.assert_called_once()
            process.wait.assert_not_called()
            helper.stop(); process.poll.return_value = -9
            receipt = helper.receipt()
            self.assertTrue(receipt['reaped'])
            self.assertEqual(receipt['status'], 'EXITED')
            process.wait.assert_not_called()

    def test_real_owned_helper_is_killed_and_reaped(self):
        real_popen = subprocess.Popen
        def hanging_child(*args, **kwargs):
            return real_popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'], **kwargs)
        spec = dict(self.spec, ready_token='nonce')
        with patch.object(observer, 'PROC_SECONDS', 0.12), \
                patch.object(observer.subprocess, 'Popen', side_effect=hanging_child):
            helper = observer.ProcObserver(self.directory, spec, [Mock(pid=10), Mock(pid=11)],
                time.monotonic_ns() + 5_080_000_000, os.environ.copy())
            helper.start()
            until = time.monotonic() + 2
            while helper.running and time.monotonic() < until:
                helper.poll(); time.sleep(0.01)
            helper.stop()
            self.assertTrue(helper.receipt()['reaped'])

    def test_helper_log_close_error_does_not_escape(self):
        helper = observer.ProcObserver(self.directory, self.spec, [], 30_000_000_000, {})
        helper.log = Mock(); helper.log.close.side_effect = OSError('log close failed')
        receipt = helper.receipt()
        self.assertTrue(receipt['reaped'])
        self.assertIn('log_close_error', receipt)

    @contextlib.contextmanager
    def integration_worker(self, case):
        spec = dict(self.spec, case=case, pg_timeout=5,
                    allocation=dict(self.spec['allocation'], job_id='synthetic'))
        probe.write_json(self.directory / 'manifest.json', spec)
        with fake_worker() as (_, dist, _), \
                patch.dict(os.environ, S07_CASE_DEADLINE_NS=str(time.monotonic_ns() + 30_000_000_000)), \
                patch.object(probe, 'await_peer_ready'), \
                patch.object(observer, 'StackDump') as dump_class, \
                patch.object(observer, 'installed_sources', return_value=dict(status='RECORDED')) as sources:
            yield dist, dump_class, sources

    def test_watchdog_init_error_cancels_in_finally(self):
        with self.integration_worker('watchdog') as (dist, dump_class, sources):
            dist.init_process_group = Mock(side_effect=RuntimeError('synthetic init failure'))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
            dump_class.return_value.arm.assert_called_once()
            dump_class.return_value.cancel.assert_called_once_with('finally')
            sources.assert_called_once_with(self.directory, 0)

    def test_watchdog_init_return_cancels_before_next_stage(self):
        with self.integration_worker('watchdog') as (dist, dump_class, _):
            dist.init_process_group = Mock()
            def after_init():
                dump_class.return_value.cancel.assert_called_once_with('init_end')
                raise RuntimeError('synthetic next-stage boundary')
            dist.get_backend = after_init
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
            self.assertEqual([call.args for call in dump_class.return_value.cancel.call_args_list],
                             [('init_end',), ('finally',)])

    def test_normal_worker_never_starts_stack_observers(self):
        with self.integration_worker('normal') as (dist, dump_class, sources):
            dist.init_process_group = Mock(side_effect=RuntimeError('synthetic boundary'))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
            dump_class.assert_not_called(); sources.assert_not_called()

    def test_parent_deadline_cleans_workers_without_helper_wait(self):
        helper = Mock()
        helper.running = True
        helper.stop.side_effect = lambda: setattr(helper, 'running', False)
        helper.state = dict(status='STARTED', helper_pid=999)
        helper.receipt.return_value = dict(reaped=True)
        with patch.object(observer, 'ProcObserver', return_value=helper):
            state = probe.supervise([[sys.executable, '-B', '-c', 'import time; time.sleep(60)']] * 2,
                self.directory, 0.15, os.environ.copy(), stack_context=self.spec)
        self.assertEqual(state['reason'], 'deadline')
        self.assertTrue(state['all_reaped'])
        self.assertLess(state['wall_seconds'], 2)
        helper.stop.assert_called_once(); helper.wait.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
