"""Job-identity gates only; framework access is replaced by a sentinel."""
import argparse
import contextlib
import io
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


class JobIdentityChecks(unittest.TestCase):
    def test_matching_job(self):
        with patch.dict(os.environ, {'CCS_JOB_ID': 'current'}):
            probe.validate_current_job('current')

    def test_missing_current_job(self):
        for current in (None, '', '   '):
            with self.subTest(current=current), patch.dict(os.environ, {}, clear=True):
                if current is not None:
                    os.environ['CCS_JOB_ID'] = current
                with self.assertRaisesRegex(ValueError, 'CCS_JOB_ID'):
                    probe.validate_current_job('current')

    def test_missing_or_old_configured_job(self):
        with patch.dict(os.environ, {'CCS_JOB_ID': 'current'}):
            for configured in (None, '', 'old', 123):
                with self.subTest(configured=configured), self.assertRaisesRegex(ValueError, 'CCS_JOB_ID'):
                    probe.validate_current_job(configured)

    def test_launcher_rejects_before_workers(self):
        for current, configured in ((None, 'current'), ('old', 'current'),
                                    ('current', 'old'), ('current', None)):
            with self.subTest(current=current, configured=configured), \
                    tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                    patch.dict(os.environ, {}, clear=True), \
                    patch.object(probe.sys, 'platform', 'linux'), \
                    patch.object(probe.os, 'sched_getaffinity', create=True) as affinity, \
                    patch.object(probe, 'supervise') as supervise:
                if current is not None:
                    os.environ['CCS_JOB_ID'] = current
                directory = Path(folder)
                allocation = directory / 'allocation.json'
                allocation.write_text(json.dumps(dict(job_id=configured, ranks={'0': {}, '1': {}})),
                                      encoding='utf-8')
                args = argparse.Namespace(output=directory / 'run', allocation=allocation,
                                          case='normal', pg_timeout=5, deadline=30)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(probe.run(args), 1)
                summary = json.loads((args.output / 'summary.json').read_text(encoding='utf-8'))
                self.assertEqual(summary['status'], 'FAIL')
                self.assertIn('CCS_JOB_ID', summary['error'])
                self.assertNotIn('supervisor', summary)
                affinity.assert_not_called()
                supervise.assert_not_called()

    def test_worker_rejects_before_cpu_and_framework(self):
        cases = [(None, 'current', 'current'), ('old', 'current', 'current'),
                 ('current', 'old', 'current'), ('current', 'current', 'old'),
                 ('current', None, 'current'), ('current', 'current', None)]
        for current, manifest_job, allocation_job in cases:
            for rank in range(2):
                with self.subTest(current=current, manifest=manifest_job, allocation=allocation_job, rank=rank), \
                        tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                        patch.dict(os.environ, {}, clear=True), \
                        patch.object(probe.cpu36, 'validate_receipt') as receipt, \
                        patch.object(probe.os, 'sched_getaffinity', create=True) as affinity, \
                        patch.object(probe, 'backend_info') as framework:
                    if current is not None:
                        os.environ['CCS_JOB_ID'] = current
                    directory = Path(folder)
                    probe.write_json(directory / 'manifest.json', dict(
                        job_id=manifest_job, allocation=dict(job_id=allocation_job)))
                    with self.assertRaisesRegex(ValueError, 'CCS_JOB_ID'):
                        probe.worker(directory, rank)
                    receipt.assert_not_called()
                    affinity.assert_not_called()
                    framework.assert_not_called()

    def test_worker_matching_reaches_framework_gate(self):
        for rank in range(2):
            with self.subTest(rank=rank), tempfile.TemporaryDirectory(dir=BASE / 'evidence') as folder, \
                    patch.dict(os.environ, dict(probe.ENVIRONMENT, CCS_JOB_ID='current')), \
                    patch.object(probe.cpu36, 'validate_receipt'), \
                    patch.object(probe.cpu36, 'snapshot_threads', return_value={}), \
                    patch.object(probe.cpu36, 'validate_snapshot'), \
                    patch.object(probe.os, 'sched_getaffinity', create=True, return_value={0}), \
                    patch.object(probe.os, 'sched_setaffinity', create=True) as bind, \
                    patch.object(probe, 'backend_info', side_effect=RuntimeError('framework sentinel')) as framework:
                directory = Path(folder)
                probe.write_json(directory / 'manifest.json', dict(job_id='current', run_id='synthetic',
                    allocation=dict(job_id='current', ranks=[dict(selected=[0])] * 2)))
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(probe.worker(directory, rank), 1)
                framework.assert_called_once_with(directory / f'rank{rank}.events.jsonl')
                bind.assert_called_once_with(0, [0])
                report = json.loads((directory / f'rank{rank}.json').read_text(encoding='utf-8'))
                self.assertEqual(report['error'], 'RuntimeError: framework sentinel')


if __name__ == '__main__':
    unittest.main(verbosity=2)
