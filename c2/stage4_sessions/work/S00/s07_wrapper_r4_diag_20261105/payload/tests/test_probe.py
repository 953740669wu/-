"""Standard-library checks only; these do not execute tensor communication."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'candidate'))
import comm_probe as probe
import cpu36_contract as cpu36
import run_checks


class ReportChecks(unittest.TestCase):
    def setUp(self):
        self.reports = [dict(status='PASS', run_id='test', rank=r, world_size=2,
                             pid=100 + r, backend='gloo', identity=[0, 1],
                             broadcast=[1.0, -2.0, 0.5, 4.0], total=[3.0, 6.0, -2.0, 1.0],
                             shape=[4], dtype='torch.float32') for r in range(2)]

    def test_complete_pair(self):
        probe.validate_reports(self.reports, 'test', [100, 101])

    def test_missing_or_extra_rank(self):
        for rows in (self.reports[:1], self.reports + self.reports[:1]):
            with self.assertRaises(ValueError):
                probe.validate_reports(rows, 'test', [100, 101])

    def test_bad_values_and_identity(self):
        for key, value in [('status', 'FAIL'), ('run_id', 'old'), ('rank', 0),
                           ('pid', 999), ('world_size', 1), ('backend', 'mpi'),
                           ('identity', [0, 0]), ('broadcast', [0.0] * 4),
                           ('total', [3.0, 6.0, -2.0, float('nan')]),
                           ('shape', [2, 2]), ('dtype', 'torch.float64')]:
            with self.subTest(key=key):
                rows = copy.deepcopy(self.reports)
                rows[1][key] = value
                with self.assertRaises(ValueError):
                    probe.validate_reports(rows, 'test', [100, 101])


class ResourceChecks(unittest.TestCase):
    def test_live_allocation_guards_with_synthetic_sysfs(self):
        data = dict(job_id='synthetic', scheduler_evidence='/raw-scheduler.txt', ranks={
            '0': dict(node=0, allocated=list(range(38))),
            '1': dict(node=1, allocated=list(range(38, 76)))})

        def read(path, **kwargs):
            name = str(path).replace('\\', '/')
            if name.endswith('allocation.json'):
                return json.dumps(data)
            if name.endswith('cpulist'):
                return '0-37' if 'node0/' in name else '38-75'
            return name.split('/cpu')[-1].split('/')[0]

        with patch.object(probe.sys, 'platform', 'linux'), \
                patch.dict(os.environ, {'CCS_JOB_ID': 'synthetic'}), \
                patch.object(probe.os, 'sched_getaffinity', create=True, return_value=set(range(76))), \
                patch.object(Path, 'read_text', read), \
                patch.object(Path, 'is_absolute', return_value=True), \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(cpu36, 'sha', return_value='synthetic-sha'):
            result = probe.load_allocation(Path('allocation.json'))
            self.assertEqual(result['ranks'][1]['selected'], list(range(38, 74)))
            data['ranks']['1']['allocated'].append(76)
            with self.assertRaises(ValueError):
                probe.load_allocation(Path('allocation.json'))
            data['ranks']['1']['allocated'] = list(range(38, 76))
            data['ranks']['1']['allocated'][0] = 39
            with self.assertRaises(ValueError):
                probe.load_allocation(Path('allocation.json'))

    def test_exact36_and_reserved2(self):
        domain = list(range(38))
        siblings = {str(cpu): [cpu] for cpu in domain}
        for allocated in (domain, domain[:36]):
            receipt = cpu36.select_cpus(allocated, domain, siblings)
            self.assertEqual(receipt['selected'], domain[:36])
            self.assertEqual(receipt['reserved'], [36, 37])

    def test_bad_allocation(self):
        domain = list(range(38))
        siblings = {str(cpu): [cpu] for cpu in domain}
        for allocated in (domain[:35], domain[:37], domain[2:], domain + [38]):
            with self.subTest(allocated=allocated), self.assertRaises(ValueError):
                cpu36.select_cpus(allocated, domain, siblings)

    def test_thread_outside_boundary(self):
        with self.assertRaises(ValueError):
            cpu36.validate_snapshot(list(range(36)),
                                    dict(complete=True, threads=[dict(tid=1, affinity=[36])]))

    def test_overlapping_rank_domains(self):
        receipt = dict(node=0, allocated=list(range(38)), selected=list(range(36)))
        with self.assertRaises(ValueError):
            probe.validate_pair([receipt, receipt])


class SupervisorChecks(unittest.TestCase):
    def run_children(self, programs, timeout=2):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            return probe.supervise([[sys.executable, '-c', code] for code in programs],
                                   Path(folder), timeout, os.environ.copy())

    def test_success(self):
        state = self.run_children(['pass', 'pass'])
        self.assertEqual(state['reason'], 'complete')
        self.assertEqual(state['exit_codes'], [0, 0])
        self.assertTrue(state['all_reaped'])

    def test_failed_rank_stops_peer(self):
        state = self.run_children(['raise SystemExit(17)', 'import time; time.sleep(60)'])
        self.assertEqual(state['reason'], 'child_failed')
        self.assertEqual(state['exit_codes'][0], 17)
        self.assertNotEqual(state['exit_codes'][1], 0)
        self.assertTrue(state['all_reaped'])

    def test_watchdog_stops_pair(self):
        state = self.run_children(['import time; time.sleep(60)'] * 2, timeout=0.5)
        self.assertEqual(state['reason'], 'deadline')
        self.assertTrue(state['all_reaped'])
        self.assertTrue(all(code != 0 for code in state['exit_codes']))

    def test_spawn_error_cleans_started_peer(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            state = probe.supervise([[sys.executable, '-c', 'import time; time.sleep(60)'],
                                     [str(Path(folder) / 'missing-executable')]],
                                    Path(folder), 2, os.environ.copy())
        self.assertEqual(state['reason'], 'launch_failed')
        self.assertTrue(state['all_reaped'])
        self.assertNotEqual(state['exit_codes'][0], 0)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux process-group cleanup only')
    def test_linux_process_group(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            child_pid = Path(folder) / 'grandchild.pid'
            code = ('import subprocess,sys,time,pathlib; '
                    'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
                    f'pathlib.Path({str(child_pid)!r}).write_text(str(p.pid)); time.sleep(60)')
            state = probe.supervise([[sys.executable, '-c', code],
                                     [sys.executable, '-c', 'import time; time.sleep(60)']],
                                    Path(folder), 1, os.environ.copy())
            self.assertTrue(state['all_reaped'])
            pid = int(child_pid.read_text())
            stat = Path(f'/proc/{pid}/stat')
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == 'Z')


class FailureAcceptanceChecks(unittest.TestCase):
    def test_preflight_failure_is_not_injected_failure_success(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            directory = Path(folder)
            probe.write_json(directory / 'summary.json', dict(status='FAIL', error='no allocation'))
            with self.assertRaises(ValueError):
                run_checks.check_case('crash', 1, directory)

    def test_timeout_must_be_gloo_broadcast_timeout(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            directory = Path(folder)
            probe.write_json(directory / 'summary.json', dict(status='FAIL', supervisor=dict(
                reason='child_failed', pids=[100, 101], all_reaped=True, exit_codes=[1, -15])))
            probe.write_json(directory / 'rank0.json', dict(stage='broadcast', error='missing torch'))
            probe.write_json(directory / 'rank1.json', dict(stage='injected_hang'))
            with self.assertRaises(ValueError):
                run_checks.check_case('collective-timeout', 1, directory)
            probe.write_json(directory / 'rank0.json', dict(stage='broadcast', error='Timed out waiting'))
            self.assertEqual(run_checks.check_case('collective-timeout', 1, directory)[
                'expected_behavior'], 'PASS')

    def test_watchdog_requires_both_injections(self):
        with tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder:
            directory = Path(folder)
            probe.write_json(directory / 'summary.json', dict(status='FAIL', supervisor=dict(
                reason='deadline', pids=[100, 101], all_reaped=True, exit_codes=[-15, -15])))
            for rank in range(2):
                probe.write_json(directory / f'rank{rank}.json', dict(stage='init_process_group'))
            with self.assertRaises(ValueError):
                run_checks.check_case('watchdog', 124, directory)


if __name__ == '__main__':
    unittest.main(verbosity=2)
