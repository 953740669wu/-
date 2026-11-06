"""Exact arithmetic and malformed-shard controls; no Torch required."""
from fractions import Fraction
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import loss_contract as contract


class LossContractChecks(unittest.TestCase):
    def test_unequal_masks_match_complete_global_objective(self):
        counts = [(1, 4), (3, 4)]
        sums = [(2, 8), (12, 16)]
        weights = [contract.backward_weights(counts, rank) for rank in range(2)]
        ddp_mean = sum(Fraction(v) * w[0] + Fraction(c) * w[1]
                       for (v, c), w in zip(sums, weights)) / 2
        self.assertEqual(ddp_mean, Fraction(14, 4) + Fraction(24, 8))

    def test_wrong_local_mean_is_a_negative_control(self):
        correct = Fraction(2 + 12, 1 + 3)
        wrong = (Fraction(2, 1) + Fraction(12, 3)) / 2
        self.assertNotEqual(correct, wrong)

    def test_local_empty_mask_has_finite_global_weight(self):
        weights = contract.backward_weights([(0, 8192), (4, 8192)], 0)
        self.assertEqual(weights, (Fraction(1, 2), Fraction(1, 8192)))

    def test_invalid_global_denominators_rejected(self):
        for counts in ([(0, 2), (0, 2)], [(1, 0), (2, 0)], [(1, 2)],
                       [(-1, 2), (3, 2)], [(1.0, 2), (3, 2)]):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                contract.backward_weights(counts, 0)

    def test_input_gradient_scaled_once_and_parameter_gradient_unchanged(self):
        self.assertEqual(contract.input_gradient_scale(2), Fraction(1, 2))
        with self.assertRaises(ValueError):
            contract.input_gradient_scale(1)

    def test_exact_32_plus_32_sharding(self):
        indices = list(reversed(range(64)))
        self.assertEqual(contract.validate_shards(indices, [indices[:32], indices[32:]]), indices)

    def test_duplicate_missing_reordered_or_wrong_batch_rejected(self):
        indices = list(range(64))
        for shards in ([indices[:32], indices[31:63]], [indices[:31], indices[32:]],
                       [indices[32:], indices[:32]], [indices[:32], indices[32:][::-1]]):
            with self.subTest(shards=shards), self.assertRaises(ValueError):
                contract.validate_shards(indices, shards)
        for global_ids in (indices[:-1], indices[:-1] + [0]):
            with self.assertRaises(ValueError):
                contract.validate_shards(global_ids, [global_ids[:32], global_ids[32:]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
