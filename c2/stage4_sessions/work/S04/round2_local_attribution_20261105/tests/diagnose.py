"""Fixed-fixture attribution, not performance or candidate acceptance."""
import copy
import json
from pathlib import Path
import platform
import sys

import torch
import torch.nn.functional as F

from common import ROOT, definitions, fixture, metric, tensor_identity
import kml_ops

R1 = ROOT.parent


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


class FixedGate(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, mask):
        ctx.save_for_backward(mask)
        return F.relu(x)

    @staticmethod
    def backward(ctx, g):
        mask, = ctx.saved_tensors
        return g * mask, None


def observe(model, data, backend=None, gate=None):
    """One unmodified loss/backward/AdamW; hooks only retain intermediates."""
    trace, hooks = {}, []
    def capture(name, tensor):
        trace[name] = tensor
        tensor.retain_grad()
        return tensor
    block = model['block']
    for name in ('norm1', 'norm2'):
        module = getattr(block, name)
        def norm_in(_m, args, key=name):
            capture(key + '_input', args[0])
        hooks.append(module.register_forward_pre_hook(norm_in))
        # Do not return the retained tensor: observation must not replace output.
        def out_hook(_m, _args, value, key=name):
            capture(key + '_fp32', value)
        hooks.append(module.register_forward_hook(out_hook))
    original_activation = block.activation
    def activation(t):
        capture('pre_relu', t)
        value = original_activation(t) if gate is None else FixedGate.apply(t, gate)
        return capture('relu_output', value)
    block.activation = activation
    old_linear = kml_ops.chain_bf16_linear
    old_attention = block._attention if backend is not None else None
    calls = []
    if backend is not None:
        def attention(qkv):
            capture('qkv_fp32', qkv)
            return old_attention(qkv)
        block._attention = attention
        def linear(x, w, b, kind):
            name = ('qkv', 'attention_out', 'linear1', 'linear2')[len(calls)]
            calls.append(name)
            if name in ('qkv', 'linear1', 'linear2'):
                capture(name + '_input', x)
            y = old_linear(x, w, b, kind)
            if name in ('qkv', 'attention_out', 'linear2'):
                capture(name, y)
            return y
        kml_ops.chain_bf16_linear = linear
    else:
        for name in ('linear1', 'linear2'):
            module = getattr(block, name)
            def in_hook(_m, args, key=name):
                capture(key + '_input', args[0])
            hooks.append(module.register_forward_pre_hook(in_hook))
        def last_hook(_m, _args, value):
            capture('linear2', value)
        hooks.append(block.linear2.register_forward_hook(last_hook))
        def attn_in(_m, args):
            capture('qkv_input', args[0])
        def attn_out(_m, _args, value):
            capture('attention_out', value[0])
        hooks.append(block.self_attn.register_forward_pre_hook(attn_in))
        hooks.append(block.self_attn.register_forward_hook(attn_out))
    x = data['x'].clone().requires_grad_()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, betas=(0.9, 0.999),
                            eps=1e-8, weight_decay=0.01)
    initial = copy.deepcopy(model.state_dict())
    steps = []
    step_hook = opt.register_step_post_hook(lambda *_: steps.append(1))
    try:
        source = x.bfloat16() if backend == 'torch_reference' else x
        capture('block_input', source)
        h = capture('block_output', block(source)).float()
        loss = F.mse_loss(model['head_v'](h)[..., 0][data['mask']], data['v'][data['mask']]) + F.mse_loss(
            model['head_coarse'](h.mean(1)), F.adaptive_avg_pool2d(data['y0'], 16).flatten(1))
        opt.zero_grad()
        loss.backward()
        values = dict(output=h.detach().clone(), loss=loss.detach().clone(), input_gradient=x.grad.clone())
        for name, p in model.named_parameters():
            assert p.grad is not None and p.grad.dtype == p.dtype == torch.float32
            values['gradient.' + name] = p.grad.detach().clone()
        opt.step()
        assert len(steps) == 1
        for name, p in model.named_parameters():
            values['parameter.' + name] = p.detach().clone()
            values['update.' + name] = p.detach() - initial[name]
            state = opt.state[p]
            assert set(state) == {'step', 'exp_avg', 'exp_avg_sq'}
            assert state['step'].item() == 1
            for key, value in state.items():
                assert value.dtype == torch.float32 and torch.isfinite(value).all()
                if key != 'step':
                    values[key + '.' + name] = value.detach().clone()
        assert all(torch.isfinite(t).all() for t in values.values())
        detached = {name: dict(value=t.detach().clone(), gradient=t.grad.detach().clone())
                    for name, t in trace.items()}
        return values, detached
    finally:
        kml_ops.chain_bf16_linear = old_linear
        if old_attention is not None:
            block._attention = old_attention
        block.activation = original_activation
        for hook in hooks:
            hook.remove()
        step_hook.remove()


def rewritten(reference, backend):
    model = copy.deepcopy(reference)
    cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
    model['block'] = cls(backend)
    model.load_state_dict(reference.state_dict(), strict=True)
    return model


def trace_metrics(ref, got):
    rows = []
    for name in ref:
        for key in ('value', 'gradient'):
            a, b = ref[name][key].float(), got[name][key].float()
            row = metric(name + '.' + key, a, b, 2e-6)
            row.update(elements=a.numel(), reference_zeros=int((a == 0).sum()),
                       candidate_zeros=int((b == 0).sum()),
                       sign_changes=int((a.sign() != b.sign()).sum()),
                       reference_abs_le_1e_3=int((a.abs() <= 1e-3).sum()))
            rows.append(row)
    return rows


def local_gradients(n, residual, w1, nweight, nbias, upstream, mask, bf16=False):
    dz = upstream.float() * mask
    gw = dz.flatten(0, 1).t() @ n.float().flatten(0, 1)
    gb = dz.sum((0, 1))
    gn = dz @ w1.float()
    if bf16:
        gn = gn.bfloat16().float()
    weight = nweight.detach().clone().requires_grad_()
    bias = nbias.detach().clone().requires_grad_()
    normalized = F.layer_norm(residual.float(), (512,), weight, bias, 1e-5)
    gweight, gbias = torch.autograd.grad(normalized, (weight, bias), gn)
    return {'block.linear1.weight': gw, 'block.linear1.bias': gb,
            'block.norm2.weight': gweight, 'block.norm2.bias': gbias}


def adamw_replay(initial, snapshots):
    """Hold initial parameters fixed, inject recorded gradients, replay one AdamW."""
    rows, exact = [], 0
    for kind, snapshot in snapshots.items():
        parameters = [torch.nn.Parameter(value.clone()) for value in initial.values()]
        opt = torch.optim.AdamW(parameters, lr=1e-4, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.01)
        for name, p in zip(initial, parameters):
            p.grad = snapshot['gradient.' + name].clone()
        opt.step()
        for name, p in zip(initial, parameters):
            for key, value in [('parameter', p.detach()), ('update', p.detach() - initial[name]),
                               ('exp_avg', opt.state[p]['exp_avg']), ('exp_avg_sq', opt.state[p]['exp_avg_sq'])]:
                assert torch.equal(value, snapshot[key + '.' + name]), (kind, key, name)
                exact += 1
            assert opt.state[p]['step'].item() == 1
            g, r = p.grad, snapshots['reference']['gradient.' + name]
            row = dict(mode=kind, name=name, elements=g.numel(),
                       gradient=metric(name, r, g, 0.02),
                       gradient_sign_changes=int((g.sign() != r.sign()).sum()),
                       reference_abs_le_eps=int((r.abs() <= 1e-8).sum()),
                       candidate_abs_le_eps=int((g.abs() <= 1e-8).sum()),
                       update=metric(name, snapshots['reference']['update.' + name],
                                     snapshot['update.' + name], 0.05))
            if name == 'block.self_attn.in_proj_bias':
                # Key bias should cancel in exact arithmetic; show its own scale,
                # rather than hiding it inside the packed Q/K/V gradient norm.
                a, b = r[512:1024], g[512:1024]
                row['key_bias_slice'] = dict(reference_norm=a.double().norm().item(),
                    candidate_norm=b.double().norm().item(), reference_max_abs=a.abs().max().item(),
                    candidate_max_abs=b.abs().max().item(),
                    reference_update_norm=snapshots['reference']['update.' + name][512:1024].double().norm().item(),
                    candidate_update_norm=snapshot['update.' + name][512:1024].double().norm().item())
            rows.append(row)
    return dict(exact_parameter_delta_moment_tensors=exact, replayed_modes=list(snapshots),
                diagnostic_optimizer_steps=len(snapshots), steps_per_optimizer=1, rows=rows)


def epilogue_probe(initial, trace):
    x = trace['linear1_input']['value'].flatten(0, 1)
    w, b = initial['block.linear1.weight'], initial['block.linear1.bias']
    ref = trace['pre_relu']['value'].flatten(0, 1)
    fused = torch.addmm(b, x, w.t())
    split = (x @ w.t()).add_(b)
    return dict(original_F_linear_matches_addmm=bool(torch.equal(ref, fused)),
                split_mm_add_matches_original=bool(torch.equal(ref, split)),
                split_vs_fused=metric('linear1.split_vs_fused', ref, split, 2e-6),
                changed_relu_gates=int(((ref > 0) != (split > 0)).sum()),
                conclusion='Same operands; only fp32 fused vs split bias epilogue differs.')


def main():
    torch.set_num_threads(2)
    model, data = fixture()
    old = json.loads((R1 / 'evidence/block_numeric.json').read_text())
    assert {k: tensor_identity(t) for k, t in data.items()} == old['fixture']
    assert {k: tensor_identity(t) for k, t in model.state_dict().items()} == old['initial']
    initial = copy.deepcopy(model.state_dict())
    control_model = rewritten(model, 'torch_fp32_control')
    bf_model = rewritten(model, 'torch_reference')
    ref, rt = observe(model, data)
    control, ct = observe(control_model, data, 'torch_fp32_control')
    bf, bt = observe(bf_model, data, 'torch_reference')
    fp32 = compare(ref, control, fp32=True)
    quantized = compare(ref, bf)
    assert quantized['metrics'] == [dict(row, same_dtype=True) for row in old['metrics']], 'R1 replay changed'
    save = lambda name, value: (ROOT / 'evidence' / name).write_text(
        json.dumps(value, indent=2) + '\n', encoding='utf-8')
    save('fp32_control.json', fp32)
    save('bf16_replay.json', dict(quantized, identical_R1_metrics=True))
    save('intermediate_metrics.json', dict(fp32=trace_metrics(rt, ct), bf16=trace_metrics(rt, bt)))
    refmask = rt['pre_relu']['value'] > 0
    bfmask = bt['pre_relu']['value'] > 0
    crossing = refmask != bfmask
    samples = []
    for index in crossing.nonzero().tolist():
        key = tuple(index)
        samples.append(dict(index=index, reference=float(rt['pre_relu']['value'][key]),
                            candidate=float(bt['pre_relu']['value'][key]),
                            reference_upstream=float(rt['relu_output']['gradient'][key]),
                            candidate_upstream=float(bt['relu_output']['gradient'][key])))
    save('relu_gate_changes.json', dict(elements=refmask.numel(), changed=int(crossing.sum()),
         reference_active=int(refmask.sum()), candidate_active=int(bfmask.sum()), samples=samples))
    kwargs = dict(n=rt['linear1_input']['value'], residual=rt['norm2_input']['value'],
                  w1=initial['block.linear1.weight'], nweight=initial['block.norm2.weight'],
                  nbias=initial['block.norm2.bias'], upstream=rt['relu_output']['gradient'])
    local_ref = local_gradients(**kwargs, mask=refmask)
    gate_only = local_gradients(**kwargs, mask=bfmask)
    local_bf = local_gradients(bt['linear1_input']['value'], bt['norm2_input']['value'],
                              initial['block.linear1.weight'].bfloat16(), initial['block.norm2.weight'],
                              initial['block.norm2.bias'], bt['relu_output']['gradient'], bfmask, bf16=True)
    local = []
    for name in local_ref:
        local.append(dict(name=name,
            reference_reconstruction=metric(name, ref['gradient.' + name], local_ref[name], 2e-6),
            bf16_reconstruction=metric(name, bf['gradient.' + name], local_bf[name], 2e-6),
            gate_only_error=metric(name, local_ref[name], gate_only[name], 0.02),
            actual_bf16_error=metric(name, ref['gradient.' + name], bf['gradient.' + name], 0.02),
            gate_only_vs_actual_delta=metric(name, bf['gradient.' + name] - ref['gradient.' + name],
                                             gate_only[name] - local_ref[name], 0.02)))
    save('local_vjp.json', local)
    fresh, _ = fixture()
    restored, _ = observe(rewritten(fresh, 'torch_reference'), data, 'torch_reference', refmask)
    assert torch.equal(restored['output'], bf['output']) and torch.equal(restored['loss'], bf['loss'])
    save('gate_restored_counterfactual.json', dict(compare(ref, restored), forward_unchanged=True,
        diagnostic_only='Not the true derivative of quantized ReLU; not a candidate fix.'))
    save('linear1_fp32_epilogue.json', epilogue_probe(initial, rt))
    save('adamw_replay.json', adamw_replay(initial, dict(reference=ref, fp32_control=control,
                                                       bf16=bf, restored_gate=restored)))
    raw = bt['qkv_fp32']['gradient']
    rounded = bt['qkv']['gradient'].float()
    assert torch.equal(raw.bfloat16().float(), rounded)
    raw_bias, rounded_bias = raw.flatten(0, 1).sum(0), rounded.flatten(0, 1).sum(0)
    assert torch.equal(rounded_bias, bf['gradient.block.self_attn.in_proj_bias'])
    save('key_bias_rounding.json', dict(
        bf16_cast_exactly_reproduces_saved_qkv_gradient=True,
        rounded_sum_exactly_reproduces_actual_bias_gradient=True,
        before_quantization_key_bias_norm=raw_bias[512:1024].double().norm().item(),
        after_quantization_key_bias_norm=rounded_bias[512:1024].double().norm().item(),
        before_quantization_key_bias_max_abs=raw_bias[512:1024].abs().max().item(),
        after_quantization_key_bias_max_abs=rounded_bias[512:1024].abs().max().item()))
    selected = ('norm2_input', 'norm2_fp32', 'linear1_input', 'pre_relu', 'relu_output', 'linear2')
    torch.save(dict(reference={k: rt[k] for k in selected}, bf16={k: bt[k] for k in selected}),
               ROOT / 'evidence/intermediates.pt')
    result = dict(round='S04_R2', status='DIAGNOSIS_COMPLETED_NOT_ACCEPTED',
        fp32=dict(checks=fp32['checks'], failed=fp32['failed']),
        bf16=dict(checks=quantized['checks'], failed=quantized['failed'], R1_exact_replay=True),
        relu_gate_changes=int(crossing.sum()),
        counterfactual_failed=sum(not m['passed'] for m in compare(ref, restored)['metrics']),
        environment=dict(python=sys.executable, torch=torch.__version__, platform=platform.platform(), threads=2),
        fixture_unchanged=True, initial_weights_unchanged=True, jobs=0, performance='NOT_RUN')
    save('summary.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
