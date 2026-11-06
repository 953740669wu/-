"""LOCAL_FIXTURE: metadata/timestamp checks, no BLAS/model/data execution."""
import copy
import unittest

from analyze_gemm import PROTOCOL, boundary_totals, check_sample


def call(index=1, thread=7):
    return dict(step=3, call_index=index, thread_id=thread, parent_call_index=None,
        role='forward', linear_context='forward', ta=False, tb=True, beta=1.0,
        m=2, n=3, k=4, native_calls=1, status='COMPLETE',
        a=dict(shape=[2, 4], stride=[4, 1], dtype='torch.float32', contiguous=True),
        b=dict(shape=[3, 4], stride=[4, 1], dtype='torch.float32', contiguous=True),
        output=dict(shape=[2, 3], stride=[3, 1], dtype='torch.float32', contiguous=True,
            aliases_a_storage=False, aliases_b_storage=False, is_given_out=True),
        sgemm=dict(layout=101, transa=111, transb=112, m=2, n=3, k=4,
            alpha=1.0, lda=4, ldb=4, beta=1.0, ldc=3),
        gemm_start_ns=10, gemm_end_ns=20, gemm_wall_ns=10,
        ctypes_thread_id=thread, ctypes_start_ns=12, ctypes_end_ns=17,
        ctypes_wall_ns=5, outer_minus_ctypes_ns=5)


def sample(rows):
    return dict(protocol=PROTOCOL, step=3, status='COMPLETE', records=len(rows), calls=rows)


class MetadataChecks(unittest.TestCase):
    def test_complete_one_to_one_pair(self):
        self.assertEqual(check_sample(sample([call()]), expected_calls=1), [])

    def test_thread_and_boundary_mismatch(self):
        row = call(); row['ctypes_thread_id'] = 8; row['ctypes_end_ns'] = 21
        issues = check_sample(sample([row]), expected_calls=1)
        self.assertTrue(any('thread' in x for x in issues))
        self.assertTrue(any('interval' in x for x in issues))

    def test_actual_shape_flags_and_leading_dimensions(self):
        row = call(); row['b']['shape'] = [3, 5]; row['sgemm']['ldb'] = 99
        issues = check_sample(sample([row]), expected_calls=1)
        self.assertTrue(any('dimensions' in x for x in issues))
        self.assertTrue(any('parameters' in x for x in issues))

    def test_missing_pair_and_alias_rejected(self):
        row = call(); row['native_calls'] = 0; row['output']['aliases_a_storage'] = True
        issues = check_sample(sample([row]), expected_calls=1)
        self.assertTrue(any('one-to-one' in x for x in issues))
        self.assertTrue(any('alias' in x for x in issues))
        self.assertTrue(check_sample(sample([]), expected_calls=1))

    def test_role_not_guessed_from_dimensions(self):
        row = call(); row['role'] = 'dW'
        self.assertTrue(any('role' in x for x in check_sample(sample([row]), expected_calls=1)))

    def test_nested_or_duplicate_spans_use_union(self):
        a = call(); b = copy.deepcopy(a); b['call_index'] = 2; b['parent_call_index'] = 1
        stats = boundary_totals([a, b])
        self.assertEqual(stats['gemm']['raw_sum_ns'], 20)
        self.assertEqual(stats['gemm']['all_threads_coverage_ns'], 10)
        self.assertEqual(stats['ctypes']['all_threads_coverage_ns'], 5)
        self.assertEqual(stats['paired_difference_sum_ns'], 10)
        self.assertEqual(stats['coverage_difference_ns'], 5)

    def test_cross_thread_coverage_is_not_thread_sum(self):
        stats = boundary_totals([call(1, 7), call(2, 8)])
        self.assertEqual(stats['gemm']['per_thread_union_sum_ns'], 20)
        self.assertEqual(stats['gemm']['all_threads_coverage_ns'], 10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
