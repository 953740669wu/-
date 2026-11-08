"""Apply the old frozen 83 metrics on C2, with the actual BF16 KML QKV dW."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

import torch
import torch.nn.functional as F

from bf16_dw import QKVWeightGradient

FIXTURE = Path(__file__).resolve().parent / "fixture"


def run(result, library, production_kml):
    native_linear = production_kml._linear
    spec = importlib.util.spec_from_file_location("s04_fixture_kml", FIXTURE / "candidate/kml_ops.py")
    fixture_kml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_kml)
    original_helper = fixture_kml.chain_bf16_linear
    result["fixture_kml_source"] = str(spec.origin)
    sys.path.insert(0, str(FIXTURE / "tests"))
    from check_alignment import compare, rewritten, step
    from common import fixture, tensor_identity

    old = json.loads((FIXTURE / "r1_block_numeric.json").read_bytes())
    inputs = torch.load(FIXTURE / "FROZEN_FIXTURE.pt", weights_only=True, map_location="cpu")
    reference, _ = fixture()
    reference.load_state_dict(inputs["state"], strict=True)
    data = inputs["data"]
    identity = dict(fixture={k: tensor_identity(t) for k, t in data.items()},
                    initial={k: tensor_identity(t) for k, t in reference.state_dict().items()})
    if identity != {key: old[key] for key in identity}:
        raise ValueError("original fixture tensor SHA differs")
    result["fixture_identity"] = identity
    control = rewritten(reference, "torch_fp32_control")
    mixed = copy.deepcopy(control)
    result["fixture_steps"] = 0
    with patch.object(F, "linear", native_linear), patch.object(production_kml, "chain_bf16_linear", original_helper, create=True):
        ref = step(reference, data)
        result["fixture_steps"] += 1
        got = step(control, data, "torch_fp32_control")
        result["fixture_steps"] += 1
    strict = result["fp32_control"] = compare(ref, got, fp32=True)
    strict["bitwise_mismatch"] = [
        name for name in ref if not torch.equal(ref[name].reshape(-1).contiguous().view(torch.uint8),
                                                got[name].reshape(-1).contiguous().view(torch.uint8))
    ]
    strict["bitwise"] = not strict["bitwise_mismatch"]
    if strict["checks"] != 83 or strict["failed"] or not strict["bitwise"]:
        result["status"] = "REJECTED_MODULE_FP32_CONTROL"
        return

    dweight = QKVWeightGradient(library)
    rng = torch.Generator().manual_seed(20261108)
    g, x = torch.randn(129, 64, generator=rng), torch.randn(129, 48, generator=rng)
    reference_product = g.bfloat16().double().T @ x.bfloat16().double()
    checked = dweight(g, x)
    error = (checked.double() - reference_product).norm().item() / reference_product.norm().item()
    result["abi_fp32_accumulation"] = dict(relative_l2=error, limit=2e-6, shape=[64, 48, 129],
                                          out_dtype=str(checked.dtype), stats=dict(dweight.stats), kml_symbol_identity=dweight.kml_symbol_identity)
    if checked.dtype != torch.float32 or not torch.isfinite(checked).all() or error > 2e-6:
        raise ValueError("actual sbgemm failed BF16-operands / FP32-C ABI check")
    dweight.reset()
    target = mixed["block"].self_attn.in_proj_weight

    class FixtureQKV(torch.autograd.Function):
        @staticmethod
        def forward(ctx, x, w, b):
            with torch.enable_grad():
                x = x.detach().requires_grad_()
                b = b.detach().requires_grad_()
                y = native_linear(x, w.detach(), b)
            ctx.save_for_backward(x, b, y)
            return y.detach()

        @staticmethod
        def backward(ctx, g):
            x, b, y = ctx.saved_tensors
            dx, db = torch.autograd.grad(y, (x, b), g)
            dw = dweight(g.reshape(-1, g.shape[-1]).contiguous(),
                         x.detach().reshape(-1, x.shape[-1]).contiguous())
            return dx, dw, db

    def linear(x, w, b=None):
        return FixtureQKV.apply(x, w, b) if w is target else native_linear(x, w, b)

    with patch.object(F, "linear", linear), patch.object(production_kml, "chain_bf16_linear", original_helper, create=True):
        actual = step(mixed, data, "torch_fp32_control")
        result["fixture_steps"] += 1
    checks = result["bf16_module"] = compare(ref, actual)
    result["bf16_dw"] = dweight.stats
    if checks["checks"] != 83 or dweight.stats["calls"] != 1 or dweight.stats["conversions"] != 2:
        raise ValueError("expected 83 frozen metrics and one actual KML BF16 QKV dW")
    result["status"] = "PASS_MODULE83" if not checks["failed"] else "REJECTED_MODULE83"
