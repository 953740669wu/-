"""Trace-gap checks with standard-library children and fake framework modules."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'candidate'))
import comm_probe as probe


def events(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def fake_framework():
    torch = types.ModuleType('torch')
    dist = types.ModuleType('torch.distributed')
    torch.distributed = dist
    torch.__version__, torch.__file__ = 'fake', __file__
    torch.__config__ = types.SimpleNamespace(show=lambda: 'fake build')
    torch.get_num_threads = lambda: 36
    torch.get_num_interop_threads = lambda: 1
    dist.is_available = dist.is_gloo_available = lambda: True
    dist.is_mpi_available = dist.is_nccl_available = lambda: False
    return torch, dist


class DiagnosticChecks(unittest.TestCase):
    def test_events_have_wall_monotonic_and_fsync(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                patch.object(probe.os, 'fsync', wraps=os.fsync) as fsync:
            path = Path(folder) / 'events.jsonl'
            self.assertTrue(probe.record_event(path, 'begin', rank=0))
            self.assertTrue(probe.record_event(path, 'end', rank=0))
            rows = events(path)
            self.assertEqual([row['event'] for row in rows], ['begin', 'end'])
            self.assertEqual(fsync.call_count, 2)
            self.assertLessEqual(rows[0]['monotonic_ns'], rows[1]['monotonic_ns'])
            self.assertTrue(all(type(row['time_ns']) is int and row['pid'] == os.getpid() for row in rows))

    def test_import_entry_is_visible_without_import_exit(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                patch.dict(sys.modules, {'torch': None}):
            path = Path(folder) / 'events.jsonl'
            self.assertEqual(probe.backend_info(path)['status'], 'UNAVAILABLE')
            names = [row['event'] for row in events(path)]
            self.assertIn('torch_import_begin', names)
            self.assertNotIn('torch_import_end', names)
            self.assertEqual(names[-1], 'backend_info_error')

    def test_hash_entry_is_distinct_from_framework_import(self):
        torch, dist = fake_framework()
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            path = Path(folder) / 'events.jsonl'
            with patch.dict(sys.modules, {'torch': torch, 'torch.distributed': dist}), \
                    patch.object(probe.sys, 'platform', 'linux'), \
                    patch.object(Path, 'read_text', return_value='000-fff r-x /fake/libtorch_cpu.so\n'), \
                    patch.object(Path, 'is_file', return_value=True), \
                    patch.object(probe.cpu36, 'sha', side_effect=OSError('hash sentinel')):
                self.assertEqual(probe.backend_info(path)['status'], 'UNAVAILABLE')
            names = [row['event'] for row in events(path)]
            self.assertIn('torch_import_end', names)
            self.assertIn('distributed_import_end', names)
            self.assertIn('library_sha_begin', names)
            self.assertNotIn('library_sha_end', names)
            self.assertEqual(names[-1], 'backend_info_error')

    def test_init_timeout_keeps_original_failure_and_records_entry(self):
        torch, dist = fake_framework()
        dist.init_process_group = unittest.mock.Mock(side_effect=RuntimeError('Wait timeout'))
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                patch.dict(sys.modules, {'torch': torch, 'torch.distributed': dist}), \
                patch.dict(os.environ, dict(probe.ENVIRONMENT, CCS_JOB_ID='synthetic')), \
                patch.object(probe.cpu36, 'validate_receipt'), \
                patch.object(probe.cpu36, 'snapshot_threads', return_value={}), \
                patch.object(probe.cpu36, 'validate_snapshot'), \
                patch.object(probe.os, 'sched_getaffinity', create=True, return_value={0}), \
                patch.object(probe.os, 'sched_setaffinity', create=True), \
                patch.object(probe, 'backend_info', return_value=dict(status='AVAILABLE_BUILT_NOT_COMM_TESTED')):
            directory = Path(folder)
            probe.write_json(directory / 'manifest.json', dict(job_id='synthetic', run_id='normal',
                pg_timeout=5, allocation=dict(job_id='synthetic', ranks=[dict(selected=[0])] * 2)))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(directory, 1), 1)
            report = json.loads((directory / 'rank1.json').read_text(encoding='utf-8'))
            self.assertEqual(report['stage'], 'init_process_group')
            self.assertEqual(report['error'], 'RuntimeError: Wait timeout')
            rows = events(directory / 'rank1.events.jsonl')
            names = [row['event'] for row in rows]
            self.assertIn('init_process_group_begin', names)
            self.assertNotIn('init_process_group_end', names)
            self.assertEqual(names[-1], 'worker_error')
            self.assertEqual(dist.init_process_group.call_args.kwargs['timeout'].total_seconds(), 5)

    def test_supervisor_records_spawn_failure_cleanup_and_reap(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            directory = Path(folder)
            state = probe.supervise([[sys.executable, '-c', 'raise SystemExit(17)'],
                                     [sys.executable, '-c', 'import time; time.sleep(60)']],
                                    directory, 2, os.environ.copy())
            rows = events(directory / 'supervisor.events.jsonl')
            self.assertEqual(state['reason'], 'child_failed')
            self.assertTrue(state['all_reaped'])
            self.assertEqual([row['child_pid'] for row in rows if row['event'] == 'spawned'], state['pids'])
            cleanup = next(row for row in rows if row['event'] == 'cleanup_begin')
            self.assertEqual(cleanup['reason'], 'child_failed')
            self.assertEqual(sum(row['event'] == 'child_reaped' for row in rows), 2)
            self.assertEqual(rows[-1]['event'], 'supervisor_end')
            self.assertTrue(any(row['event'] in ('signal_sent', 'child_terminate') for row in rows))

    def test_trace_io_failure_does_not_skip_cleanup(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                patch.object(probe.os, 'fsync', side_effect=OSError('fsync sentinel')), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            state = probe.supervise([[sys.executable, '-c', 'raise SystemExit(17)'],
                                     [sys.executable, '-c', 'import time; time.sleep(60)']],
                                    Path(folder), 2, os.environ.copy())
            self.assertEqual(state['reason'], 'child_failed')
            self.assertTrue(state['all_reaped'])
            self.assertIn('TRACE_WRITE_ERROR', stderr.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
