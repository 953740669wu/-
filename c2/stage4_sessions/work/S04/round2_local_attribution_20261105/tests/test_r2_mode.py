import unittest

import torch

from common import definitions, fixture


class R2Mode(unittest.TestCase):
    def test_same_rewrite_without_quantization(self):
        torch.set_num_threads(2)
        model, data = fixture()
        cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
        block = cls('torch_fp32_control')
        block.load_state_dict(model['block'].state_dict(), strict=True)
        x = data['x'].clone().requires_grad_()
        y = block(x)
        self.assertEqual(y.dtype, torch.float32)
        y.square().mean().backward()
        self.assertEqual(x.grad.dtype, torch.float32)
        self.assertTrue(all(p.grad is not None and p.grad.dtype == torch.float32 for p in block.parameters()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
