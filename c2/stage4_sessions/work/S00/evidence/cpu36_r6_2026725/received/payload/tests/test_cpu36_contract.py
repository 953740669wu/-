"""CPU36 policy checks; no torch or Linux execution is claimed by these tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'diagnostic'))
import cpu36_contract as contract


class CPU36Checks(unittest.TestCase):
    def setUp(self):
        self.domain = list(range(76, 114))
        self.siblings = {cpu: [cpu] for cpu in self.domain}
        self.selected = list(range(76, 112))

    def test_allocated38_reserves_last_two_of_actual_domain(self):
        result = contract.select_cpus(self.domain, self.domain, self.siblings)
        self.assertEqual(result['allocated'], self.domain)
        self.assertEqual(result['selected'], self.selected)
        self.assertEqual(result['reserved'], [112, 113])

    def test_exact36_is_valid_only_with_last_two_reserved(self):
        self.assertEqual(contract.select_cpus(self.selected, self.domain, self.siblings)['selected'], self.selected)
        with self.assertRaises(ValueError):
            contract.select_cpus(list(range(78, 114)), self.domain, self.siblings)

    def test_insufficient_37_or_cross_domain_allocation_rejected(self):
        for allocated in [self.domain[:35], self.domain[:37], self.domain[:37] + [200]]:
            with self.subTest(allocated=allocated), self.assertRaises(ValueError):
                contract.select_cpus(allocated, self.domain, self.siblings)

    def test_smt_siblings_do_not_count_as_two_physical_cores(self):
        self.siblings[77] = [76, 77]
        self.siblings[76] = [76, 77]
        with self.assertRaises(ValueError):
            contract.select_cpus(self.domain, self.domain, self.siblings)

    def snapshot(self, masks):
        return dict(complete=True, threads=[dict(tid=100 + i, affinity=mask) for i, mask in enumerate(masks)])

    def test_bound_single_cpu_tids_are_valid_without_each_mask_equal36(self):
        self.assertEqual(contract.validate_threads(self.selected, self.snapshot([[cpu] for cpu in self.selected]), 36), [])

    def test_total_tids_need_not_equal36_idle_pool_threads_allowed(self):
        self.assertEqual(contract.validate_threads(self.selected, self.snapshot([self.selected] * 40), 36), [])

    def test_reserved_or_unauthorized_tid_rejected(self):
        for mask in [[112], [200], [76, 112]]:
            self.assertTrue(contract.validate_threads(self.selected, self.snapshot([mask]), 36))

    def test_union36_alone_does_not_override_torch_threads1(self):
        self.assertTrue(contract.validate_threads(self.selected, self.snapshot([[cpu] for cpu in self.selected]), 1))

    def test_missing_or_incomplete_tid_evidence_rejected(self):
        for snap in [dict(complete=False, threads=[]), self.snapshot([]), self.snapshot([[]])]:
            self.assertTrue(contract.validate_threads(self.selected, snap, 36))

    def test_duplicate_tid_or_boolean_thread_count_rejected(self):
        snap = self.snapshot([[76], [77]])
        snap['threads'][1]['tid'] = snap['threads'][0]['tid']
        self.assertTrue(contract.validate_threads(self.selected, snap, 36))
        self.assertTrue(contract.validate_threads(self.selected, self.snapshot([[76]]), True))

    def test_negative_control_never_changes_cpu_boundary(self):
        snap = self.snapshot([[76]])
        self.assertEqual(contract.validate_threads(self.selected, snap, 1, expected_threads=1), [])
        self.assertTrue(contract.validate_threads(self.selected, self.snapshot([[112]]), 1, expected_threads=1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
