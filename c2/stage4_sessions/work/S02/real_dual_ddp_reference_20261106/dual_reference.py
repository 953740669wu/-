"""Fixed real-engineering shards/masks and original complete B64 strict reference."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import random

from data_gate import engineering_data as data
import engineering_training as training
import profile_contract
from diagnostic_common import configure_backend, finish_backend

ROOT = Path(__file__).resolve().parent
DESCRIPTOR_SHA256 = 'b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
FIRST5 = json.loads((ROOT / 'REFERENCE_FIRST5.json').read_text())
EPOCH25 = json.loads((ROOT / 'REFERENCE_EPOCH25.json').read_text())
_spec = importlib.util.spec_from_file_location('s02_dual_accepted', ROOT / 'tests/check_equivalence.py')
accepted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(accepted)


def validate_partition(global_indices, rank_indices):
    if (len(global_indices) != 64 or any(type(x) is not int for x in global_indices) or
            len(set(global_indices)) != 64 or rank_indices != [global_indices[:32], global_indices[32:]]):
        raise ValueError('exact ordered first32/last32 disjoint partition required')


def plan(step):
    if type(step) is not int or not 1 <= step <= 25:
        raise ValueError('original epoch steps 1..25 only')
    order = list(range(1600)); random.Random(0).shuffle(order)
    indices = order[(step - 1) * 64:step * 64]
    expected = EPOCH25['steps'][step - 1]
    if len(EPOCH25['steps']) != 25 or expected['step'] != step or expected['frame_indices'] != indices:
        raise ValueError('frozen original25 epoch identity differs')
    ranks = [indices[:32], indices[32:]]
    validate_partition(indices, ranks)
    return dict(step=step, global_indices=indices, rank_indices=ranks,
                expected_mask_sha256=expected['mask_sha256'],
                expected_frame_ids_sha256=expected['frame_ids_sha256'])


def check_identity(step, frame_ids, mask):
    expected = plan(step)
    if (len(frame_ids) != 64 or tuple(mask.shape) != (64, 208) or str(mask.dtype) != 'torch.bool' or
            profile_contract.identity(frame_ids) != expected['expected_frame_ids_sha256'] or
            hashlib.sha256(mask.detach().contiguous().numpy().tobytes()).hexdigest() != expected['expected_mask_sha256']):
        raise ValueError('original global frame/mask identity differs; no resampling')


def load_data(descriptor_path, descriptor_sha256, ledger_path):
    if descriptor_sha256 != DESCRIPTOR_SHA256:
        raise ValueError('original engineering descriptor SHA required')
    metadata = data.load_descriptor(descriptor_path, descriptor_sha256)
    description = metadata['description']
    profile_contract.check_data(description, FIRST5)
    path = Path(ledger_path)
    if not path.is_absolute() or path.resolve() in {
            Path(description['runtime_exposure_ledger_path']).resolve(),
            Path(description['exposure_ledger']['path']).resolve()}:
        raise ValueError('new owned absolute per-rank exposure ledger required')
    ledger = data.Exposure(path, description)
    loaded = data.load_arrays(metadata, ledger)
    normalization = dict(image_scale=loaded['image_scale'], scope=loaded['normalization_scope'],
                         fit_partition='train', train_units=[x['unit'] for x in metadata['units']['train']])
    if len(loaded['train']['v']) != 1600 or normalization != FIRST5['normalization']:
        raise ValueError('original1600 frames/train-only normalization required')
    return metadata, loaded, normalization, ledger


def initialize(torch):
    import numpy as np
    torch.manual_seed(0); np.random.seed(0); random.seed(0)
    definitions = accepted.model_definitions(torch)
    model = definitions['Encoder']()
    opt = training.optimizer(torch, model)
    angles = definitions['protocol_angles'](16, 1)
    identity = dict(parameters=sum(p.numel() for p in model.parameters()),
                    initial_weights_sha256=training.model_sha(model), train_seed=0)
    if identity['parameters'] != 37995777 or identity['initial_weights_sha256'] != FIRST5['initialization']['initial_weights_sha256']:
        raise ValueError('full original seed0 Encoder initialization differs')
    if any(p.dtype != torch.float32 or p.device.type != 'cpu' for p in model.parameters()):
        raise ValueError('original CPU fp32 parameters required')
    return model, opt, angles, torch.get_rng_state().clone(), identity


class MaskStream:
    def __init__(self, torch, post_init_rng_state):
        self.torch = torch
        self.post_init_state = post_init_rng_state.clone()
        self.generator = torch.Generator(device='cpu').set_state(self.post_init_state)
        self.next_step = 1

    def next(self, step):
        if step != self.next_step:
            raise ValueError('mask stream cursor differs')
        expected = plan(step)
        mask = self.torch.rand(64, 208, generator=self.generator) < .5
        if hashlib.sha256(mask.numpy().tobytes()).hexdigest() != expected['expected_mask_sha256']:
            raise ValueError('original post-init mask stream differs; stop without reseeding')
        self.next_step += 1
        return mask

    def state_dict(self):
        return dict(next_step=self.next_step, post_init_state=self.post_init_state.clone(),
                    generator_state=self.generator.get_state().clone())

    def load_state_dict(self, value):
        step = value['next_step']
        if (type(step) is not int or not 1 <= step <= 26 or
                not self.torch.equal(value['post_init_state'], self.post_init_state)):
            raise ValueError('mask restore initial state/cursor mismatch')
        expected = self.torch.Generator(device='cpu').set_state(self.post_init_state)
        for _ in range(step - 1):
            self.torch.rand(64, 208, generator=expected)
        if not self.torch.equal(expected.get_state(), value['generator_state']):
            raise ValueError('mask restore generator state/cursor mismatch')
        self.generator.set_state(value['generator_state']); self.next_step = step


def new_mask_stream(torch, post_init_rng_state):
    return MaskStream(torch, post_init_rng_state)


def shard(torch, global_values, global_mask, rank):
    if (type(rank) is not int or rank not in (0, 1) or len(global_values) != 4 or
            any(v.shape[0] != 64 for v in global_values) or global_mask.shape != global_values[0].shape or
            global_mask.dtype != torch.bool):
        raise ValueError('two ordered32 shards of complete64 required')
    start = rank * 32
    values = tuple(v[start:start + 32].detach().clone().contiguous() for v in global_values)
    return values, global_mask[start:start + 32].clone().contiguous()


@contextmanager
def _isolated_rng(torch):
    before = training.rng_state(torch)
    try:
        yield
    finally:
        training.restore_rng(torch, before)


def _historical_loss_check(torch, step, losses, metrics, role):
    for key in ('total', 'voltage', 'coarse'):
        accepted.compare(torch, f'{role}.{step}.baseline_loss.{key}',
                         torch.tensor(FIRST5['steps'][step - 1]['losses'][key], dtype=torch.float32),
                         losses[key], 'tensor', metrics)


class B64Reference:
    def __init__(self, torch):
        self.torch = torch
        with _isolated_rng(torch):
            self.model, self.opt, self.angles, _, self.initialization = initialize(torch)
        self.initial = {n: p.detach().clone() for n, p in self.model.named_parameters()}
        self.last_step = 0
        self.pending = None
        self.closed = False

    def advance(self, step, global_values, global_mask, metrics):
        if self.closed or self.pending is not None or type(step) is not int or step != self.last_step + 1 or not 1 <= step <= 5:
            raise ValueError('reference sequential five updates only; release each compared step')
        if global_values[0].shape[0] != 64 or global_mask.shape != global_values[0].shape:
            raise ValueError('complete B64 reference required; never B32x2')
        torch = self.torch
        values = tuple(v.detach().clone() for v in global_values)
        outputs = {}
        def capture(key):
            def hook(_module, _args, value): outputs[key] = value.detach().clone()
            return hook
        handles = [m.register_forward_hook(capture(k)) for k, m in
                   [('h', self.model), ('v', self.model.head_v), ('coarse', self.model.head_coarse)]]
        try:
            with _isolated_rng(torch):
                losses = training.train_step(torch, self.model, self.opt, values, global_mask)
                training.validate_update(torch, self.model, self.opt, values, step)
                _historical_loss_check(torch, step, losses, metrics, 'reference')
            self.pending = dict(outputs=outputs, losses=losses,
                                input_grads=[values[i].grad.detach().clone() for i in (0, 1)])
        finally:
            for h in handles: h.remove()
        return self.pending

    def compare(self, step, ddp_encoder, ddp_optimizer, got, metrics):
        if self.closed or self.pending is None or step != self.last_step + 1:
            raise ValueError('matching pending reference step required')
        torch = self.torch
        a, b = dict(self.model.named_parameters()), dict(ddp_encoder.named_parameters())
        if set(a) != set(b) or set(self.initial) != set(a):
            raise ValueError('all original canonical Encoder/head parameter names required')
        group = ddp_optimizer.param_groups
        if len(group) != 1 or len(group[0]['params']) != len(b) or {id(p) for p in group[0]['params']} != {id(p) for p in b.values()}:
            raise ValueError('optimizer must cover each canonical parameter exactly once')
        if {k: v for k, v in group[0].items() if k != 'params'} != {k: v for k, v in self.opt.param_groups[0].items() if k != 'params'}:
            raise ValueError('original AdamW hyperparameters required')
        for field, names in [('outputs', {'h', 'v', 'coarse'}), ('losses', {'total', 'voltage', 'coarse'})]:
            if set(got[field]) != names:
                raise ValueError('complete global outputs/losses required')
            for key in sorted(names):
                accepted.compare(torch, f'{step}.{field}.{key}', self.pending[field][key], got[field][key], 'tensor', metrics)
        _historical_loss_check(torch, step, got['losses'], metrics, 'ddp')
        if len(got['input_grads']) != 2 or any(v is None for v in got['input_grads']):
            raise ValueError('both global concatenated raw input gradients required')
        for i in (0, 1):
            accepted.compare(torch, f'{step}.input_grad.{i}', self.pending['input_grads'][i], got['input_grads'][i] / 2, 'tensor', metrics)
        for name, p in a.items():
            q = b[name]
            if p.grad is None or q.grad is None:
                raise ValueError('missing canonical parameter gradient: ' + name)
            for key, left, right in [('grad', p.grad, q.grad), ('param', p.detach(), q.detach()),
                                     ('delta', p.detach() - self.initial[name], q.detach() - self.initial[name])]:
                accepted.compare(torch, f'{step}.{key}.{name}', left, right, 'tensor', metrics)
            sa, sb = self.opt.state[p], ddp_optimizer.state[q]
            if set(sa) != {'step', 'exp_avg', 'exp_avg_sq'} or set(sa) != set(sb):
                raise ValueError('complete original AdamW state required: ' + name)
            for key in sa:
                accepted.compare(torch, f'{step}.state.{name}.{key}', sa[key], sb[key], 'exact' if key == 'step' else 'state', metrics)
        aa, bb = self.model.state_dict(), ddp_encoder.state_dict()
        if set(aa) != set(bb):
            raise ValueError('complete original model state keys required')
        for name in sorted(set(aa) - set(a)):
            accepted.compare(torch, f'{step}.buffer.{name}', aa[name], bb[name], 'tensor', metrics)
        self.last_step = step
        self.pending = None
        self.opt.zero_grad(set_to_none=True)

    def close(self):
        if self.opt is not None: self.opt.zero_grad(set_to_none=True)
        self.pending = None; self.initial.clear()
        self.model = self.opt = self.angles = None
        self.closed = True
