"""Small native Torch36 state-carry tests; never a full-model/C2 result."""
import copy
from pathlib import Path
import sys
import unittest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'candidate'))
from full_batch_step import training_step
from sequence_core import SequenceState
from check_sequence5 import numerical_step, compare_step


class Encoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.input = torch.nn.Linear(1, 8)
        self.tf = torch.nn.TransformerEncoder(torch.nn.TransformerEncoderLayer(
            8, 2, 16, dropout=0., batch_first=True), 2, enable_nested_tensor=False)
        self.head_v = torch.nn.Linear(8, 1)
        self.head_coarse = torch.nn.Linear(8, 256)

    def forward(self, v, angles, belt, mask):
        return self.tf(self.input(v.unsqueeze(-1)), src_key_padding_mask=~mask)


class NativeSequenceTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(31)
        self.definitions = dict(Encoder=Encoder, UNet=lambda: torch.nn.Linear(2, 2))
        models = torch.nn.ModuleDict({'enc': Encoder(), 'dec': self.definitions['UNet']()})
        self.case = dict(initial=copy.deepcopy(models.state_dict()), v=torch.randn(4, 3),
            y0=torch.randn(4, 1, 16, 16), angles=None, belt=None,
            mask=torch.tensor([[1,0,1],[1,1,1],[0,1,1],[1,1,0]], dtype=torch.bool))

    def test_five_updates_carry_state_and_clear_all_previous_gradients(self):
        actual = SequenceState(torch, self.definitions, self.case, False)
        manual = SequenceState(torch, self.definitions, self.case, False)
        identity = id(actual.optimizer)
        for step in range(1, 6):
            for parameter in actual.models.parameters():
                parameter.grad = torch.full_like(parameter, 1e8)
            actual.v.grad = torch.full_like(actual.v, 1e8)
            actual.image.grad = torch.full_like(actual.image, 1e8)
            actual.begin(step)
            self.assertIsNone(actual.v.grad); self.assertIsNone(actual.image.grad)
            self.assertTrue(all(p.grad is None for p in actual.models.parameters()))
            actual.update(); actual.validate(step)
            manual.optimizer.zero_grad(set_to_none=True)
            manual.v.grad = None; manual.image.grad = None
            training_step(manual.models['enc'], manual.models['dec'], manual.optimizer,
                manual.v, None, None, manual.image, self.case['mask'])
            for left, right in zip(actual.models.parameters(), manual.models.parameters()):
                self.assertTrue(torch.equal(left, right))
                if left.grad is not None:
                    self.assertTrue(torch.equal(left.grad, right.grad))
                    for key in ('step', 'exp_avg', 'exp_avg_sq'):
                        self.assertTrue(torch.equal(actual.optimizer.state[left][key], manual.optimizer.state[right][key]))
            self.assertEqual(id(actual.optimizer), identity)
            self.assertEqual(actual.state_summary()['optimizer_step_min'], step)
            self.assertTrue(torch.equal(actual.v.grad, manual.v.grad))

    def test_five_checkpoint_updates_keep_full_original_comparisons(self):
        reference = SequenceState(torch, self.definitions, self.case, False)
        candidate = SequenceState(torch, self.definitions, self.case, True)
        previous = [state.digest() for state in (reference, candidate)]
        for step in range(1, 6):
            left, left_meta = numerical_step(reference, step)
            right, right_meta = numerical_step(candidate, step)
            self.assertEqual([left_meta['before_digest'], right_meta['before_digest']], previous)
            metrics, failures = compare_step(torch, left, right)
            self.assertFalse(failures); self.assertTrue(all(m['passed'] for m in metrics))
            self.assertTrue(all(family in {m['name'].split('.')[0] for m in metrics}
                for family in ('loss','input_v','input_y0','output','grad','param','delta','state')))
            previous = [left_meta['after_digest'], right_meta['after_digest']]

    def test_optimizer_recreation_or_skipped_update_is_rejected(self):
        state = SequenceState(torch, self.definitions, self.case, False)
        state.begin(1); state.update(); state.validate(1)
        with self.assertRaises(ValueError):
            state.begin(3)
        state.optimizer = torch.optim.AdamW(state.models.parameters(), lr=1e-4)
        with self.assertRaises(ValueError):
            state.begin(2)


if __name__ == '__main__':
    torch.set_num_threads(36)
    assert torch.get_num_threads() == 36
    print('SMALL_NATIVE_TORCH36_ONLY; no full fixed case, C2, or training-memory measurement', flush=True)
    unittest.main(verbosity=2)
