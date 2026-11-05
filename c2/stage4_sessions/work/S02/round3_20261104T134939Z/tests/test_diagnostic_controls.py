"""Real torch diagnostic controls; not full-model acceptance."""
import importlib.util
import os
from pathlib import Path
import unittest
import torch

ROOT = Path(__file__).resolve().parents[1]


class Controls(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('diagnostic_common', ROOT / 'diagnostic_common.py')
        self.common = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.common)

    def test_fresh_adam_formula_and_small_gradient_amplification(self):
        deltas = []
        for grad in (1e-9, -1e-9):
            p = torch.nn.Parameter(torch.tensor([0.]))
            opt = torch.optim.AdamW([p], lr=1e-4)
            p.grad = torch.tensor([grad])
            opt.step()
            expected = self.common.first_update(0., grad)
            self.assertAlmostEqual(p.item(), expected, delta=1e-11)
            deltas.append(p.item())
        self.assertGreater(abs(deltas[0] - deltas[1]), 1e-5)

    def test_constant_key_bias_is_mathematically_redundant(self):
        torch.manual_seed(12)
        q = torch.randn(2, 3, 4, dtype=torch.float64)
        k = torch.randn(2, 3, 4, dtype=torch.float64)
        v = torch.randn(2, 3, 4, dtype=torch.float64)
        bias = torch.randn(4, dtype=torch.float64, requires_grad=True)
        y = torch.softmax(q @ (k + bias).transpose(-2, -1), -1) @ v
        ref = torch.softmax(q @ k.transpose(-2, -1), -1) @ v
        self.assertLess((y-ref).abs().max().item(), 1e-12)
        y.square().sum().backward()
        self.assertLess(bias.grad.abs().max().item(), 1e-12)

    def test_loss_target_and_prediction_adjoints_replay(self):
        torch.manual_seed(2)
        x = torch.randn(7, 3, requires_grad=True)
        target = torch.randn(7, 3, requires_grad=True)
        p = x.square()
        gp, gt = torch.autograd.grad(torch.nn.functional.mse_loss(p,target), (p,target), retain_graph=True)
        ref = torch.autograd.grad(torch.nn.functional.mse_loss(p,target), (x,target))
        xx, tt = x.detach().clone().requires_grad_(), target.detach().clone().requires_grad_()
        torch.autograd.backward((xx.square(),tt),(gp,gt))
        self.assertTrue(torch.equal(ref[0],xx.grad))
        self.assertTrue(torch.equal(ref[1],tt.grad))

    def test_kml_rejects_missing_actual_environment(self):
        if os.name == 'nt':
            with self.assertRaisesRegex(RuntimeError, 'Linux'):
                self.common.configure_backend(torch, 'kml', None)
        else:
            with self.assertRaisesRegex(RuntimeError, 'four|CPU'):
                self.common.configure_backend(torch, 'kml', None)


if __name__ == '__main__':
    torch.set_num_threads(4)
    unittest.main(verbosity=2)
