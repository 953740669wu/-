import unittest
from unittest.mock import patch

import torch
import torch.nn.functional as F

from common import definitions, fixture
import kml_ops


class Alignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_native_linear_epilogue_and_autograd(self):
        model, data = fixture()
        x = data['x'].clone().requires_grad_()
        z = data['x'].clone().requires_grad_()
        ref = model['block'].linear1
        w = ref.weight.detach().clone().requires_grad_()
        b = ref.bias.detach().clone().requires_grad_()
        y = F.linear(x, ref.weight, ref.bias)
        got = kml_ops.chain_bf16_linear(z, w, b, 'torch_fp32_control')
        self.assertNotIn('ChainBF16Linear', type(got.grad_fn).__name__)
        self.assertTrue(torch.equal(y, got), 'same fused linear epilogue required')
        g = torch.ones_like(y)
        a = torch.autograd.grad(y, (x, ref.weight, ref.bias), g)
        c = torch.autograd.grad(got, (z, w, b), g)
        self.assertTrue(all(torch.equal(v, t) for v, t in zip(a, c)))

    def test_explicit_candidate_graph_without_whole_reference_calls(self):
        model, data = fixture()
        cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
        block = cls('torch_fp32_control')
        block.load_state_dict(model['block'].state_dict(), strict=True)
        original = F._in_projection_packed
        with patch.object(torch.nn.TransformerEncoderLayer, 'forward', side_effect=AssertionError('whole block forbidden')), \
                patch.object(torch.nn.MultiheadAttention, 'forward', side_effect=AssertionError('whole MHA forbidden')), \
                patch.object(F, '_in_projection_packed', wraps=original) as projection:
            value = block(data['x'])
            value.square().mean().backward()
        self.assertEqual(projection.call_count, 1)
        q, k, v = projection.call_args.args[:3]
        self.assertIs(q, k)
        self.assertIs(k, v)
        self.assertEqual(tuple(q.shape), (17, 2, 512))
        self.assertEqual(tuple(q.stride()), (512, 8704, 1))
        self.assertEqual(value.dtype, torch.float32)
        self.assertTrue(all(p.grad is not None for p in block.parameters()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
