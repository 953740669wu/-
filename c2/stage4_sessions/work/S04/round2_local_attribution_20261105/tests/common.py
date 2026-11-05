"""Load unchanged class definitions without executing the original model CLI."""
import ast
import hashlib
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))


def definitions(folder, names):
    source = ROOT / folder / 's4_models.py'
    tree = ast.parse(source.read_text('utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    assert {n.name for n in nodes} == set(names), 'missing original/candidate definitions'
    ns = dict(torch=torch, nn=torch.nn, F=torch.nn.functional)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), ns)
    return ns


def fixture():
    torch.manual_seed(0)
    enc = definitions('baseline', ['Encoder'])['Encoder'](depth=1)
    models = torch.nn.ModuleDict(dict(block=enc.tf.layers[0], head_v=enc.head_v,
                                    head_coarse=enc.head_coarse))
    rng = torch.Generator().manual_seed(20261105)
    x = torch.randn(2, 17, 512, generator=rng)
    v = torch.randn(2, 17, generator=rng)
    y0 = torch.randn(2, 1, 64, 64, generator=rng)
    mask = torch.rand(2, 17, generator=rng) < 0.5
    mask[0, 0] = True
    return models, dict(x=x, v=v, y0=y0, mask=mask)


def tensor_identity(t):
    t = t.detach().contiguous()
    return dict(dtype=str(t.dtype), shape=list(t.shape), sha256=hashlib.sha256(
        t.view(torch.uint8).numpy().tobytes()).hexdigest())


def metric(name, ref, got, limit):
    if ref is None or got is None or ref.shape != got.shape:
        return dict(name=name, passed=False, reason='missing tensor / shape')
    if not torch.isfinite(ref).all() or not torch.isfinite(got).all():
        return dict(name=name, passed=False, reason='NaN/Inf')
    delta = got.double() - ref.double()
    norm = ref.double().norm().item()
    rms = delta.square().mean().sqrt().item()
    rel = delta.norm().item() / max(norm, 1e-12)
    return dict(name=name, reference_norm=norm, max_abs=delta.abs().max().item(),
                rms_abs=rms, l2_relative=rel, limit=limit,
                passed=rms <= 1e-7 if norm <= 1e-8 else rel <= limit)
