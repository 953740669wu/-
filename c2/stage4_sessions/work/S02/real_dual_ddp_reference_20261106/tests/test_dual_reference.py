"""New reference/shard contract checks; tiny models do not establish C2 acceptance."""
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dual_reference as ref


class TinyEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.val = torch.nn.Linear(1, 2)
        self.head_v = torch.nn.Linear(2, 1)
        self.head_coarse = torch.nn.Linear(2, 256)

    def forward(self, v, angles, belt, mask):
        return self.val(v[..., None])


def tiny_initialize(torch):
    torch.manual_seed(0); np.random.seed(0); random.seed(0)
    model = TinyEncoder()
    return model, ref.training.optimizer(torch, model), None, torch.get_rng_state().clone(), {}


def tiny_values():
    v = torch.linspace(-.1, .1, 64 * 2).reshape(64, 2)
    image = torch.linspace(-.2, .2, 64 * 16 * 16).reshape(64, 1, 16, 16)
    return (v, image, torch.zeros(64, 2, 4), torch.zeros(64, 2))


class ReferenceTests(unittest.TestCase):
    def test_01_original_25_order_and_partition_rejections(self):
        order = list(range(1600)); random.Random(0).shuffle(order)
        combined = []
        for step in range(1, 26):
            p = ref.plan(step)
            self.assertEqual(p['global_indices'], order[(step - 1) * 64:step * 64])
            self.assertEqual(p['rank_indices'], [p['global_indices'][:32], p['global_indices'][32:]])
            ref.validate_partition(p['global_indices'], p['rank_indices'])
            combined += p['global_indices']
        self.assertEqual(sorted(combined), list(range(1600)))
        p = ref.plan(1)
        for ranks in ([p['rank_indices'][0], p['rank_indices'][0]],
                      [p['rank_indices'][0][:-1], p['rank_indices'][1]],
                      [p['rank_indices'][1], p['rank_indices'][0]]):
            with self.assertRaises(ValueError): ref.validate_partition(p['global_indices'], ranks)
        for step in (0, 26, True):
            with self.assertRaises(ValueError): ref.plan(step)

    def test_02_full_original_init_and_all_masks_isolated(self):
        # Full original initialization only: no Encoder forward/train or real input read.
        torch.manual_seed(0); np.random.seed(0); random.seed(0)
        definitions = ref.accepted.model_definitions(torch)
        model = definitions['Encoder']()
        state = torch.get_rng_state().clone()
        angles = definitions['protocol_angles'](16, 1)
        self.assertEqual(sum(p.numel() for p in model.parameters()), 37995777)
        named = dict(model.named_parameters())
        self.assertEqual(len(named), 153)
        self.assertTrue({'head_v.weight', 'head_v.bias', 'head_coarse.weight', 'head_coarse.bias'} <= set(named))
        original_opt = ref.training.optimizer(torch, model)
        self.assertEqual({id(p) for p in original_opt.param_groups[0]['params']}, {id(p) for p in named.values()})
        digest = ref.training.model_sha(model)
        if sys.platform == 'win32':
            # First failure is retained separately. Runtime guard remains strict;
            # these checks validate original masks without claiming C2 init PASS.
            self.assertEqual(digest, '411aa36f4d120512d7de6e6646733ea898a99531144cac84688a9ef1c2a567dd')
            with self.assertRaisesRegex(ValueError, 'initialization differs'):
                ref.initialize(torch)
        else:
            self.assertEqual(digest, ref.FIRST5['initialization']['initial_weights_sha256'])
            checked, opt, _, checked_state, _ = ref.initialize(torch)
            self.assertTrue(torch.equal(state, checked_state))
            del checked, opt
        self.assertEqual(tuple(angles.shape), (208, 4))
        stream = ref.new_mask_stream(torch, state)
        for step in range(1, 26):
            torch.rand(3)  # DDP/extra construction may use process RNG.
            before = torch.get_rng_state().clone()
            mask = stream.next(step)
            self.assertTrue(torch.equal(before, torch.get_rng_state()))
            self.assertEqual(hashlib.sha256(mask.numpy().tobytes()).hexdigest(), ref.plan(step)['expected_mask_sha256'])
            if step == 8:
                restored = ref.new_mask_stream(torch, state)
                restored.load_state_dict(stream.state_dict())
        self.assertEqual(stream.next_step, 26)
        with self.assertRaises(ValueError): stream.next(26)
        with self.assertRaises(ValueError): restored.next(8)
        self.assertEqual(hashlib.sha256(restored.next(9).numpy().tobytes()).hexdigest(), ref.plan(9)['expected_mask_sha256'])
        changed = dict(restored.state_dict()); changed['post_init_state'] = state.clone(); changed['post_init_state'][0] ^= 1
        with self.assertRaises(ValueError): restored.load_state_dict(changed)
        del model, named, original_opt, stream, restored

    def test_03_shard_order_and_independent_leaves(self):
        values = tiny_values(); mask = torch.arange(128).reshape(64, 2) % 3 == 0
        pieces = [ref.shard(torch, values, mask, rank) for rank in (0, 1)]
        for i in range(4): self.assertTrue(torch.equal(torch.cat([x[0][i] for x in pieces]), values[i]))
        self.assertTrue(torch.equal(torch.cat([x[1] for x in pieces]), mask))
        for local, local_mask in pieces:
            self.assertTrue(local[0].is_leaf and local[1].is_leaf)
            self.assertNotEqual(local[0].untyped_storage().data_ptr(), values[0].untyped_storage().data_ptr())
            self.assertTrue(local_mask.is_contiguous())
        for rank in (-1, 2, True):
            with self.assertRaises(ValueError): ref.shard(torch, values, mask, rank)

    def test_04_identity_checks_and_original_comparator_failure(self):
        for bad in (torch.zeros(64, 208, dtype=torch.bool), torch.zeros(63, 208, dtype=torch.bool)):
            with self.assertRaises(ValueError): ref.check_identity(1, [], bad)
        raw = (ROOT / 'tests/check_equivalence.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e')
        with self.assertRaises(AssertionError): ref.accepted.compare(torch, 'original_limit', torch.zeros(1), torch.tensor([3e-5]), 'tensor', [])
        with self.assertRaises(AssertionError): ref.accepted.compare(torch, 'missing', torch.ones(1), None, 'tensor', [])

    def test_05_five_continuous_tiny_adamw_and_rng_release(self):
        metrics = []
        with patch.object(ref, 'initialize', tiny_initialize):
            peer, opt, _, _, _ = tiny_initialize(torch)
            before = ref.training.rng_state(torch)
            reference = ref.B64Reference(torch)
            self.assertTrue(ref.training.exact(torch, before, ref.training.rng_state(torch)))
            mask = torch.ones(64, 2, dtype=torch.bool)
            for step in range(1, 6):
                values = tiny_values()
                before = ref.training.rng_state(torch)
                with patch.object(ref, '_historical_loss_check'):
                    expected = reference.advance(step, values, mask, metrics)
                self.assertTrue(ref.training.exact(torch, before, ref.training.rng_state(torch)))
                pvalues = tuple(v.clone().detach() for v in values)
                captured = {}
                handles = [module.register_forward_hook(lambda _m, _a, out, k=key: captured.__setitem__(k, out.detach().clone()))
                           for key, module in [('h', peer), ('v', peer.head_v), ('coarse', peer.head_coarse)]]
                losses = ref.training.train_step(torch, peer, opt, pvalues, mask)
                for h in handles: h.remove()
                got = dict(outputs=captured, losses=losses, input_grads=[pvalues[i].grad * 2 for i in (0, 1)])
                with patch.object(ref, '_historical_loss_check'):
                    reference.compare(step, peer, opt, got, metrics)
                self.assertIsNone(reference.pending)
                self.assertTrue(all(p.grad is None for p in reference.model.parameters()))
                self.assertTrue(all(opt.state[p]['step'].item() == step for p in peer.parameters()))
                del expected
            with self.assertRaises(ValueError): reference.advance(6, tiny_values(), mask, metrics)
            reference.close()
            self.assertIsNone(reference.model); self.assertIsNone(reference.opt)
            self.assertEqual(reference.initial, {})
        self.assertTrue(metrics and all(x['passed'] and x['max_abs'] == 0 for x in metrics))
        (ROOT / 'evidence/tiny_adamw_metrics.json').write_text(json.dumps(dict(
            scope='TINY_NATIVE_TORCH_B64_VS_IDENTICAL_B64_WITH_RAW_INPUT_GRADS_X2_NOT_DDP_OR_KML',
            completed_steps=5, metric_count=len(metrics), metrics=metrics), indent=2) + '\n', encoding='utf-8')

    def test_06_missing_parameter_or_input_scale_rejected(self):
        for kind in ('parameter', 'input_scale'):
            with patch.object(ref, 'initialize', tiny_initialize):
                reference = ref.B64Reference(torch)
                with patch.object(ref, '_historical_loss_check'):
                    expected = reference.advance(1, tiny_values(), torch.ones(64, 2, dtype=torch.bool), [])
                got = dict(outputs=expected['outputs'], losses=expected['losses'], input_grads=expected['input_grads'])
                if kind == 'parameter':
                    peer = TinyEncoder(); peer.extra = torch.nn.Parameter(torch.zeros(1)); opt = ref.training.optimizer(torch, peer)
                else: peer, opt = reference.model, reference.opt
                with self.assertRaises((AssertionError, ValueError)):
                    reference.compare(1, peer, opt, got, [])
                reference.close()

    def test_07_data_anchor_refusal_and_new_ledger(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence', prefix='data_contract_') as temp:
            path = Path(temp) / 'ledger.json'
            with self.assertRaises(ValueError): ref.load_data(None, 'untrusted', path)
            d = dict(corpus=ref.FIRST5['corpus'], train=ref.FIRST5['units'],
                     runtime_exposure_ledger_path=str(path), exposure_ledger=dict(path=str(path.with_name('old.json'))))
            metadata = dict(description=d, units=dict(train=d['train'], val=[]))
            with patch.object(ref.data, 'load_descriptor', return_value=metadata):
                with self.assertRaises(ValueError): ref.load_data('ignored', ref.DESCRIPTOR_SHA256, path)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    (ROOT / 'evidence').mkdir(exist_ok=True)
    torch.set_num_threads(2)
    unittest.main(failfast=True, verbosity=2)
