"""One aligned fp32 attempt and one unchanged-bf16 regression; no timing."""
import copy
import hashlib
import inspect
import json
import platform
import sys
from unittest.mock import patch

import torch
import torch.nn.functional as F

from common import ROOT, definitions, fixture, metric, tensor_identity

S04 = ROOT.parent
R2 = S04 / 'round2_local_attribution_20261105'


def limits(name):
    return 0.05 if name.startswith('update.') else 0.04 if name.startswith('exp_avg_sq.') else (
        0.02 if name.startswith(('gradient.', 'exp_avg.')) or name == 'input_gradient' else 0.01)


def compare(ref, got, fp32=False):
    assert set(ref) == set(got)
    metrics = []
    for name, value in ref.items():
        row = metric(name, value, got[name], 2e-6 if fp32 else limits(name))
        if fp32:
            absolute = 2e-6 if name.startswith(('exp_avg.', 'exp_avg_sq.')) else 2e-5
            row.update(max_abs_limit=absolute, passed=row['max_abs'] <= absolute and
                       (row['reference_norm'] <= 1e-8 or row['l2_relative'] <= 2e-6))
        row['same_dtype'] = value.dtype == got[name].dtype
        row['passed'] = row['passed'] and row['same_dtype']
        metrics.append(row)
    return dict(checks=len(metrics), failed=sum(not r['passed'] for r in metrics), metrics=metrics)


def rewritten(reference, backend):
    model = copy.deepcopy(reference)
    cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
    model['block'] = cls(backend)
    model.load_state_dict(reference.state_dict(), strict=True)
    return model


def step(model, data, backend=None):
    initial = copy.deepcopy(model.state_dict())
    x = data['x'].clone().requires_grad_()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, betas=(0.9, 0.999),
                            eps=1e-8, weight_decay=0.01)
    steps = []
    hook = opt.register_step_post_hook(lambda *_: steps.append(1))
    source = x.bfloat16() if backend == 'torch_reference' else x
    try:
        if backend == 'torch_fp32_control':
            with patch.object(torch.nn.TransformerEncoderLayer, 'forward', side_effect=AssertionError('whole reference block forbidden')), \
                    patch.object(torch.nn.MultiheadAttention, 'forward', side_effect=AssertionError('whole reference MHA forbidden')):
                h = model['block'](source).float()
        else:
            h = model['block'](source).float()
        loss = F.mse_loss(model['head_v'](h)[..., 0][data['mask']], data['v'][data['mask']]) + F.mse_loss(
            model['head_coarse'](h.mean(1)), F.adaptive_avg_pool2d(data['y0'], 16).flatten(1))
        opt.zero_grad()
        loss.backward()
        assert x.grad is not None and x.grad.dtype == torch.float32
        values = dict(output=h.detach().clone(), loss=loss.detach().clone(), input_gradient=x.grad.clone())
        for name, p in model.named_parameters():
            assert p.grad is not None and p.grad.dtype == p.dtype == torch.float32
            values['gradient.' + name] = p.grad.detach().clone()
        opt.step()
        assert len(steps) == 1 and set(model.state_dict()) == set(initial)
        for name, p in model.named_parameters():
            values['parameter.' + name] = p.detach().clone()
            values['update.' + name] = p.detach() - initial[name]
            state = opt.state[p]
            assert set(state) == {'step', 'exp_avg', 'exp_avg_sq'} and state['step'].item() == 1
            for key, value in state.items():
                assert value.dtype == torch.float32 and torch.isfinite(value).all()
                if key != 'step':
                    values[key + '.' + name] = value.detach().clone()
        assert all(torch.isfinite(t).all() for t in values.values())
        return values
    finally:
        hook.remove()


def save(name, value):
    (ROOT / 'evidence' / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    torch.set_num_threads(2)
    model, data = fixture()
    old = json.loads((S04 / 'evidence/block_numeric.json').read_text())
    assert {k: tensor_identity(t) for k, t in data.items()} == old['fixture']
    assert {k: tensor_identity(t) for k, t in model.state_dict().items()} == old['initial']
    aligned = rewritten(model, 'torch_fp32_control')
    bf16 = rewritten(model, 'torch_reference')
    ref = step(model, data)
    got = step(aligned, data, 'torch_fp32_control')
    replay = step(bf16, data, 'torch_reference')
    result, regression = compare(ref, got, fp32=True), compare(ref, replay)
    assert regression['metrics'] == [dict(row, same_dtype=True) for row in old['metrics']]
    assert regression['metrics'] == json.loads((R2 / 'evidence/bf16_replay.json').read_text())['metrics']
    save('fp32_aligned.json', result)
    save('bf16_unchanged.json', dict(regression, exact_R1_R2_metrics=True))
    before = json.loads((R2 / 'evidence/fp32_control.json').read_text())
    assert [r['name'] for r in before['metrics']] == [r['name'] for r in result['metrics']]
    transitions = [dict(name=a['name'], previous=a, current=b) for a, b in zip(before['metrics'], result['metrics'])]
    old_failures = [t for t in transitions if not t['previous']['passed']]
    new_failures = [t for t in transitions if t['previous']['passed'] and not t['current']['passed']]
    save('failure_transitions.json', dict(original_seven=old_failures, newly_failed=new_failures,
                                       all_83_statuses=[dict(name=t['name'], R2=t['previous']['passed'],
                                                            R3=t['current']['passed']) for t in transitions]))
    functions = []
    for fn in (F._in_projection_packed, F.multi_head_attention_forward,
               torch.nn.MultiheadAttention.forward, torch.nn.TransformerEncoderLayer.forward):
        source = inspect.getsource(fn)
        path = inspect.getsourcefile(fn)
        functions.append(dict(name=fn.__qualname__, path=path, first_line=inspect.getsourcelines(fn)[1],
                              function_sha256=hashlib.sha256(source.encode()).hexdigest(),
                              file_sha256=hashlib.sha256(open(path, 'rb').read()).hexdigest()))
    save('torch_source_identity.json', dict(torch=torch.__version__, functions=functions,
         private_API='F._in_projection_packed: local diagnostic dependency, not a portable backend acceptance'))
    summary = dict(round='S04_R3', status='PASS_LOCAL_FP32_CONTROL_ONLY' if not result['failed'] else 'FAIL_STOP_NO_MORE_ALIGNMENT',
        alignment_attempts=1, fp32_checks=result['checks'], fp32_failed=result['failed'],
        old_seven_resolved=sum(t['current']['passed'] for t in old_failures), newly_failed=len(new_failures),
        all_83_bitwise_equal=all(torch.equal(ref[k], got[k]) for k in ref),
        bf16_checks=regression['checks'], bf16_failed=regression['failed'], bf16_exact_R1_R2_replay=True,
        environment=dict(python=sys.executable, torch=torch.__version__, torch_file=torch.__file__,
                         platform=platform.platform(), threads=torch.get_num_threads()),
        input_and_initial_weight_sha_unchanged=True, whole_reference_block_and_MHA_forbidden=True,
        gradients_from='native autograd, no reference gradient/mask injection',
        cluster_jobs=0, full_model_runs=0, performance='NOT_RUN')
    save('summary.json', summary)
    print(json.dumps(summary, indent=2))
    return int(bool(result['failed']))


if __name__ == '__main__':
    sys.exit(main())
