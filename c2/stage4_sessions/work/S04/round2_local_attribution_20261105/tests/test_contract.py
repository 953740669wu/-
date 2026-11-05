import copy
import os
import unittest

import torch
import torch.nn.functional as F

from common import definitions, fixture, metric
import kml_ops


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_new_symbols(self):
        self.assertTrue(callable(kml_ops.chain_bf16_linear))
        self.assertIn('BF16EncoderBlock', definitions('candidate', ['BF16EncoderBlock']))

    def test_comparator_negative_controls(self):
        x = torch.ones(3)
        self.assertTrue(metric('same', x, x, 0.01)['passed'])
        for got in (None, torch.ones(2), x * 1.03, x * float('nan'), x * float('inf')):
            self.assertFalse(metric('bad', x, got, 0.01)['passed'])
        self.assertFalse(metric('nearzero', x * 0, x * 2e-7, 0.01)['passed'])

    def test_linear_fp32_dw_oracle(self):
        rng = torch.Generator().manual_seed(7)
        x = torch.randn(2, 3, 7, generator=rng).bfloat16().requires_grad_()
        w = torch.randn(5, 7, generator=rng).requires_grad_()
        b = torch.randn(5, generator=rng).requires_grad_()
        g = torch.randn(2, 3, 5, generator=rng).bfloat16()
        y = kml_ops.chain_bf16_linear(x, w, b, 'torch_reference')
        expected = (x.float().reshape(-1, 7) @ w.bfloat16().float().t() + b).bfloat16()
        self.assertTrue(torch.equal(y.reshape(-1, 5), expected))
        y.backward(g)
        self.assertEqual(w.grad.dtype, torch.float32)
        self.assertTrue(torch.equal(w.grad, g.float().reshape(-1, 5).t() @ x.float().reshape(-1, 7)))
        self.assertTrue(torch.equal(x.grad, (g.float() @ w.bfloat16().float()).bfloat16()))
        self.assertTrue(torch.equal(b.grad, g.float().sum((0, 1))))

    def test_linear_rejects_wrong_precision(self):
        with self.assertRaises((ValueError, RuntimeError)):
            kml_ops.chain_bf16_linear(torch.ones(2, 7), torch.ones(5, 7), None, 'torch_reference')

    def test_kml_no_silent_fallback(self):
        if os.name != 'nt' and kml_ops._lib is not None:
            self.skipTest('requires unavailable backend negative control')
        with self.assertRaises(RuntimeError):
            kml_ops.chain_bf16_linear(torch.ones(2, 7).bfloat16(), torch.ones(5, 7), None, 'kml')

    def test_state_and_boundary(self):
        ref, data = fixture()
        cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
        block = cls('torch_reference')
        block.load_state_dict(ref['block'].state_dict(), strict=True)
        self.assertEqual(set(block.state_dict()), set(ref['block'].state_dict()))
        before_linear, before_sdpa = F.linear, F.scaled_dot_product_attention
        y = block(data['x'].bfloat16())
        self.assertEqual(y.dtype, torch.bfloat16)
        self.assertEqual(y.shape, data['x'].shape)
        self.assertTrue(y.is_contiguous())
        self.assertTrue(all(p.dtype == torch.float32 for p in block.parameters()))
        self.assertIs(F.linear, before_linear)
        self.assertIs(F.scaled_dot_product_attention, before_sdpa)

    def test_block_rejects_unsupported_inputs(self):
        cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
        block = cls('torch_reference')
        x = torch.zeros(2, 17, 512).bfloat16()
        for kwargs in (dict(src_mask=torch.ones(17, 17)), dict(is_causal=True),
                       dict(src_key_padding_mask=torch.ones(2, 17))):
            with self.assertRaises(ValueError):
                block(x, **kwargs)
        with self.assertRaises(ValueError):
            block(x.float())

    def test_fp32_control(self):
        ref, data = fixture()
        got = copy.deepcopy(ref['block'])
        x = data['x'].clone().requires_grad_()
        z = data['x'].clone().requires_grad_()
        y, t = ref['block'](x), got(z)
        self.assertTrue(metric('fp32.output', y, t, 2e-6)['passed'])
        y.square().mean().backward()
        t.square().mean().backward()
        self.assertTrue(metric('fp32.dx', x.grad, z.grad, 2e-6)['passed'])
        for a, b in zip(ref['block'].parameters(), got.parameters()):
            self.assertTrue(metric('fp32.dw', a.grad, b.grad, 2e-6)['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
