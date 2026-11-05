"""Real full-size torch check. Exit 2 means NOT_RUN, never numerical PASS.

Run one configuration per process; this harness retains comparison snapshots and
must not be used to measure a production step's memory or throughput.
"""
import argparse
import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def model_definitions(torch):
    # s4_models is a CLI with top-level argv/resource/NPZ work. Execute only its
    # unchanged class/protocol AST definitions; do not mock resource or numpy.
    source = ROOT / 'baseline' / 's4_models.py'
    tree = ast.parse(source.read_text('utf-8'))
    names = {'Encoder', 'Block', 'UNet', 'protocol_angles'}
    nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    if {n.name for n in nodes} != names:
        raise AssertionError('missing original model definitions')
    ns = dict(torch=torch, nn=torch.nn, F=torch.nn.functional, math=math)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    return ns


def expected_gradient(name, part):
    if part == 'pre':
        return name.startswith('enc.')
    return name.startswith('dec.') or not name.startswith(
        ('enc.mask_tok', 'enc.head_v.', 'enc.head_coarse.'))


def compare(torch, name, ref, got, category, metrics):
    if ref is None or got is None:
        if ref is not None or got is not None:
            raise AssertionError(f'{name}: missing/unexpected tensor')
        return
    if ref.shape != got.shape or ref.dtype != got.dtype:
        raise AssertionError(f'{name}: shape/dtype mismatch')
    if not torch.isfinite(ref).all() or not torch.isfinite(got).all():
        raise AssertionError(f'{name}: NaN/Inf')
    if category == 'exact':
        if not torch.equal(ref, got):
            raise AssertionError(f'{name}: must be unchanged/exact')
        return
    # Norms in float64; no giant concatenation across parameters.
    delta = got.double() - ref.double()
    norm = ref.double().norm().item()
    rel = delta.norm().item() / max(norm, 1e-12)
    absolute = delta.abs().max().item() if delta.numel() else 0.0
    limit = 2e-6 if category == 'state' else 2e-5
    passed = absolute <= limit and (norm <= 1e-8 or rel <= 2e-6)
    metrics.append(dict(name=name, max_abs=absolute, l2_relative=rel,
                        reference_norm=norm, passed=passed))
    if not passed:
        raise AssertionError(f'{name}: max_abs={absolute}, relative={rel}')


def loss_unit_checks(torch):
    """Small real-autograd negative control, not full-model acceptance."""
    target = torch.tensor([-1.] + [1.] * 9)
    observations = []
    for kind in ('full', 'weighted', 'wrong_mean'):
        p = torch.nn.Parameter(torch.tensor(0.25))
        opt = torch.optim.AdamW([p], lr=1e-4)
        opt.zero_grad()
        if kind == 'full':
            torch.nn.functional.mse_loss(p.expand_as(target), target).backward()
        else:
            for chunk in (target[:1], target[1:]):
                squared = (p - chunk).square()
                loss = squared.sum() / target.numel() if kind == 'weighted' else squared.mean() / 2
                loss.backward()
        grad = p.grad.detach().clone()
        opt.step()
        observations.append((grad, p.detach().clone(), opt.state[p]['exp_avg'].clone(),
                             opt.state[p]['exp_avg_sq'].clone()))
    for i, (ref, got) in enumerate(zip(observations[0], observations[1])):
        compare(torch, f'loss_unit.{i}', ref, got, 'tensor', [])
    assert observations[0][0] * observations[2][0] < 0, 'negative control must reverse gradient'
    assert observations[0][1] != observations[2][1], 'wrong denominator must change AdamW update'
    bad_pairs = [(torch.ones(1), None), (torch.ones(1), torch.tensor([float('nan')])),
                 (torch.ones(1), torch.tensor([float('inf')]))]
    for ref, got in bad_pairs:
        try:
            compare(torch, 'negative_control', ref, got, 'tensor', [])
        except AssertionError:
            pass
        else:
            raise AssertionError('comparator accepted missing/nonfinite tensor')
    return 'PASS_REAL_AUTOGRAD_UNIT_ONLY'


def main(args, torch, result):
    torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    result['loss_unit_check'] = loss_unit_checks(torch)
    # Never silently use KML's torch.mm fallback as C2 KML validation.
    if args.kml:
        import os
        if not os.environ.get('KML_BLAS_LIB') or os.environ.get('LINEAR_DTYPE', 'fp32') != 'fp32':
            raise RuntimeError('--kml requires the actual KML_BLAS_LIB and fp32')
        sys.path.insert(0, str(ROOT / 'baseline'))
        import kml_ops
        if kml_ops._lib is None:
            raise RuntimeError('KML not loaded')
        kml_ops.patch_linear()
    ns = model_definitions(torch)
    enc, dec = ns['Encoder'](), ns['UNet']()
    # Keep names identical to original state_dicts inside two explicit prefixes.
    models = torch.nn.ModuleDict({'enc': enc, 'dec': dec})
    initial = copy.deepcopy(models.state_dict())
    expected_counts = json.loads((ROOT / 'evidence' / 'static_memory.json').read_text('utf-8'))['parameters']
    assert sum(p.numel() for p in enc.parameters()) == expected_counts['encoder']
    assert sum(p.numel() for p in dec.parameters()) == expected_counts['decoder']
    B = 64
    L, skip = (16, 1) if args.belt == '16_adjacent' else (32, 5)
    angle = ns['protocol_angles'](L, skip)
    M = len(angle)
    v0, y0 = torch.randn(B, M), torch.randn(B, 1, 64, 64) * 0.1
    angles = angle.expand(B, M, 4)
    belt = torch.full((B, M), float(L == 32))
    mask = torch.rand(B, M) < 0.8
    mask[:16] = False
    mask[16:32] = torch.rand(16, M) < 0.2
    t, noise = torch.randint(0, 1000, (B,)), torch.randn_like(y0)
    abar = torch.cumprod(1 - torch.linspace(1e-4, 0.02, 1000), 0)
    spec = importlib.util.spec_from_file_location('s02_step', ROOT / 'candidate' / 'training_step.py')
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    result['environment'] = dict(python=sys.executable, torch=torch.__version__,
                                 torch_file=torch.__file__, threads=torch.get_num_threads(),
                                 backend='actual_KML' if args.kml else 'native_torch', device='cpu')
    result['mask_counts'] = [int(m.sum()) for m in mask.split(16)]
    result['metrics'] = []

    def run(reference):
        models.load_state_dict(initial, strict=True)
        models.zero_grad(set_to_none=True)
        opt = torch.optim.AdamW(models.parameters(), lr=1e-4, betas=(0.9, 0.999),
                                eps=1e-8, weight_decay=0.01)
        if args.history == 'seeded':
            # Synthetic prior state, not a trained checkpoint. Exercises inactive
            # parameter states and step counters after a phase switch.
            for p in models.parameters():
                opt.state[p] = dict(step=torch.tensor(7.0), exp_avg=torch.full_like(p, 0.001),
                                    exp_avg_sq=torch.full_like(p, 0.0001))
        calls = []
        step_hook = opt.register_step_post_hook(lambda *_: calls.append(1))
        v, image = v0.clone().requires_grad_(), y0.clone().requires_grad_()
        outputs = {}
        handles = []
        def hook(name):
            def capture(_module, _inputs, output):
                outputs.setdefault(name, []).append(output.detach().clone())
            return capture
        watched = {'h': enc.tf}
        watched.update({'voltage': enc.head_v, 'coarse': enc.head_coarse} if args.part == 'pre'
                       else {'noise_prediction': dec})
        for name, module in watched.items():
            handles.append(module.register_forward_hook(hook(name)))
        try:
            if reference:
                F = torch.nn.functional
                if args.part == 'pre':
                    h = enc(v, angles, belt, mask)
                    loss = F.mse_loss(enc.head_v(h)[..., 0][mask], v[mask]) + F.mse_loss(
                        enc.head_coarse(h.mean(1)), F.adaptive_avg_pool2d(image, 16).flatten(1))
                else:
                    a = abar[t][:, None, None, None]
                    xt = a.sqrt() * image + (1 - a).sqrt() * noise
                    h = enc(v, angles, belt)
                    loss = F.mse_loss(dec(xt, t, h), noise)
                opt.zero_grad()
                loss.backward()
                opt.step()
                loss = loss.detach()
            else:
                loss = candidate.training_step(enc, dec, opt, v, angles, belt, image,
                    part=args.part, microbatch=args.microbatch, mask=mask, t=t, noise=noise, abar=abar)
        finally:
            for handle in handles:
                handle.remove()
            step_hook.remove()
        assert len(calls) == 1, 'must call optimizer.step exactly once'
        snapshot = {'loss': loss.clone(), 'input_v': v.grad, 'input_y0': image.grad}
        snapshot.update({'output.' + k: torch.cat(chunks) for k, chunks in outputs.items()})
        for name, p in models.named_parameters():
            active = expected_gradient(name, args.part)
            assert (p.grad is not None) == active, f'{name}: incorrect gradient presence'
            snapshot['grad.' + name] = None if p.grad is None else p.grad.detach().clone()
            snapshot['param.' + name] = p.detach().clone()
            snapshot['delta.' + name] = p.detach() - initial[name]
            state = opt.state.get(p, {})
            expected_keys = {'step', 'exp_avg', 'exp_avg_sq'} if active or args.history == 'seeded' else set()
            assert set(state) == expected_keys, f'{name}: AdamW state keys'
            for key, value in state.items():
                if key == 'step':
                    assert value.item() == (7 if args.history == 'seeded' else 0) + int(active)
                if not active:
                    original = {'step': 7.0, 'exp_avg': 0.001, 'exp_avg_sq': 0.0001}[key]
                    assert torch.equal(value, torch.full_like(value, original)), f'{name}: inactive state changed'
                snapshot['state.' + name + '.' + key] = value.detach().clone()
            if not active:
                assert torch.equal(p, initial[name]), f'{name}: inactive parameter changed'
        assert set(models.state_dict()) == set(initial), 'state_dict keys changed'
        return snapshot

    reference = run(True)
    if args.checkpoint:
        candidate.enable_checkpoint(enc)
    actual = run(False)
    assert set(reference) == set(actual), 'snapshot keys differ'
    for name in reference:
        category = 'exact' if name.endswith('.step') else 'state' if name.startswith('state.') else 'tensor'
        compare(torch, name, reference[name], actual[name], category, result['metrics'])
    # Invalid global mask must reject before clearing gradients or changing state.
    opt = torch.optim.AdamW(models.parameters(), lr=1e-4)
    first = next(enc.parameters())
    sentinel = torch.ones_like(first)
    first.grad = sentinel
    try:
        candidate.training_step(enc, dec, opt, v0, angles, belt, y0, part='pre',
                                microbatch=16, mask=torch.zeros_like(mask))
    except ValueError:
        assert first.grad is sentinel and not opt.state
    else:
        raise AssertionError('empty full mask did not reject')
    result['status'] = 'PASS_SYNTHETIC_FULL_MODEL_ONLY'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--belt', choices=['16_adjacent', '32_skip4'], required=True)
    parser.add_argument('--part', choices=['pre', 'dec'], required=True)
    parser.add_argument('--microbatch', type=int, choices=[16, 32, 64], required=True)
    parser.add_argument('--checkpoint', action='store_true')
    parser.add_argument('--history', choices=['fresh', 'seeded'], default='fresh')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--kml', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(status='NOT_RUN', config={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()})
    code = 2
    if importlib.util.find_spec('torch') is None:
        result['reason'] = 'No torch in this interpreter; no model/autograd/AdamW executed.'
    else:
        try:
            import torch
            main(args, torch, result)
            code = 0
        except Exception as exc:
            import traceback
            result.update(status='FAIL', error=repr(exc), traceback=traceback.format_exc())
            code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'metrics'}, indent=2))
    sys.exit(code)
