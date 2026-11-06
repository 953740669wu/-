"""Only owned short subprocesses; no fault injection in a cluster job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import runtime_guard as guard
import supervisor


class LifecycleChecks(unittest.TestCase):
    def test_current_job_missing_or_stale_rejected(self):
        for current, configured in ((None, 'old'), ('', 'old'), ('new', 'old')):
            with patch.dict(os.environ, {}, clear=True):
                if current is not None:
                    os.environ['CCS_JOB_ID'] = current
                with self.assertRaises(ValueError):
                    guard.validate_current_job(configured)
        with patch.dict(os.environ, {'CCS_JOB_ID': 'new'}):
            guard.validate_current_job('new')

    def test_absolute_application_deadline_never_restarts(self):
        started = time.monotonic_ns() - 841 * 10**9
        with self.assertRaises(TimeoutError):
            supervisor.check_deadline(started + 840 * 10**9)

    def test_one_rank_failure_stops_and_reaps_owned_sibling(self):
        (ROOT / 'evidence').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            directory = Path(folder)
            commands = [[sys.executable, '-I', '-B', '-c', 'raise SystemExit(17)'],
                        [sys.executable, '-I', '-B', '-c', 'import time;time.sleep(10)']]
            start = time.monotonic_ns()
            value = supervisor.supervise(commands, directory, start + 5 * 10**9,
                                         start + 8 * 10**9, os.environ.copy())
            self.assertEqual(value['reason'], 'child_failed')
            self.assertEqual(value['exit_codes'][0], 17)
            self.assertTrue(value['all_reaped'])
            self.assertLess(time.monotonic_ns() - start, 8 * 10**9)
            self.assertEqual(len(value['pids']), 2)

    def test_deadline_reaps_owned_children(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            start = time.monotonic_ns()
            command = [sys.executable, '-I', '-B', '-c', 'import time;time.sleep(10)']
            value = supervisor.supervise([command, command], Path(folder), start + 300_000_000,
                                         start + 3 * 10**9, os.environ.copy())
            self.assertEqual(value['reason'], 'deadline')
            self.assertTrue(value['all_reaped'])

    def test_atomic_report_keeps_previous_on_replace_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            target = Path(folder) / 'rank0.json'
            guard.write_rank_report(target, dict(stage='checkpoint'))
            before = target.read_bytes()
            with patch.object(guard.os, 'replace', side_effect=OSError('denied')):
                with self.assertRaises(OSError):
                    guard.write_rank_report(target, dict(stage='error'))
            self.assertEqual(target.read_bytes(), before)

    @unittest.skipUnless(os.name == 'posix', 'NOT_RUN: Linux owned-session descendant check')
    def test_owned_descendant_session_is_stopped_on_rank_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            directory = Path(folder)
            # The failing sibling waits for a bounded owned marker, rather than a timing guess.
            failed_code = ('import sys,time;from pathlib import Path\n'
                           'stop=time.monotonic()+3\n'
                           'while not Path(sys.argv[1]).exists() and time.monotonic()<stop:time.sleep(.01)\n'
                           'raise SystemExit(17)')
            failed = [sys.executable, '-I', '-B', '-c', failed_code, str(directory/'descendant.pid')]
            child_code = ('import subprocess,sys,time;from pathlib import Path;'
                          'p=subprocess.Popen([sys.executable,"-I","-B","-c",'
                          '"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(10)"]);'
                          'Path(sys.argv[1]).write_text(str(p.pid));time.sleep(10)')
            child = [sys.executable, '-I', '-B', '-c', child_code, str(directory / 'descendant.pid')]
            start = time.monotonic_ns()
            value = supervisor.supervise([failed, child], directory, start + 5*10**9,
                                         start + 8*10**9, os.environ.copy())
            self.assertEqual(value['reason'], 'child_failed')
            self.assertTrue(value['all_reaped'])
            owned_pid = int((directory / 'descendant.pid').read_text())
            stopped = False
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    stat = Path(f'/proc/{owned_pid}/stat').read_text()
                    stopped = stat[stat.rfind(')')+2:].split()[0] == 'Z'
                except FileNotFoundError:
                    stopped = True
                if stopped:
                    break
                time.sleep(.01)
            self.assertTrue(stopped, 'owned descendant remains alive after session cleanup')


if __name__ == '__main__':
    unittest.main(verbosity=2)
