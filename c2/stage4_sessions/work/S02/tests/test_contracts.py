"""Stdlib algebra/static checks only; these do not execute autograd."""
import ast
from fractions import Fraction
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Contracts(unittest.TestCase):
    def test_masked_micro_means_are_not_full_mean(self):
        # Residual squares and mask counts from two unequal-density chunks.
        sums, counts = [4, 18], [1, 9]
        full = Fraction(sum(sums), sum(counts))
        wrong = sum(Fraction(s, n) for s, n in zip(sums, counts)) / 2
        self.assertNotEqual(full, wrong)
        self.assertEqual(full, sum(Fraction(s, sum(counts)) for s in sums))

    def test_empty_local_mask_and_uneven_last_chunk(self):
        sums, counts = [0, 8, 6], [0, 4, 1]
        self.assertEqual(Fraction(14, 5), sum(Fraction(s, sum(counts)) for s in sums))
        # Per-sample coarse and decoder elements use total counts, including tail.
        sizes = [3, 3, 1]
        self.assertEqual(sum(Fraction(n * 256, 7 * 256) for n in sizes), 1)
        self.assertEqual(sum(Fraction(n * 4096, 7 * 4096) for n in sizes), 1)

    def test_candidate_has_single_update_outside_micro_loop(self):
        tree = ast.parse((ROOT / 'candidate' / 'training_step.py').read_text('utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'training_step')
        methods = lambda nodes, name: [n for node in nodes for n in ast.walk(node)
                                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                      and n.func.attr == name]
        self.assertEqual(len(methods(fn.body, 'zero_grad')), 1)
        self.assertEqual(len(methods(fn.body, 'step')), 1)
        loop = next(n for n in fn.body if isinstance(n, ast.For))
        self.assertFalse(methods(loop.body, 'step'))
        self.assertFalse(methods(loop.body, 'zero_grad'))
        self.assertEqual(len(methods(loop.body, 'backward')), 1)
        self.assertFalse(methods(fn.body, 'rand'))
        self.assertFalse(methods(fn.body, 'randint'))
        self.assertFalse(methods(fn.body, 'randn_like'))

    def test_model_copy_is_byte_identical(self):
        project = ROOT.parents[3]
        for name in ('s4_models.py', 'kml_ops.py'):
            self.assertEqual((ROOT / 'baseline' / name).read_bytes(), (project / name).read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
