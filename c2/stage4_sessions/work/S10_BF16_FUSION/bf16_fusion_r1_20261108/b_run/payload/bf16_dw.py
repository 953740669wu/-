"""S10 mixed-precision QKV dW. All other arithmetic uses the original path."""
import ctypes
import os
from pathlib import Path
from time import monotonic_ns

import torch
import torch.nn.functional as F


class QKVWeightGradient:
    def __init__(self, library):
        self.library = ctypes.CDLL(str(Path(library).resolve()), mode=ctypes.RTLD_LOCAL)
        expected = Path(os.environ["KML_BLAS_LIB"]).resolve(strict=True)
        kml = ctypes.CDLL(str(expected), mode=ctypes.RTLD_LOCAL)
        bound = self.library.s10_sbgemm_address
        bound.restype = ctypes.c_void_p
        bound.argtypes = []
        if bound() != ctypes.cast(kml.cblas_sbgemm, ctypes.c_void_p).value:
            raise ValueError("wrapper sbgemm did not bind to the frozen KML symbol")
        self.kml_symbol_identity = str(expected)
        self.gemm = self.library.s10_qkv_dw
        self.gemm.restype = None
        self.gemm.argtypes = [ctypes.c_int] * 3 + [ctypes.c_void_p] * 3
        self.reset()

    def reset(self):
        self.stats = dict(calls=0, conversions=0, converted_elements=0, pack_ns=0, gemm_ns=0, zero_ns=0)

    def __call__(self, g, x):
        if not (g.dtype == x.dtype == torch.float32 and g.is_contiguous() and x.is_contiguous()
                and g.ndim == x.ndim == 2 and len(g) == len(x)):
            raise ValueError("QKV dW requires matching contiguous fp32 operand rows")
        start = monotonic_ns()
        gb = g.to(torch.bfloat16)
        xb = x.to(torch.bfloat16)
        packed = monotonic_ns()
        out = torch.zeros(g.shape[1], x.shape[1], dtype=torch.float32)
        cleared = monotonic_ns()
        self.gemm(g.shape[1], x.shape[1], len(g), gb.data_ptr(), xb.data_ptr(), out.data_ptr())
        end = monotonic_ns()
        self.stats["calls"] += 1
        self.stats["conversions"] += 2
        self.stats["converted_elements"] += g.numel() + x.numel()
        self.stats["pack_ns"] += packed - start
        self.stats["zero_ns"] += cleared - packed
        self.stats["gemm_ns"] += end - cleared
        return out

    def install_encoder(self, model, kml_ops):
        selected = {id(layer.self_attn.in_proj_weight) for layer in model.tf.layers}
        if len(selected) != 12:
            raise ValueError("expected the 12 original Encoder QKV weights")
        dweight = self

        class QKVLinear(kml_ops._LinearFn):
            @staticmethod
            def backward(ctx, gy):
                x, w = ctx.saved_tensors
                rows = gy.reshape(-1, gy.shape[-1])
                g = rows.contiguous()
                gx = kml_ops.gemm(g, w).view(ctx.sh) if ctx.needs_input_grad[0] else None
                gw = dweight(g, x) if ctx.needs_input_grad[1] else None
                gb = rows.sum(0) if ctx.hasb and ctx.needs_input_grad[2] else None
                return gx, gw, gb

        linear = F.linear

        def qkv_only(x, w, b=None):
            if id(w) in selected:
                return QKVLinear.apply(x, w, b)
            return linear(x, w, b)

        F.linear = qkv_only
