"""Check the changed QKV orchestration against original MHA, without quantization."""
import copy
import json
import unittest

import torch
import torch.nn.functional as F

from common import ROOT, definitions, fixture, metric


class AttentionBoundary(unittest.TestCase):
    def test_original_mha_output_and_gradients(self):
        torch.set_num_threads(2)
        model, data = fixture()
        ref = model['block'].self_attn
        cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
        block = cls('torch_reference')
        block.self_attn.load_state_dict(copy.deepcopy(ref.state_dict()), strict=True)
        x = data['x'].clone().requires_grad_()
        z = data['x'].clone().requires_grad_()
        out = ref(x, x, x, need_weights=False)[0]
        a = block.self_attn
        qkv = F.linear(z, a.in_proj_weight, a.in_proj_bias)
        got = F.linear(block._attention(qkv), a.out_proj.weight, a.out_proj.bias)
        g = torch.randn(out.shape, generator=torch.Generator().manual_seed(19))
        out.backward(g)
        got.backward(g)
        metrics = [metric('attention.output', out, got, 2e-6),
                   metric('attention.input_gradient', x.grad, z.grad, 2e-6)]
        for (name, p), (other, q) in zip(ref.named_parameters(), a.named_parameters()):
            self.assertEqual(name, other)
            metrics.append(metric('attention.gradient.' + name, p.grad, q.grad, 2e-6))
        (ROOT / 'evidence/attention_fp32_control.json').write_text(
            json.dumps(dict(status='PASS' if all(m['passed'] for m in metrics) else 'FAIL',
                            metrics=metrics), indent=2) + '\n', encoding='utf-8')
        self.assertTrue(all(m['passed'] for m in metrics), metrics)


if __name__ == '__main__':
    unittest.main(verbosity=2)
