"""Readiness protocol only: controlled clocks, fake framework and stdlib children."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'candidate'))
import comm_probe as probe
from test_diagnostics import fake_framework


class Clock:
    def __init__(self, now=0, on_sleep=None):
        self.now = now
        self.on_sleep = on_sleep

    def sleep(self, seconds):
        self.now += int(seconds * 1e9)
        if self.on_sleep:
            self.on_sleep(self.now)


@contextlib.contextmanager
def fake_worker():
    torch, dist = fake_framework()
    with patch.dict(sys.modules, {'torch': torch, 'torch.distributed': dist}), \
            patch.dict(os.environ, dict(probe.ENVIRONMENT, CCS_JOB_ID='synthetic')), \
            patch.object(probe.cpu36, 'validate_receipt'), \
            patch.object(probe.cpu36, 'snapshot_threads', return_value={}), \
            patch.object(probe.cpu36, 'validate_snapshot') as validate, \
            patch.object(probe.os, 'sched_getaffinity', create=True, return_value={0}), \
            patch.object(probe.os, 'sched_setaffinity', create=True), \
            patch.object(probe, 'backend_info', return_value=dict(status='AVAILABLE_BUILT_NOT_COMM_TESTED')):
        yield torch, dist, validate


class ReadinessChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=BASE / 'evidence')
        self.directory = Path(self.temp.name).resolve()
        assert self.directory.is_relative_to(BASE / 'evidence')
        self.addCleanup(self.temp.cleanup)
        self.spec = dict(run_id='normal', job_id='synthetic', ready_token='this-run-token')
        self.stop = 30_000_000_000
        self.pids = [os.getpid(), os.getpid() + 10000]

    def context(self, directory=None):
        directory = directory or self.directory
        value = dict(self.spec, pids=self.pids, deadline_ns=self.stop)
        probe.write_json(directory / 'participants.json', value)
        return value

    def peer(self, directory=None, **changes):
        directory = directory or self.directory
        value = dict(self.spec, rank=1, pid=self.pids[1])
        value.update(changes)
        probe.write_json(directory / 'ready_rank1.json', value)

    def test_matching_atomic_ready(self):
        self.context(); self.peer()
        with patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                patch.object(probe.time, 'monotonic_ns', return_value=0):
            probe.await_peer_ready(self.directory, self.spec, 0, None)
        own = json.loads((self.directory / 'ready_rank0.json').read_text())
        self.assertEqual(own, dict(self.spec, rank=0, pid=os.getpid()))
        self.assertFalse((self.directory / 'ready_rank0.json.tmp').exists())

    def test_preparation_stagger_over_five_seconds_before_init(self):
        self.context()
        clock = Clock()

        def delayed_peer(now):
            if now >= 6_250_000_000 and not (self.directory / 'ready_rank1.json').exists():
                probe.publish_json(self.directory / 'ready_rank1.json', dict(self.spec, rank=1, pid=self.pids[1]))

        clock.on_sleep = delayed_peer
        spec = dict(self.spec, pg_timeout=5, allocation=dict(job_id='synthetic', ranks=[dict(selected=[0])] * 2))
        probe.write_json(self.directory / 'manifest.json', spec)
        called = []
        with fake_worker() as (_, dist, validate), \
                patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                patch.object(probe.time, 'monotonic_ns', side_effect=lambda: clock.now), \
                patch.object(probe.time, 'sleep', side_effect=clock.sleep):
            def initialize(*args, **kwargs):
                self.assertGreaterEqual(clock.now, 6_250_000_000)
                self.assertTrue((self.directory / 'ready_rank0.json').exists())
                self.assertTrue((self.directory / 'ready_rank1.json').exists())
                self.assertGreaterEqual(validate.call_count, 2)
                self.assertEqual(kwargs['timeout'].total_seconds(), 5)
                called.append(clock.now)
                raise RuntimeError('fake init boundary')

            dist.init_process_group = Mock(side_effect=initialize)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
        self.assertEqual(len(called), 1)
        rows = [json.loads(line) for line in (self.directory / 'rank0.events.jsonl').read_text().splitlines()]
        names = [row['event'] for row in rows]
        self.assertLess(names.index('preparation_complete'), names.index('ready_published'))
        self.assertLess(names.index('both_ready'), names.index('init_process_group_begin'))

    def test_wrong_or_partial_peer_ready_rejected(self):
        for index, changes in enumerate([dict(run_id='old'), dict(job_id='old'),
                dict(ready_token='old'), dict(rank=0), dict(rank=True), dict(pid=self.pids[1] + 1),
                dict(pid=float(self.pids[1])), None]):
            with self.subTest(changes=changes):
                directory = self.directory / str(index); directory.mkdir()
                self.context(directory)
                if changes is None:
                    (directory / 'ready_rank1.json').write_text('{"run_id":', encoding='utf-8')
                else:
                    self.peer(directory, **changes)
                with patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                        patch.object(probe.time, 'monotonic_ns', return_value=0), \
                        self.assertRaises(ValueError):
                    probe.await_peer_ready(directory, self.spec, 0, None)

    def test_missing_peer_uses_remaining_case_budget(self):
        self.context()
        clock = Clock(now=29_000_000_000)
        with patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                patch.object(probe.time, 'monotonic_ns', side_effect=lambda: clock.now), \
                patch.object(probe.time, 'sleep', side_effect=clock.sleep), \
                self.assertRaises(TimeoutError):
            probe.await_peer_ready(self.directory, self.spec, 0, None)
        self.assertLessEqual(clock.now, self.stop + 50_000_000)

    def test_missing_participant_context_times_out_without_own_ready(self):
        clock = Clock(now=29_000_000_000)
        with patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                patch.object(probe.time, 'monotonic_ns', side_effect=lambda: clock.now), \
                patch.object(probe.time, 'sleep', side_effect=clock.sleep), \
                self.assertRaises(TimeoutError):
            probe.await_peer_ready(self.directory, self.spec, 0, None)
        self.assertFalse((self.directory / 'ready_rank0.json').exists())

    def test_invalid_participant_context_rejected(self):
        for index, changes in enumerate([dict(job_id='old'), dict(run_id='old'), dict(ready_token='old'),
                dict(pids=[self.pids[1], self.pids[0]]), dict(pids=[self.pids[0]] * 2),
                dict(deadline_ns=self.stop + 1), dict(deadline_ns=float(self.stop))]):
            with self.subTest(changes=changes):
                directory = self.directory / str(index); directory.mkdir()
                context = dict(self.spec, pids=self.pids, deadline_ns=self.stop); context.update(changes)
                probe.write_json(directory / 'participants.json', context)
                with patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                        patch.object(probe.time, 'monotonic_ns', return_value=0), \
                        self.assertRaises(ValueError):
                    probe.await_peer_ready(directory, self.spec, 0, None)
                self.assertFalse((directory / 'ready_rank0.json').exists())

    def test_ready_fsync_failure_is_fatal_not_diagnostic_tolerance(self):
        with patch.object(probe.os, 'fsync', side_effect=OSError('ready fsync failure')), \
                patch.object(probe.os, 'replace') as replace, self.assertRaises(OSError):
            probe.publish_json(self.directory / 'ready_rank0.json', dict(self.spec, rank=0, pid=self.pids[0]))
        replace.assert_not_called()
        self.assertFalse((self.directory / 'ready_rank0.json').exists())

    def test_old_own_ready_is_not_overwritten(self):
        path = self.directory / 'ready_rank0.json'; path.write_text('old', encoding='utf-8')
        with self.assertRaises(ValueError):
            probe.publish_json(path, dict(self.spec, rank=0, pid=self.pids[0]))
        self.assertEqual(path.read_text(), 'old')

    def test_expired_pair_never_calls_init(self):
        self.context(); self.peer()
        probe.write_json(self.directory / 'manifest.json', dict(self.spec,
            allocation=dict(job_id='synthetic', ranks=[dict(selected=[0])] * 2)))
        with fake_worker() as (_, dist, _), \
                patch.dict(os.environ, {'S07_CASE_DEADLINE_NS': str(self.stop)}), \
                patch.object(probe.time, 'monotonic_ns', return_value=self.stop):
            dist.init_process_group = Mock()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
            dist.init_process_group.assert_not_called()

    def test_failed_preparation_never_publishes_ready(self):
        for mode in ('torch1', 'bad_tid'):
            with self.subTest(mode=mode):
                directory = self.directory / mode; directory.mkdir()
                probe.write_json(directory / 'manifest.json', dict(self.spec,
                    allocation=dict(job_id='synthetic', ranks=[dict(selected=[0])] * 2)))
                with fake_worker() as (torch, dist, validate), \
                        patch.object(probe, 'await_peer_ready') as ready:
                    dist.init_process_group = Mock()
                    if mode == 'torch1':
                        torch.get_num_threads = lambda: 1
                    else:
                        validate.side_effect = [None, ValueError('TID outside selected36')]
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(probe.worker(directory, 0), 1)
                    ready.assert_not_called(); dist.init_process_group.assert_not_called()

    def test_ready_error_never_calls_init(self):
        probe.write_json(self.directory / 'manifest.json', dict(self.spec,
            allocation=dict(job_id='synthetic', ranks=[dict(selected=[0])] * 2)))
        with fake_worker() as (_, dist, _), \
                patch.object(probe, 'await_peer_ready', side_effect=ValueError('wrong ready')):
            dist.init_process_group = Mock()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.worker(self.directory, 0), 1)
            dist.init_process_group.assert_not_called()


class ParentReadinessChecks(unittest.TestCase):
    def run_pair(self, commands, limit=1):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            directory = Path(folder).resolve(); assert directory.is_relative_to(BASE / 'evidence')
            spec = dict(run_id='normal', job_id='synthetic', ready_token='parent-token')
            environment = dict(os.environ, S07_TEST_SPEC=json.dumps(spec))
            state = probe.supervise(commands(directory), directory, limit, environment, ready_context=spec)
            context = json.loads((directory / 'participants.json').read_text()) if (directory / 'participants.json').exists() else None
            rows = [json.loads(line) for line in (directory / 'supervisor.events.jsonl').read_text().splitlines()]
            return state, context, rows

    def waiter(self, directory):
        code = ('import sys,json,os; from pathlib import Path; '
                f'sys.path.insert(0,{str(BASE / "candidate")!r}); import comm_probe as p; '
                'p.await_peer_ready(Path(sys.argv[1]),json.loads(os.environ["S07_TEST_SPEC"]),0,None)')
        return [sys.executable, '-B', '-c', code, str(directory)]

    def test_parent_pids_and_original_deadline(self):
        state, context, rows = self.run_pair(lambda _: [[sys.executable, '-c', 'pass']] * 2, limit=2)
        self.assertEqual(state['reason'], 'complete')
        self.assertEqual(context['pids'], state['pids'])
        self.assertLessEqual(context['deadline_ns'] - rows[0]['monotonic_ns'], 2_000_000_000)
        self.assertGreater(context['deadline_ns'] - rows[0]['monotonic_ns'], 1_500_000_000)

    def test_missing_ready_bounded_cleanup(self):
        state, _, _ = self.run_pair(lambda directory: [self.waiter(directory),
            [sys.executable, '-c', 'import time; time.sleep(60)']], limit=0.5)
        self.assertIn(state['reason'], ('deadline', 'child_failed'))
        self.assertTrue(state['all_reaped'])
        self.assertNotEqual(state['exit_codes'], [0, 0])
        self.assertLess(state['wall_seconds'], 4)

    def test_peer_failure_cleans_waiting_rank(self):
        state, _, _ = self.run_pair(lambda directory: [self.waiter(directory),
            [sys.executable, '-c', 'raise SystemExit(17)']])
        self.assertEqual(state['reason'], 'child_failed')
        self.assertEqual(state['exit_codes'][1], 17)
        self.assertTrue(state['all_reaped'])

    def test_launch_failure_cleans_waiting_rank(self):
        state, context, _ = self.run_pair(lambda directory: [self.waiter(directory),
            [str(directory / 'missing-executable')]])
        self.assertEqual(state['reason'], 'launch_failed')
        self.assertIsNone(context)
        self.assertTrue(state['all_reaped'])

    def test_parent_context_write_failure_cleans_both(self):
        with patch.object(probe, 'publish_json', side_effect=OSError('context write failure')):
            state, context, _ = self.run_pair(lambda directory: [self.waiter(directory),
                [sys.executable, '-c', 'import time; time.sleep(60)']])
        self.assertEqual(state['reason'], 'launch_failed')
        self.assertIsNone(context)
        self.assertTrue(state['all_reaped'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
