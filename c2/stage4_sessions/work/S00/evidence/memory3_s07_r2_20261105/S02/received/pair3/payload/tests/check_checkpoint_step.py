"""Small native autograd checks, not the fixed full model or C2 acceptance."""
import copy
from pathlib import Path
import sys
import unittest

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import full_batch_step


class TinyEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.input = torch.nn.Linear(1, 8)
        layer = torch.nn.TransformerEncoderLayer(8, 2, 16, dropout=0., batch_first=True)
        self.tf = torch.nn.TransformerEncoder(layer, 2, enable_nested_tensor=False)
        self.head_v = torch.nn.Linear(8, 1)
        self.head_coarse = torch.nn.Linear(8, 256)

    def forward(self, v, angles, belt, mask):
        return self.tf(self.input(v.unsqueeze(-1)), src_key_padding_mask=~mask)


class CheckpointStepTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(17)
        self.enc = TinyEncoder()
        self.dec = torch.nn.Linear(2, 2)
        self.v = torch.randn(4, 3)
        self.image = torch.randn(4, 1, 16, 16)
        self.mask = torch.tensor([[1, 0, 1], [1, 1, 1], [0, 1, 1], [1, 1, 0]], dtype=torch.bool)

    def run_step(self, enc, dec, helper):
        v = self.v.clone().requires_grad_(); image = self.image.clone().requires_grad_()
        opt = torch.optim.AdamW(list(enc.parameters()) + list(dec.parameters()), lr=1e-4,
            betas=(0.9, 0.999), eps=1e-8, weight_decay=0.01)
        steps = []
        handle = opt.register_step_post_hook(lambda *_: steps.append(1))
        if helper:
            loss = full_batch_step.training_step(enc, dec, opt, v, None, None, image, self.mask)
        else:
            h = enc(v, None, None, self.mask)
            loss = F.mse_loss(enc.head_v(h)[..., 0][self.mask], v[self.mask]) + F.mse_loss(
                enc.head_coarse(h.mean(1)), F.adaptive_avg_pool2d(image, 16).flatten(1))
            opt.zero_grad(); loss.backward(); opt.step()
        handle.remove()
        return loss, v.grad, image.grad, opt, steps

    def test_mean_formula_and_single_fresh_adamw_step(self):
        ref, got = copy.deepcopy(self.enc), copy.deepcopy(self.enc)
        dr, dg = copy.deepcopy(self.dec), copy.deepcopy(self.dec)
        left = self.run_step(ref, dr, False); right = self.run_step(got, dg, True)
        for a, b in zip(left[:3], right[:3]):
            self.assertTrue(torch.equal(a, b))
        self.assertEqual(right[4], [1])
        self.assertFalse(right[0].requires_grad)
        for a, b in zip(ref.parameters(), got.parameters()):
            self.assertTrue(torch.equal(a, b)); self.assertTrue(torch.equal(a.grad, b.grad))
            for name in ('step', 'exp_avg', 'exp_avg_sq'):
                self.assertTrue(torch.equal(left[3].state[a][name], right[3].state[b][name]))
        self.assertTrue(all(p.grad is None and p not in right[3].state for p in dg.parameters()))

    def test_checkpoint_isolation_kwargs_recompute_and_strict_gradients(self):
        ref, got = copy.deepcopy(self.enc), copy.deepcopy(self.enc)
        original = ref.tf.layers[0].forward
        full_batch_step.enable_checkpoint(got)
        self.assertEqual(ref.tf.layers[0].forward, original)
        self.assertEqual(list(ref.state_dict()), list(got.state_dict()))
        calls = []
        handle = got.tf.layers[0].linear1.register_forward_pre_hook(lambda *_: calls.append(1))
        left = self.run_step(ref, copy.deepcopy(self.dec), True)
        right = self.run_step(got, copy.deepcopy(self.dec), True)
        handle.remove()
        self.assertGreaterEqual(len(calls), 2)
        sys.path.insert(0, str(ROOT / 'tests'))
        from check_equivalence import compare
        metrics = []
        for name, a, b in zip(('loss', 'input_v', 'input_image'), left[:3], right[:3]):
            compare(torch, name, a, b, 'tensor', metrics)
        for (name, a), (_, b) in zip(ref.named_parameters(), got.named_parameters()):
            compare(torch, name, a, b, 'tensor', metrics)
            compare(torch, name + '.grad', a.grad, b.grad, 'tensor', metrics)
            for key in ('step', 'exp_avg', 'exp_avg_sq'):
                compare(torch, name + '.' + key, left[3].state[a][key], right[3].state[b][key],
                        'exact' if key == 'step' else 'state', metrics)
        self.assertTrue(all(item['passed'] for item in metrics))
        self.assertEqual(left[4], [1]); self.assertEqual(right[4], [1])


if __name__ == '__main__':
    torch.set_num_threads(36)
    assert torch.get_num_threads() == 36
    print('SMALL_NATIVE_CHECK_ONLY; actual Torch intra-op=36; no full model/case/KML/memory run', flush=True)
    unittest.main(verbosity=2)
