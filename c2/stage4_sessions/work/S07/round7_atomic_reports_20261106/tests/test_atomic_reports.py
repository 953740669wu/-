"""Owned, deterministic publication faults; no Torch or communication."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'candidate'))
import comm_probe as probe
import run_checks


CHILD = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import comm_probe as probe
mode, phase, folder = sys.argv[2:]
folder = Path(folder)
target = folder / 'rank0.json'
real_open = Path.open

def pause(name):
    (folder / 'paused.json').write_text(json.dumps(dict(path=str(name))), encoding='utf-8')
    while True:
        time.sleep(.01)

class Gate:
    def __init__(self, stream):
        self.stream = stream
    def __enter__(self):
        self.stream.__enter__()
        return self
    def __exit__(self, *args):
        return self.stream.__exit__(*args)
    def __getattr__(self, name):
        return getattr(self.stream, name)
    def write(self, text):
        if phase == 'partial':
            self.stream.write(text[:len(text)//2])
            self.stream.flush()
        pause(self.stream.name)

if mode == 'old':
    def opened(path, mode='r', *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        return Gate(stream) if path == target and mode == 'w' else stream
    Path.open = opened
    probe.write_json(target, dict(stage='broadcast', error='new peer reset'))
else:
    if phase == 'commit':
        probe.os.replace = lambda source, destination: pause(source)
    else:
        real_temp = probe.tempfile.NamedTemporaryFile
        probe.tempfile.NamedTemporaryFile = lambda *a, **k: Gate(real_temp(*a, **k))
    probe.write_rank_report(target, dict(stage='broadcast', error='new peer reset'))
'''


class AtomicReportChecks(unittest.TestCase):
    def setUp(self):
        (BASE / 'evidence').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='atomic_test_', dir=BASE / 'evidence')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.target = self.directory / 'rank0.json'
        self.old = dict(status='FAIL', rank=0, stage='broadcast', checkpoints=[{'stage': 'broadcast'}])
        probe.write_json(self.target, self.old)
        self.old_bytes = self.target.read_bytes()

    def assert_preserved(self):
        self.assertEqual(self.target.read_bytes(), self.old_bytes)
        self.assertEqual(json.loads(self.target.read_text()), self.old)

    def assert_no_temp(self):
        self.assertEqual(list(self.directory.glob('.rank0.json.*.tmp')), [])

    def seed_crash(self):
        probe.write_json(self.directory / 'rank1.json', dict(stage='injected_crash'))
        probe.write_json(self.directory / 'summary.json', dict(status='FAIL', supervisor=dict(
            all_reaped=True, pids=[101, 102], reason='child_failed', exit_codes=[-15, 17])))

    def interrupted(self, mode, phase, prior=True):
        if not prior:
            self.target.unlink()
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', CHILD,
                                  str(BASE / 'candidate'), mode, phase, str(self.directory)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            marker = self.directory / 'paused.json'
            deadline = time.monotonic() + 5
            while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists(), 'owned child did not reach deterministic fault point')
            # The marker is closed by the child before it waits; tolerate only that short write race.
            while True:
                try:
                    paused = json.loads(marker.read_text())
                    break
                except json.JSONDecodeError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.01)
            child.terminate()
            child.communicate(timeout=3)
            self.assertIsNotNone(child.returncode)
            self.assertNotEqual(child.returncode, 0)
            return Path(paused['path'])
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)

    def test_first_publication_matches_original_serialization(self):
        expected = self.directory / 'expected.json'
        data = dict(rank=0, stage='finished', values=[1, -2, .5], text='核')
        probe.write_json(expected, data)
        self.target.unlink()
        probe.write_rank_report(self.target, data)
        self.assertEqual(self.target.read_bytes(), expected.read_bytes())
        self.assert_no_temp()

    def test_successful_replacement(self):
        probe.write_rank_report(self.target, dict(self.old, error='peer reset'))
        self.assertEqual(json.loads(self.target.read_text()), dict(self.old, error='peer reset'))
        self.assert_no_temp()

    def test_serialization_failures_preserve_previous(self):
        for bad in (float('nan'), object()):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises((ValueError, TypeError)):
                    probe.write_rank_report(self.target, dict(error=bad))
                self.assert_preserved()
                self.assert_no_temp()

    def stream_fault(self, operation):
        real = probe.tempfile.NamedTemporaryFile

        def faulty(*args, **kwargs):
            stream = real(*args, **kwargs)
            setattr(stream, operation, lambda *a: (_ for _ in ()).throw(OSError(operation)))
            return stream

        with patch.object(probe.tempfile, 'NamedTemporaryFile', faulty):
            with self.assertRaises(OSError):
                probe.write_rank_report(self.target, dict(stage='new'))
        self.assert_preserved()
        self.assert_no_temp()

    def test_write_failure_preserves_previous(self):
        self.stream_fault('write')

    def test_flush_failure_preserves_previous(self):
        self.stream_fault('flush')

    def test_fsync_failure_preserves_previous(self):
        with patch.object(probe.os, 'fsync', side_effect=OSError('fsync')):
            with self.assertRaises(OSError):
                probe.write_rank_report(self.target, dict(stage='new'))
        self.assert_preserved()
        self.assert_no_temp()

    def test_replace_failure_preserves_previous(self):
        with patch.object(probe.os, 'replace', side_effect=OSError('replace')):
            with self.assertRaises(OSError):
                probe.write_rank_report(self.target, dict(stage='new'))
        self.assert_preserved()
        self.assert_no_temp()

    def test_same_directory_exclusive_temp_and_closed_before_commit(self):
        real = probe.os.replace
        seen = []

        def replace(source, target):
            source = Path(source)
            self.assertEqual(source.parent, self.target.parent)
            self.assertTrue(source.name.startswith('.rank0.json.'))
            self.assertTrue(source.name.endswith('.tmp'))
            self.assert_preserved()
            self.assertEqual(json.loads(source.read_text()), dict(stage='new'))
            with self.assertRaises(FileExistsError):
                source.open('x')
            seen.append(source)
            real(source, target)

        with patch.object(probe.os, 'replace', replace):
            probe.write_rank_report(self.target, dict(stage='new'))
        self.assertEqual(len(seen), 1)
        self.assert_no_temp()

    def test_exception_cleanup_only_removes_owned_temp(self):
        unrelated = self.directory / '.rank0.json.other.tmp'
        unrelated.write_bytes(b'other owner')
        with patch.object(probe.os, 'replace', side_effect=OSError('replace')):
            with self.assertRaises(OSError):
                probe.write_rank_report(self.target, dict(stage='new'))
        self.assertEqual(unrelated.read_bytes(), b'other owner')
        self.assertEqual(list(self.directory.glob('.rank0.json.*.tmp')), [unrelated])
        self.assert_preserved()

    def test_old_interrupted_write_truncates_previous_to_empty(self):
        self.interrupted('old', 'zero')
        self.assertEqual(self.target.read_bytes(), b'')

    def test_old_interrupted_write_leaves_partial_json(self):
        self.interrupted('old', 'partial')
        self.assertTrue(self.target.stat().st_size > 0)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.target.read_text())

    def test_atomic_interrupted_write_preserves_previous_checkpoint(self):
        remnant = self.interrupted('atomic', 'zero')
        self.assert_preserved()
        self.assertEqual(remnant.parent, self.directory)
        self.assertEqual(remnant.read_bytes(), b'')
        self.seed_crash()
        self.assertEqual(run_checks.check_case('crash', 1, self.directory)['expected_behavior'], 'PASS')
        self.assertNotIn('error', json.loads(self.target.read_text()))

    def test_atomic_interrupted_partial_write_preserves_previous(self):
        remnant = self.interrupted('atomic', 'partial')
        self.assert_preserved()
        self.assertTrue(remnant.stat().st_size > 0)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(remnant.read_text())

    def test_atomic_interrupted_before_replace_preserves_previous(self):
        remnant = self.interrupted('atomic', 'commit')
        self.assert_preserved()
        self.assertEqual(json.loads(remnant.read_text())['error'], 'new peer reset')

    def test_uncommitted_first_publication_still_rejected(self):
        remnant = self.interrupted('atomic', 'partial', prior=False)
        self.assertTrue(remnant.is_file())
        self.assertFalse(self.target.exists())
        self.seed_crash()
        with self.assertRaises(FileNotFoundError):
            run_checks.check_case('crash', 1, self.directory)

    def test_original_reader_rejects_missing_empty_partial_for_both_ranks(self):
        self.seed_crash()
        for rank in range(2):
            for bad in (None, b'', b'{"stage":'):
                with self.subTest(rank=rank, bad=bad):
                    path = self.directory / f'rank{rank}.json'
                    before = path.read_bytes()
                    path.unlink()
                    if bad is not None:
                        path.write_bytes(bad)
                    with self.assertRaises((FileNotFoundError, json.JSONDecodeError)):
                        run_checks.check_case('crash', 1, self.directory)
                    path.write_bytes(before)

    def test_readiness_still_refuses_existing_publication(self):
        ready = self.directory / 'ready_rank0.json'
        probe.publish_json(ready, dict(rank=0, pid=os.getpid()))
        before = ready.read_bytes()
        with self.assertRaises(ValueError):
            probe.publish_json(ready, dict(rank=1))
        self.assertEqual(ready.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
