"""One original-size block, fresh AdamW, fixed local fixture. Exit 1 on numeric FAIL."""
import argparse
import copy
import json
import platform
import sys

import torch
import torch.nn.functional as F

from common import ROOT, definitions, fixture, metric, tensor_identity


def run():
    torch.set_num_threads(2)
    ref, data = fixture()
    initial = copy.deepcopy(ref.state_dict())
    got = copy.deepcopy(ref)
    cls = definitions('candidate', ['BF16EncoderBlock'])['BF16EncoderBlock']
    got['block'] = cls('torch_reference')
    got.load_state_dict(initial, strict=True)
    results = []
    for model, candidate in ((ref, False), (got, True)):
        x = data['x'].clone().requires_grad_()
        opt = torch.optim.AdamW(model.parameters(), lr=1e-4, betas=(0.9, 0.999),
                                eps=1e-8, weight_decay=0.01)
        calls = []
        hook = opt.register_step_post_hook(lambda *_: calls.append(1))
        h = model['block'](x.bfloat16() if candidate else x).float()
        loss = F.mse_loss(model['head_v'](h)[..., 0][data['mask']], data['v'][data['mask']]) + F.mse_loss(
            model['head_coarse'](h.mean(1)), F.adaptive_avg_pool2d(data['y0'], 16).flatten(1))
        opt.zero_grad()
        loss.backward()
        values = dict(output=h.detach(), loss=loss.detach(), input_gradient=x.grad)
        for name, p in model.named_parameters():
            assert p.grad is not None and p.grad.dtype == p.dtype == torch.float32, name
            values['gradient.' + name] = p.grad.detach().clone()
        opt.step()
        hook.remove()
        assert len(calls) == 1
        assert set(model.state_dict()) == set(initial)
        for name, p in model.named_parameters():
            assert p.dtype == torch.float32
            values['parameter.' + name] = p.detach().clone()
            values['update.' + name] = p.detach() - initial[name]
            state = opt.state[p]
            assert set(state) == {'step', 'exp_avg', 'exp_avg_sq'}
            assert state['step'].item() == 1
            for key, value in state.items():
                assert value.dtype == torch.float32 and torch.isfinite(value).all()
                if key != 'step':
                    values[key + '.' + name] = value.detach().clone()
        results.append(values)
    metrics = []
    for name, ref_value in results[0].items():
        limit = 0.05 if name.startswith('update.') else 0.04 if name.startswith('exp_avg_sq.') else (
            0.02 if name.startswith(('gradient.', 'exp_avg.')) or name == 'input_gradient' else 0.01)
        metrics.append(metric(name, ref_value, results[1][name], limit))
    failed = [m for m in metrics if not m['passed']]
    return dict(status='FAIL_LOCAL_QUANTIZATION_GATE' if failed else 'PASS_LOCAL_QUANTIZATION_ONLY',
                backend='torch_reference_fp32_emulation_of_quantized_sbgemm',
                environment=dict(python=sys.executable, torch=torch.__version__, torch_file=torch.__file__,
                                 platform=platform.platform(), threads=torch.get_num_threads()),
                precision='bf16 block interface/fp32 master+AdamW; CKPT0; no global autocast',
                fixture={k: tensor_identity(v) for k, v in data.items()},
                initial={k: tensor_identity(v) for k, v in initial.items()},
                metrics=metrics, checks=len(metrics), failed=len(failed),
                not_run=['actual_KML', 'C2_CPU36', 'bgemm_long_K', 'sbgemm_beta_initial_C',
                         'full_model', '200_updates', 'performance', 'memory_HBM'],
                jobs=0, full_model_runs=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run()
    path = ROOT / args.output
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'backend', 'checks', 'failed')}))
    sys.exit(int(result['failed'] > 0))
