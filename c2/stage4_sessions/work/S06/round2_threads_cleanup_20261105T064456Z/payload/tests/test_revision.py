"""Targeted R2 checks; Linux process-group integration remains explicitly conditional."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import probe
import run_probe
from test_probe import fixture_dir

SELECTED = list(range(36))


def snapshot(mask=None, complete=True):
    return dict(complete=complete, threads=[dict(tid=1, affinity=SELECTED if mask is None else mask)],
                vanished=[], errors=[])


def fake_torch(intraop=36):
    return SimpleNamespace(get_num_threads=lambda: intraop, get_num_interop_threads=lambda: 2,
                           __config__=SimpleNamespace(parallel_info=lambda: 'observed parallel info'))


class ThreadChecks(unittest.TestCase):
    def observe(self, torch, snap, environment=None, selected=None):
        report = {}
        with mock.patch.dict(os.environ, environment or probe.CPU36.ENVIRONMENT, clear=True), \
                mock.patch.object(probe.CPU36, 'snapshot_threads', return_value=snap):
            probe.thread_checkpoint(torch, report, 'after_framework', SELECTED if selected is None else selected)
        return report

    def test_actual_36_passes_without_setter(self):
        report = self.observe(fake_torch(), snapshot())
        self.assertEqual(report['thread_checkpoints'][0]['torch_intraop'], 36)
        self.assertEqual(report['thread_checkpoints'][0]['validation'], 'PASS')

    def test_actual_35_rejected_despite_env_36(self):
        with self.assertRaisesRegex(ValueError, 'actual.*36'):
            self.observe(fake_torch(35), snapshot())

    def test_openblas_36_rejected(self):
        env = dict(probe.CPU36.ENVIRONMENT, OPENBLAS_NUM_THREADS='36')
        with self.assertRaisesRegex(ValueError, 'environment'):
            self.observe(fake_torch(), snapshot(), env)

    def test_one_thread_pinned_inside_boundary_is_valid(self):
        self.observe(fake_torch(), snapshot([17]))

    def test_any_tid_outside_selected_rejected(self):
        snap = snapshot()
        snap['threads'].append(dict(tid=2, affinity=[36]))
        with self.assertRaisesRegex(ValueError, 'outside selected36'):
            self.observe(fake_torch(), snap)

    def test_incomplete_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.observe(fake_torch(), snapshot(complete=False))

    def test_duplicate_selected_rejected(self):
        with self.assertRaisesRegex(ValueError, 'selected36'):
            self.observe(fake_torch(), snapshot(), selected=[0] * 36)

    def test_failed_observation_retained(self):
        report = {}
        with mock.patch.dict(os.environ, probe.CPU36.ENVIRONMENT, clear=True), \
                mock.patch.object(probe.CPU36, 'snapshot_threads', return_value=snapshot([999])):
            with self.assertRaises(ValueError):
                probe.thread_checkpoint(fake_torch(), report, 'before_exit', SELECTED)
        self.assertEqual(report['thread_checkpoints'][0]['snapshot']['threads'][0]['affinity'], [999])
        self.assertEqual(report['thread_checkpoints'][0]['validation'], 'FAILED')


class CleanupChecks(unittest.TestCase):
    def exercise(self, error, cleanup_error=None):
        child = mock.Mock(pid=43210, returncode=None)
        child.poll.return_value = None
        child.wait.side_effect = [error, cleanup_error or 0, 0]
        with fixture_dir() as td, mock.patch.object(run_probe.subprocess, 'Popen', return_value=child), \
                mock.patch.object(run_probe.signal, 'signal') as handlers, \
                mock.patch.object(run_probe.os, 'killpg', create=True):
            result = run_probe.run_child(['owned-probe'], Path(td), 0.1)
            receipt = json.loads((Path(td) / 'execution.json').read_text())
        self.assertEqual(receipt['status'], result['status'])
        for call in child.wait.call_args_list:
            self.assertGreater(call.kwargs['timeout'], 0)
        self.assertEqual(result['cleanup']['status'], 'REAPED')
        return result, child, handlers

    def test_timeout_bounded_cleanup(self):
        result, _, _ = self.exercise(subprocess.TimeoutExpired('owned-probe', 0.1))
        self.assertEqual(result['status'], 'TIMEOUT')
        self.assertEqual(result['exit_code'], 124)

    def test_keyboard_interrupt_bounded_cleanup(self):
        result, _, _ = self.exercise(KeyboardInterrupt())
        self.assertEqual(result['status'], 'INTERRUPTED')
        self.assertEqual(result['exit_code'], 130)

    def test_term_bounded_cleanup(self):
        result, _, _ = self.exercise(run_probe.ParentInterrupted(signal.SIGTERM))
        self.assertEqual(result['status'], 'INTERRUPTED')
        self.assertEqual(result['exit_code'], 143)

    def test_wait_exception_bounded_cleanup(self):
        result, _, _ = self.exercise(RuntimeError('injected wait exception'))
        self.assertEqual(result['status'], 'ERROR')
        self.assertIn('injected wait exception', result['exception'])

    def test_term_handler_routes_to_cleanup(self):
        with self.assertRaises(run_probe.ParentInterrupted) as ctx:
            run_probe.parent_signal(signal.SIGTERM, None)
        self.assertEqual(ctx.exception.signum, signal.SIGTERM)

    def test_term_during_spawn_is_deferred_until_handle_exists(self):
        child = mock.Mock(pid=43210, returncode=None)
        child.poll.return_value = None
        child.wait.return_value = 0
        installed = {}

        def register(sig, handler):
            installed[sig] = handler
            return signal.SIG_DFL

        def spawn(*args, **kwargs):
            self.assertEqual(kwargs['start_new_session'], os.name == 'posix')
            installed[signal.SIGTERM](signal.SIGTERM, None)
            return child

        with fixture_dir() as td, mock.patch.object(run_probe.subprocess, 'Popen', side_effect=spawn), \
                mock.patch.object(run_probe.signal, 'signal', side_effect=register), \
                mock.patch.object(run_probe.os, 'killpg', create=True):
            result = run_probe.run_child(['owned-probe'], Path(td), 0.1)
        self.assertEqual(result['status'], 'INTERRUPTED')
        self.assertEqual(result['cleanup']['status'], 'REAPED')
        self.assertEqual(installed[signal.SIGTERM], signal.SIG_DFL)
        self.assertEqual(installed[signal.SIGINT], signal.SIG_DFL)

    def test_posix_cleanup_targets_only_owned_group(self):
        child = mock.Mock(pid=43210, returncode=None)
        child.wait.return_value = 0
        with mock.patch.object(run_probe.os, 'name', 'posix'), \
                mock.patch.object(run_probe.signal, 'SIGKILL', 9, create=True), \
                mock.patch.object(run_probe.os, 'killpg', create=True) as killpg:
            receipt = run_probe.cleanup_child(child)
        self.assertEqual(killpg.call_args_list[:2], [mock.call(43210, signal.SIGTERM),
                                                    mock.call(43210, 9)])
        self.assertEqual(receipt['scope'], 'owned_process_group')
        self.assertTrue(receipt['direct_child_reaped'])

    def test_cleanup_failure_cannot_pass(self):
        child = mock.Mock(pid=43210, returncode=None)
        child.poll.return_value = None
        child.wait.side_effect = [0, subprocess.TimeoutExpired('owned-probe', 1),
                                  subprocess.TimeoutExpired('owned-probe', 1)]
        with fixture_dir() as td, mock.patch.object(run_probe.subprocess, 'Popen', return_value=child), \
                mock.patch.object(run_probe.signal, 'signal'), \
                mock.patch.object(run_probe.os, 'killpg', create=True):
            result = run_probe.run_child(['owned-probe'], Path(td), 0.1)
        self.assertEqual(result['status'], 'CLEANUP_FAILED')
        self.assertNotEqual(result['exit_code'], 0)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux process groups NOT_RUN on this host')
class LinuxGroupChecks(unittest.TestCase):
    def test_linux_child_does_not_inherit_blocked_term_or_int(self):
        code = ('import signal; mask=signal.pthread_sigmask(signal.SIG_BLOCK,set()); '
                'assert not {signal.SIGTERM,signal.SIGINT} & mask, mask')
        with fixture_dir() as td:
            result = run_probe.run_child([sys.executable, '-c', code], Path(td), 5)
        self.assertEqual(result['status'], 'PASS')

    def exercise(self, sig):
        with fixture_dir() as td:
            folder = Path(td)
            pidfile = folder / 'owned_pids.json'
            child_code = ('import json,os,pathlib,signal,subprocess,sys,time; '
                          'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                          'p=subprocess.Popen([sys.executable,"-c",'
                          '"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"]); '
                          'pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),p.pid])); time.sleep(30)')
            driver = folder / 'driver.py'
            driver.write_text('import json,pathlib,sys\nsys.path.insert(0,sys.argv[1])\nimport run_probe\n'
                              'r=run_probe.run_child([sys.executable,"-c",sys.argv[3],sys.argv[4]],'
                              'pathlib.Path(sys.argv[2]),10)\n'
                              'pathlib.Path(sys.argv[2],"driver_result.json").write_text(json.dumps(r))\n'
                              'sys.exit(r["exit_code"])\n')
            sentinel = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
            parent = subprocess.Popen([sys.executable, '-B', str(driver), str(ROOT / 'candidate'), td,
                                       child_code, str(pidfile)])
            owned = []
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pidfile.exists())
                owned = json.loads(pidfile.read_text())
                parent.send_signal(sig)
                self.assertEqual(parent.wait(timeout=5), 128 + sig)
                result = json.loads((folder / 'driver_result.json').read_text())
                self.assertEqual(result['cleanup']['status'], 'REAPED')
                self.assertIsNone(sentinel.poll(), 'unrelated session must survive')
                for pid in owned:
                    path = Path('/proc') / str(pid) / 'stat'
                    deadline = time.monotonic() + 2
                    while path.exists():
                        try:
                            state = path.read_text().split(')')[-1].strip().split()[0]
                        except FileNotFoundError:
                            break
                        if state in ('Z', 'X'):
                            break
                        self.assertLess(time.monotonic(), deadline, 'live owned descendant remains')
                        time.sleep(0.02)
            finally:
                if parent.poll() is None:
                    parent.kill()
                parent.wait(timeout=2)
                if owned:
                    try:
                        os.killpg(owned[0], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                sentinel.terminate()
                sentinel.wait(timeout=2)

    def test_linux_term_cleans_ignoring_descendants_and_preserves_other_session(self):
        self.exercise(signal.SIGTERM)

    def test_linux_sigint_cleans_ignoring_descendants_and_preserves_other_session(self):
        self.exercise(signal.SIGINT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
