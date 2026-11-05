"""Unit parsing and missing-evidence checks; no actual training memory run."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memory_metrics
import cpu36_guard


class MemoryMetricTests(unittest.TestCase):
    def test_proc_units_are_bytes_and_mib(self):
        text = 'Name:\tpython\nVmRSS:\t1024 kB\nVmHWM:\t2048 kB\nHugetlbPages:\t0 kB\n'
        with patch.object(memory_metrics.Path, 'read_text', return_value=text):
            data = memory_metrics.rss()
        self.assertEqual(data['rss_bytes'], 1048576)
        self.assertEqual(data['peak_rss_bytes'], 2097152)
        self.assertEqual(data['peak_rss_MiB'], 2.)

    def test_missing_wrong_unit_or_hugetlb_evidence_rejected(self):
        for text in ('VmRSS: 1 kB\n', 'VmRSS: 1 MB\nVmHWM: 2 kB\nHugetlbPages: 0 kB\n',
                     'VmRSS: 1 kB\nVmHWM: 2 kB\nHugetlbPages: 4 kB\n'):
            with self.subTest(text=text), patch.object(memory_metrics.Path, 'read_text', return_value=text), \
                 self.assertRaises(ValueError):
                memory_metrics.rss()

    def test_peak_reset_denied_never_claims_training_peak(self):
        with patch.object(memory_metrics.Path, 'write_text', side_effect=PermissionError('denied')):
            data = memory_metrics.reset_peak()
        self.assertFalse(data['available'])
        self.assertIn('denied', data['error'])

    def test_peak_reset_targets_only_own_process_counter(self):
        with patch.object(memory_metrics.Path, 'write_text') as write:
            data = memory_metrics.reset_peak()
        self.assertTrue(data['available'])
        write.assert_called_once_with('5\n', encoding='ascii')

    def test_memory_guard_accepts_complete_training_phase_evidence(self):
        names = ['before_framework', 'after_framework', 'after_backend', 'initialized',
                 'before_training', 'after_training']
        state = dict(errors=[], checkpoints=[dict(name=name) for name in names])
        with patch.object(cpu36_guard, 'checkpoint', side_effect=lambda state, name, _torch:
                          state['checkpoints'].append(dict(name=name))):
            cpu36_guard.finish_memory(state, object())

    def test_memory_guard_rejects_missing_training_boundary(self):
        state = dict(errors=[], checkpoints=[dict(name='before_framework')])
        with patch.object(cpu36_guard, 'checkpoint'), self.assertRaisesRegex(ValueError, 'memory CPU36'):
            cpu36_guard.finish_memory(state, object())


if __name__ == '__main__':
    unittest.main(verbosity=2)
