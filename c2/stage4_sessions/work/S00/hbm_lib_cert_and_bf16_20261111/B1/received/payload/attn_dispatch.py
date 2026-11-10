"""Isolated BF16-tile dispatch based on the reviewed external _FusedAttnFn."""
import ctypes
import hashlib
import json
import math
from pathlib import Path

import torch
import torch.nn.functional as F

BQ = 16


def view(x):
    return [x.data_ptr(), *x.stride()[:3]]


def output(batch, heads, tokens, width):
    return torch.empty(tokens, batch, heads, width, dtype=torch.float32, device='cpu').permute(1, 2, 0, 3)


class FusedAttention(torch.autograd.Function):
    @staticmethod
    def forward(ctx, q, k, v, scale, kernel):
        b, h, nq, d = q.shape
        nk = k.shape[2]
        o = output(b, h, nq, d)
        lse = torch.empty(b, h, nq, dtype=torch.float32, device='cpu')
        kernel.call('forward', b, h, nq, nk, d, scale, BQ, *view(q), *view(k), *view(v), *view(o), lse.data_ptr())
        ctx.save_for_backward(q, k, v, o, lse)
        ctx.scale, ctx.kernel = scale, kernel
        return o

    @staticmethod
    def backward(ctx, grad):
        q, k, v, o, lse = ctx.saved_tensors
        b, h, nq, d = q.shape
        nk = k.shape[2]
        if grad.stride(-1) != 1 or grad.stride(-2) < d:
            grad = grad.contiguous()
        dq, dk, dv = output(b, h, nq, d), output(b, h, nk, d), output(b, h, nk, d)
        ctx.kernel.call('backward', b, h, nq, nk, d, ctx.scale, BQ, *view(q), *view(k), *view(v),
                        *view(o), *view(grad), lse.data_ptr(), *view(dq), *view(dk), *view(dv))
        return dq, dk, dv, None, None


class Dispatch:
    def __init__(self, receipt):
        info = self.identity = json.loads(Path(receipt).read_bytes())
        if info['bq'] != BQ or info['bf16'] != 1:
            raise RuntimeError('wrong BF16/BQ16 build receipt')
        for name in ('library', 'locking_kml'):
            p = Path(info[name]['path'])
            if hashlib.sha256(p.read_bytes()).hexdigest() != info[name]['sha256']:
                raise RuntimeError('attention library identity changed: ' + name)
        self.lib = ctypes.CDLL(info['library']['path'])
        load = self.lib.kml_attn_load
        load.argtypes, load.restype = [ctypes.c_char_p], ctypes.c_int
        if load(info['locking_kml']['path'].encode()):
            raise RuntimeError('failed to load the distinct locking KML namespace')
        self.locking_info = self.lib.kml_attn_locking_info
        self.locking_info.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_long),
                                      ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_void_p)]
        self.locking_info.restype = ctypes.c_int
        self.namespace = self.locking_namespace()
        v = [ctypes.c_void_p] + [ctypes.c_long] * 3
        head = [ctypes.c_int] * 5 + [ctypes.c_float, ctypes.c_int]
        self.forward = self.lib.kml_attn_fwd_bf
        self.backward = self.lib.kml_attn_bwd_bf
        self.forward.argtypes = head + v * 4 + [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        self.backward.argtypes = head + v * 5 + [ctypes.c_void_p] + v * 3 + [ctypes.POINTER(ctypes.c_ulong)]
        self.forward.restype = self.backward.restype = ctypes.c_int
        self.sm_guard = getattr(ctypes.CDLL(None), 'kml_sm_guard', None)
        if self.sm_guard is not None:
            self.sm_guard.argtypes, self.sm_guard.restype = [], None
        self.counts = dict(forward=0, backward=0, forward_tiles=0, backward_tiles=0)
        self.check_maps()

    def locking_namespace(self):
        handle, namespace_id, path, gemm = ctypes.c_void_p(), ctypes.c_long(), ctypes.c_char_p(), ctypes.c_void_p()
        if self.locking_info(ctypes.byref(handle), ctypes.byref(namespace_id), ctypes.byref(path), ctypes.byref(gemm)):
            raise RuntimeError('cannot identify the actual isolated locking KML handle and SBGEMM owner')
        expected = self.identity['locking_kml']
        if (not handle.value or namespace_id.value <= 0 or not path.value or not gemm.value
                or str(Path(path.value.decode()).resolve(strict=True)) != expected['path']):
            raise RuntimeError('isolated locking KML handle, namespace, or path differs')
        receipt = dict(**expected, namespace_id=namespace_id.value, handle=handle.value, gemm_address=gemm.value, symbol="cblas_sbgemm")
        if hasattr(self, 'namespace') and self.namespace != receipt:
            raise RuntimeError('isolated locking KML identity changed within worker')
        return receipt

    def check_maps(self):
        maps = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()}
        if any(self.identity[k]['path'] not in maps for k in ('library','locking_kml')):
            raise RuntimeError('required fused attention or locking KML mapping missing')

    def call(self, direction, *args):
        tiles = ctypes.c_ulong()
        status = getattr(self, direction)(*args, ctypes.byref(tiles))
        if self.sm_guard is not None:
            self.sm_guard()
        if status != 0:
            raise RuntimeError(f'BF16 fused attention {direction} native status {status}')
        batch, heads, nq, nk, _, _, bq = args[:7]
        expected = batch * heads * ((nq + bq - 1) // bq)
        if direction == 'backward':
            expected += batch * heads * ((nk + bq - 1) // bq)
        if bq != BQ or tiles.value != expected:
            raise RuntimeError(f'{direction} wrong BF16 tile count: {tiles.value}, expected {expected}')
        self.counts[direction] += 1
        self.counts[direction + '_tiles'] += tiles.value

    def sdpa(self, q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, **kwargs):
        expected = (32, 8, 928, 64)
        if attn_mask is not None or dropout_p or is_causal or kwargs or any(
                x.device.type != 'cpu' or x.dtype != torch.float32 or tuple(x.shape) != expected
                or x.stride(-1) != 1 or x.stride(-2) < expected[-1] for x in (q, k, v)):
            raise RuntimeError('unsupported SDPA contract in fused candidate; fallback prohibited')
        scale = expected[-1] ** -0.5 if scale is None else scale
        if not math.isfinite(scale):
            raise RuntimeError('nonfinite attention scale')
        return FusedAttention.apply(q, k, v, scale, self)

    def install(self):
        F.scaled_dot_product_attention = self.sdpa
