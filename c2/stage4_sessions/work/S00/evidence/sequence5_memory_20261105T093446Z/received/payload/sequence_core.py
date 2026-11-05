"""Five repeated fixed-case updates with one model and AdamW per sequence."""
import hashlib
import json
from pathlib import Path
import sys

from diagnostic_common import sha_file, tensor_sha

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
import check_equivalence as accepted
sys.path.insert(0, str(ROOT / 'candidate'))
STEPS = 5


def load_case(torch, path):
    manifest = json.loads((ROOT / 'CASE_MANIFEST.json').read_text())
    if sha_file(path) != manifest['sha256'] or path.stat().st_size != manifest['bytes']:
        raise ValueError('wrong original fixed case')
    case = torch.load(path, map_location='cpu', weights_only=True)
    digest = hashlib.sha256()
    for name, value in case['initial'].items():
        digest.update(name.encode()); digest.update(value.contiguous().numpy().tobytes())
    identity = dict(initial_weights_sha256=digest.hexdigest(), fixed_tensor_sha256={
        name: tensor_sha(case[name]) for name in ('v', 'y0', 'idx', 'mask', 't', 'noise')})
    if identity != manifest['identity'] or case['input_protocol'] != 'S02_PAIRED_BELT_V1':
        raise ValueError('wrong loaded weights/tensors/protocol')
    if case['v'].shape != (64, 208) or case['y0'].shape != (64, 1, 64, 64):
        raise ValueError('wrong full B64 case shapes')
    return case, dict(case_file_sha256=manifest['sha256'], case_identity=identity)


class SequenceState:
    def __init__(self, torch, definitions, case, checkpoint):
        from full_batch_step import enable_checkpoint, training_step
        self.torch, self.case = torch, case
        self.models = torch.nn.ModuleDict({'enc': definitions['Encoder'](), 'dec': definitions['UNet']()})
        self.models.load_state_dict(case['initial'], strict=True)
        if checkpoint:
            enable_checkpoint(self.models['enc'])
        self.optimizer = torch.optim.AdamW(self.models.parameters(), lr=1e-4, betas=(0.9, 0.999),
                                           eps=1e-8, weight_decay=0.01)
        self.model_id, self.optimizer_id = id(self.models), id(self.optimizer)
        self.v = case['v'].clone().requires_grad_()
        self.image = case['y0'].clone().requires_grad_()
        self.completed, self.pending = 0, False
        self.training_step = training_step

    def state_summary(self):
        values = [float(state['step'].item()) for state in self.optimizer.state.values()]
        return dict(completed_updates=self.completed, model_id=id(self.models), optimizer_id=id(self.optimizer),
                    optimizer_states=len(values), optimizer_step_min=min(values) if values else 0,
                    optimizer_step_max=max(values) if values else 0)

    def check_optimizer(self, expected):
        if id(self.models) != self.model_id or id(self.optimizer) != self.optimizer_id:
            raise ValueError('model or optimizer recreated within sequence')
        for name, parameter in self.models.named_parameters():
            state = self.optimizer.state.get(parameter, {})
            active = accepted.expected_gradient(name, 'pre')
            keys = {'step', 'exp_avg', 'exp_avg_sq'} if active and expected else set()
            if set(state) != keys or (keys and state['step'].item() != expected):
                raise ValueError('AdamW state/step continuity failed: ' + name)

    def begin(self, step):
        if self.pending or step != self.completed + 1 or not 1 <= step <= STEPS:
            raise ValueError('missing/repeated/out-of-order sequence update')
        self.check_optimizer(self.completed)
        before = self.state_summary()
        self.optimizer.zero_grad(set_to_none=True)
        self.v.grad = None; self.image.grad = None
        if any(p.grad is not None for p in self.models.parameters()):
            raise ValueError('previous parameter gradients were not cleared')
        self.pending = True
        return dict(**before, parameter_gradients_cleared=True, input_gradients_cleared=True)

    def update(self):
        if not self.pending:
            raise ValueError('begin/gradient cleanup required before update')
        loss = self.training_step(self.models['enc'], self.models['dec'], self.optimizer,
            self.v, self.case['angles'], self.case['belt'], self.image, self.case['mask'])
        self.completed += 1; self.pending = False
        return loss

    def validate(self, step):
        if self.completed != step or self.pending:
            raise ValueError('update did not complete')
        self.check_optimizer(step)
        for name, parameter in self.models.named_parameters():
            active = accepted.expected_gradient(name, 'pre')
            if (parameter.grad is not None) != active:
                raise ValueError('incorrect gradient presence: ' + name)
            if not self.torch.isfinite(parameter).all() or (active and not self.torch.isfinite(parameter.grad).all()):
                raise ValueError('nonfinite parameter/gradient: ' + name)
            for value in self.optimizer.state.get(parameter, {}).values():
                if not self.torch.isfinite(value).all():
                    raise ValueError('nonfinite optimizer state: ' + name)
        if any(value.grad is None or not self.torch.isfinite(value.grad).all() for value in (self.v, self.image)):
            raise ValueError('missing/nonfinite input gradient')
        return dict(**self.state_summary(), input_gradients_finite=True, parameter_gradients_finite=True,
                    optimizer_state_finite=True)

    def digest(self):
        """Strict checker only; the lightweight memory path never hashes live state."""
        digest = hashlib.sha256()
        for name, parameter in self.models.named_parameters():
            digest.update(name.encode()); digest.update(parameter.detach().contiguous().numpy().tobytes())
            for key, value in sorted(self.optimizer.state.get(parameter, {}).items()):
                digest.update(key.encode()); digest.update(value.detach().contiguous().numpy().tobytes())
        return digest.hexdigest()
