"""Stdlib policy tests only; no framework, model, Linux or KML acceptance."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cpu36_contract as contract
import cpu36_guard as guard


class CPU36GuardTests(unittest.TestCase):
    def setUp(self):
        self.receipt = contract.select_cpus(list(range(38)), list(range(38)),
                                          {str(i): [i] for i in range(38)})
        self.receipt['node'] = 0
        self.record = dict(name='after_framework', calling_tid=101, calling_affinity=[0],
            environment=contract.ENVIRONMENT.copy(), torch_intraop=36, torch_interop=608,
            parallel_info='actual torch metadata', runtime=dict(libraries={
                '/runtime/libomp.so': {'omp_get_max_threads': 36}}),
            snapshot=dict(complete=True, threads=[dict(tid=101, affinity=[0]),
                dict(tid=102, affinity=list(range(36)))], vanished=[], errors=[]))

    def test_legal_close_single_core_caller_passes(self):
        guard.validate_checkpoint(self.record, self.receipt)

    def test_torch1_rejected(self):
        self.record['torch_intraop'] = 1
        with self.assertRaisesRegex(ValueError, 'intra-op'):
            guard.validate_checkpoint(self.record, self.receipt)

    def test_reserved_and_unauthorized_cpus_rejected(self):
        for cpu in (36, 37, 99):
            with self.subTest(cpu=cpu):
                record = copy.deepcopy(self.record)
                record['snapshot']['threads'][1]['affinity'] = [cpu]
                with self.assertRaisesRegex(ValueError, 'boundary'):
                    guard.validate_checkpoint(record, self.receipt)

    def test_wrong_selected_count_rejected(self):
        self.receipt['selected'] = list(range(35))
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'):
            guard.validate_checkpoint(self.record, self.receipt)

    def test_missing_empty_duplicate_or_incomplete_tid_rejected(self):
        for change in (dict(threads=[]), dict(complete=False), dict(vanished=[102]),
                       dict(errors=['unreadable']), dict(threads=[dict(tid=101, affinity=[])]),
                       dict(threads=[dict(tid=101, affinity=[0]), dict(tid=101, affinity=[1])])):
            with self.subTest(change=change):
                record = copy.deepcopy(self.record)
                record['snapshot'].update(change)
                with self.assertRaises(ValueError):
                    guard.validate_checkpoint(record, self.receipt)

    def test_missing_caller_or_conflicting_omp_rejected(self):
        for key, value in [('calling_tid', 999), ('runtime', {'libraries': {}}),
                           ('environment', dict(OMP_NUM_THREADS='36', MKL_NUM_THREADS='1'))]:
            with self.subTest(key=key):
                record = copy.deepcopy(self.record); record[key] = value
                with self.assertRaises(ValueError):
                    guard.validate_checkpoint(record, self.receipt)

    def test_exact_first36_allocation_passes(self):
        receipt = contract.select_cpus(list(range(36)), list(range(38)),
                                      {str(i): [i] for i in range(38)})
        self.assertEqual(receipt['reserved'], [36, 37])

    def test_bad_allocation_sizes_and_reserve_overlap_rejected(self):
        for allowed in (list(range(4)), list(range(35)), list(range(37)), list(range(1, 37))):
            with self.subTest(allowed=allowed), self.assertRaises(ValueError):
                contract.select_cpus(allowed, list(range(38)), {str(i): [i] for i in range(38)})

    def test_cross_domain_authorization_rejected(self):
        with patch.object(guard.os, 'sched_getaffinity', return_value=set(range(76)), create=True), \
             patch.object(guard.contract, 'discover_contracts', return_value={0: self.receipt}), \
             patch.dict(os.environ, {'CCS_JOB_ID': 'test-job'}):
            with self.assertRaisesRegex(ValueError, 'single'):
                guard.capture_allocation()

    def test_missing_actual_gemm_rejected(self):
        import diagnostic_common
        with self.assertRaisesRegex(RuntimeError, 'no actual'):
            diagnostic_common.finish_backend({'kml_gemm_calls': 0}, list(range(36)))

    def test_library_identity_drift_rejected(self):
        import diagnostic_common
        record = dict(kml_gemm_calls=1, libraries=[dict(path='/runtime/kml.so', sha256='before')])
        with patch.object(diagnostic_common, 'affinity', return_value={}), \
             patch.object(diagnostic_common, 'mapped_libraries', return_value=[dict(path='/runtime/kml.so', sha256='after')]), \
             self.assertRaisesRegex(RuntimeError, 'library changed'):
            diagnostic_common.finish_backend(record, list(range(36)))

    def test_checker_import_does_not_import_frameworks(self):
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)
        spec = importlib.util.spec_from_file_location('checker_import_test',
            Path(__file__).resolve().parents[1] / 'diagnose_update.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertNotIn('torch', sys.modules)
        self.assertNotIn('numpy', sys.modules)

    def test_prepare_captures_then_binds_before_framework(self):
        import json
        allocation = dict(job_id='test-job', host='test-host', receipt=self.receipt)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'evidence') as tmp:
            path = Path(tmp) / 'allocation.json'; path.write_text(json.dumps(allocation))
            state = {}
            with patch.object(guard.sys, 'platform', 'linux'), \
                 patch.object(guard, 'capture_allocation', return_value=allocation), \
                 patch.object(guard.os, 'sched_setaffinity', create=True) as bind, \
                 patch.object(guard.os, 'sched_getaffinity', return_value=set(range(36)), create=True), \
                 patch.object(guard, 'checkpoint') as check:
                guard.prepare(list(range(36)), path, state)
            bind.assert_called_once_with(0, list(range(36)))
            check.assert_called_once_with(state, 'before_framework')
            self.assertEqual(state['pid'], os.getpid())

    def test_missing_or_stale_allocation_receipt_rejected(self):
        import json
        allocation = dict(job_id='current-job', host='test-host', receipt=self.receipt)
        with patch.object(guard.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(ValueError, 'missing'):
                guard.prepare(list(range(36)), None, {})
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'evidence') as tmp:
                path = Path(tmp) / 'allocation.json'
                path.write_text(json.dumps(dict(allocation, job_id='old-job')))
                with patch.object(guard, 'capture_allocation', return_value=allocation), \
                     self.assertRaisesRegex(ValueError, 'job/host'):
                    guard.prepare(list(range(36)), path, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
