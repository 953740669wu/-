"""CPU kernels for s4_models on C2: stride-1 Conv2d as im2col + one KML SME sgemm (forward and backward).

KML is called through ctypes on the tensors' buffers. It must share torch's OpenMP runtime (sw/torch_kml, whose
libgomp is BiSheng libomp), otherwise its threads inherit one core. Without KML_BLAS_LIB the GEMMs fall back to
torch.mm, so the layer is usable anywhere and can be checked against F.conv2d.
"""
import os, ctypes, struct
import torch, torch.nn as nn, torch.nn.functional as F

_lib = None
if os.environ.get('KML_BLAS_LIB'):
    _lib = ctypes.CDLL(os.environ['KML_BLAS_LIB'], mode=ctypes.RTLD_LOCAL)
    _argt = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                  ctypes.c_int, ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
    # bgemm: all bf16, alpha/beta in h0/h1 (probe_bgemm.py). sbgemm: bf16 A/B, fp32 alpha/beta/C, fp32 accumulation,
    # but some tiles ignore beta=0 and add into C (probe_sbgemm.py), so its C is always zeroed or a bias with beta=1.
    _sgemm, _bgemm, _sbgemm = _lib.cblas_sgemm, _lib.cblas_bgemm, _lib.cblas_sbgemm
    _sgemm.argtypes = _bgemm.argtypes = _sbgemm.argtypes = _argt
ROW, NT, T = 101, 111, 112                       # CblasRowMajor, CblasNoTrans, CblasTrans
_BF1 = struct.unpack('<f', struct.pack('<I', 0x3F80))[0]   # bf16 1.0 in the low half of an fp32 register


def gemm(a, b, ta=False, tb=False, out=None, beta=0.0, acc32=False):
    """op(a) @ op(b) (+ beta * out) for contiguous 2-D tensors, fp32 result; both float32 (KML sgemm) or both
    bfloat16 (KML bgemm: its C is bf16 and it accumulates through C across K blocks, relative error ~0.15 at
    K = 6e4, so use it only for short K; acc32=True uses sbgemm instead, fp32 C). Falls back to torch.mm without KML."""
    m, k = (a.shape[1], a.shape[0]) if ta else a.shape
    n = b.shape[0] if tb else b.shape[1]
    if _lib is None:
        r = ((a.t() if ta else a) @ (b.t() if tb else b)).float()
        return r if out is None else out.mul_(beta).add_(r)
    assert a.is_contiguous() and b.is_contiguous() and a.dtype == b.dtype
    if a.dtype == torch.bfloat16 and acc32:
        c = torch.zeros(m, n) if out is None else out
        if out is not None and beta != 1.0: c.mul_(beta)
        _sbgemm(ROW, T if ta else NT, T if tb else NT, m, n, k, 1.0, a.data_ptr(), a.shape[1],
                b.data_ptr(), b.shape[1], 1.0, c.data_ptr(), n)
        return c
    if a.dtype == torch.bfloat16:
        cb = torch.empty(m, n, dtype=torch.bfloat16)
        _bgemm(ROW, T if ta else NT, T if tb else NT, m, n, k, _BF1, a.data_ptr(), a.shape[1],
               b.data_ptr(), b.shape[1], 0.0, cb.data_ptr(), n)
        return cb.float() if out is None else out.mul_(beta).add_(cb)
    f = _sgemm
    c = torch.empty(m, n) if out is None else out
    assert c.is_contiguous() and c.dtype == torch.float32 and c.shape == (m, n)
    f(ROW, T if ta else NT, T if tb else NT, m, n, k, 1.0, a.data_ptr(), a.shape[1],
      b.data_ptr(), b.shape[1], beta if out is not None else 0.0, c.data_ptr(), n)
    return c


def _cols(x, k, p):
    """(B, C, H, W) -> im2col as (C*k*k, B*H*W), one GEMM operand for the whole batch."""
    B, C, H, W = x.shape
    return F.unfold(x, k, padding=p).view(B, C * k * k, H * W).transpose(0, 1).reshape(C * k * k, B * H * W)


class _ConvFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, w, b, k, p):
        B, _, H, W = x.shape
        co = w.shape[0]
        y = gemm(w.reshape(co, -1).contiguous(), _cols(x, k, p))          # (co, B*H*W)
        if b is not None: y += b[:, None]
        ctx.save_for_backward(x, w); ctx.k, ctx.p, ctx.hasb = k, p, b is not None
        return y.view(co, B, H, W).transpose(0, 1).contiguous()

    @staticmethod
    def backward(ctx, gy):
        x, w = ctx.saved_tensors; k, p = ctx.k, ctx.p
        B, C, H, W = x.shape; co = w.shape[0]
        g = gy.transpose(0, 1).reshape(co, B * H * W).contiguous()          # (co, B*H*W)
        gw = gemm(g, _cols(x, k, p), tb=True).view_as(w)                    # im2col recomputed, not stored
        gc = gemm(w.reshape(co, -1).contiguous(), g, ta=True)              # (C*k*k, B*H*W)
        gx = F.fold(gc.view(C * k * k, B, H * W).transpose(0, 1), (H, W), k, padding=p)
        return gx, gw, (g.sum(1) if ctx.hasb else None), None, None


class KConv2d(nn.Conv2d):
    """Drop-in for a stride-1, 'same'-padded, ungrouped nn.Conv2d (the kernels of the s4_models U-Net)."""
    def forward(self, x):
        if x.is_cuda or not torch.is_grad_enabled() and _lib is None:
            return super().forward(x)
        return _ConvFn.apply(x.float().contiguous(), self.weight, self.bias, self.kernel_size[0], self.padding[0])


def swap_convs(model):
    """Replace every eligible nn.Conv2d in model by a KConv2d sharing the same parameters."""
    n = 0
    for name, m in list(model.named_modules()):
        for cn, c in list(m.named_children()):
            if type(c) is nn.Conv2d and c.stride == (1, 1) and c.groups == 1 and c.dilation == (1, 1) and \
                    c.kernel_size[0] == c.kernel_size[1] and c.padding == (c.kernel_size[0] // 2,) * 2:
                kc = KConv2d.__new__(KConv2d); kc.__dict__ = c.__dict__     # same Parameter objects
                setattr(m, cn, kc); n += 1
    return n


# ---------------------------------------------------------------- attention as chunked batched GEMMs
# torch's CPU flash-attention kernel runs at ~86 GFLOP/s on the 32-belt encoder (B64 x 8 heads x 928 tokens); here
# scores are formed per chunk of (batch x head) rows with bmm (BLAS sgemm_, i.e. KML with the shim), and recomputed in
# backward from the saved log-sum-exp, so memory stays at one chunk of scores.
CHUNK_FLOATS = int(os.environ.get('ATTN_CHUNK_FLOATS', 64 * 2 ** 20))


class _AttnFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx, q, k, v, scale):
        BH, N, d = q.shape; Nk = k.shape[1]
        step = max(1, CHUNK_FLOATS // (N * Nk))
        o = torch.empty_like(q); lse = torch.empty(BH, N)
        for s in range(0, BH, step):
            sc = torch.bmm(q[s:s + step], k[s:s + step].transpose(1, 2)).mul_(scale)
            m = sc.logsumexp(-1, keepdim=True)
            lse[s:s + step] = m[..., 0]
            torch.bmm(sc.sub_(m).exp_(), v[s:s + step], out=o[s:s + step])
        ctx.save_for_backward(q, k, v, o, lse); ctx.scale = scale
        return o

    @staticmethod
    def backward(ctx, go):
        q, k, v, o, lse = ctx.saved_tensors; scale = ctx.scale
        BH, N, d = q.shape; Nk = k.shape[1]
        step = max(1, CHUNK_FLOATS // (N * Nk))
        go = go.contiguous()
        dq, dk, dv = torch.empty_like(q), torch.empty_like(k), torch.empty_like(v)
        D = (go * o).sum(-1, keepdim=True)
        for s in range(0, BH, step):
            sl = slice(s, s + step)
            p = torch.bmm(q[sl], k[sl].transpose(1, 2)).mul_(scale).sub_(lse[sl, :, None]).exp_()
            torch.bmm(p.transpose(1, 2), go[sl], out=dv[sl])
            dp = torch.bmm(go[sl], v[sl].transpose(1, 2))
            ds = dp.sub_(D[sl]).mul_(p).mul_(scale)
            torch.bmm(ds, k[sl], out=dq[sl])
            torch.bmm(ds.transpose(1, 2), q[sl], out=dk[sl])
        return dq, dk, dv, None


_sdpa = F.scaled_dot_product_attention


def gemm_attention(q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False, scale=None, **kw):
    """Drop-in for F.scaled_dot_product_attention without mask/dropout/causal (else the stock kernel)."""
    if q.is_cuda or attn_mask is not None or dropout_p or is_causal or kw or q.dtype != torch.float32:
        return _sdpa(q, k, v, attn_mask=attn_mask, dropout_p=dropout_p, is_causal=is_causal, scale=scale, **kw)
    sh = q.shape
    sc = scale if scale is not None else sh[-1] ** -0.5
    f = lambda x: x.reshape(-1, *x.shape[-2:]).contiguous()
    return _AttnFn.apply(f(q), f(k), f(v), sc).view(*sh[:-1], v.shape[-1])


def patch_attention():
    """Route every F.scaled_dot_product_attention call (nn.MultiheadAttention included) to gemm_attention."""
    F.scaled_dot_product_attention = gemm_attention


# ---------------------------------------------------------------- linear layers on KML (phase B1 / C2)
# Every F.linear call (nn.Linear and nn.MultiheadAttention's in/out projections) -> one KML GEMM per pass.
# LINEAR_DTYPE=bf16 runs the forward and dX GEMMs in bgemm (bf16 outputs, as CUDA autocast does; fp32 master weights)
# and dW, whose K is the token count, with fp32 accumulation: sbgemm for >= 1M outputs, else sgemm (bench_gemm.py).
LINEAR_DTYPE = {'fp32': torch.float32, 'bf16': torch.bfloat16}[os.environ.get('LINEAR_DTYPE', 'fp32')]


class _LinearFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, w, b):
        sh = x.shape
        x2 = x.reshape(-1, sh[-1]).to(LINEAR_DTYPE).contiguous()
        wc = w.to(LINEAR_DTYPE).contiguous()
        if b is not None:
            y = b.float().expand(x2.shape[0], w.shape[0]).contiguous()
            gemm(x2, wc, tb=True, out=y, beta=1.0)
        else:
            y = gemm(x2, wc, tb=True)
        ctx.save_for_backward(x2, wc); ctx.sh, ctx.hasb = sh, b is not None
        return y.view(*sh[:-1], w.shape[0])

    @staticmethod
    def backward(ctx, gy):
        x2, wc = ctx.saved_tensors
        g = gy.reshape(-1, gy.shape[-1]).to(LINEAR_DTYPE).contiguous()
        gx = gemm(g, wc).view(ctx.sh) if ctx.needs_input_grad[0] else None
        gw = None
        if ctx.needs_input_grad[1]:
            big = g.dtype == torch.bfloat16 and g.shape[1] * x2.shape[1] >= 2 ** 20
            gw = gemm(g, x2, ta=True, acc32=True) if big else gemm(g.float(), x2.float(), ta=True)
        gb = gy.reshape(-1, gy.shape[-1]).sum(0) if ctx.hasb and ctx.needs_input_grad[2] else None
        return gx, gw, gb


_linear = F.linear


def kml_linear(x, w, b=None):
    if x.is_cuda or _lib is None or x.dtype not in (torch.float32, torch.bfloat16) or x.numel() < 2 ** 16:
        return _linear(x, w, b)                                      # tiny GEMMs (time embedding, heads)
    return _LinearFn.apply(x, w, b)


def patch_linear():
    """Route every F.linear call (nn.Linear, nn.MultiheadAttention projections) through KML."""
    F.linear = kml_linear


# S04 isolated candidate: no global patch, persistent bf16 activation interface.
def _chain_gemm(a, b, backend, ta=False, tb=False):
    if backend == 'torch_reference':
        # Quantization oracle only: deliberately NOT native bf16/KML performance.
        a, b = a.float(), b.float()
        return (a.t() if ta else a) @ (b.t() if tb else b)
    if backend != 'kml':
        raise ValueError('explicit torch_reference or kml backend required')
    import sys
    if sys.platform != 'linux' or _lib is None:
        raise RuntimeError('actual Linux KML required; no torch fallback')
    # bf16 forward/dX use fp32 C; dW operands are already fp32 -> SGEMM.
    return gemm(a, b, ta=ta, tb=tb, acc32=a.dtype == torch.bfloat16)


class _ChainBF16LinearFn(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, w, b, backend):
        x2 = x.reshape(-1, x.shape[-1]).contiguous()
        wc = w.bfloat16().contiguous()
        y = _chain_gemm(x2, wc, backend, tb=True)
        if b is not None:
            y.add_(b)
        ctx.save_for_backward(x2, wc)
        ctx.shape, ctx.hasb, ctx.backend = x.shape, b is not None, backend
        return y.bfloat16().view(*x.shape[:-1], w.shape[0])

    @staticmethod
    def backward(ctx, gy):
        x2, wc = ctx.saved_tensors
        g = gy.reshape(-1, gy.shape[-1]).contiguous()
        gx = (_chain_gemm(g, wc, ctx.backend).bfloat16().view(ctx.shape)
              if ctx.needs_input_grad[0] else None)
        # Long token reduction always uses fp32 SGEMM, never bf16 bgemm dW.
        gw = (_chain_gemm(g.float(), x2.float(), ctx.backend, ta=True)
              if ctx.needs_input_grad[1] else None)
        gb = g.float().sum(0) if ctx.hasb and ctx.needs_input_grad[2] else None
        return gx, gw, gb, None


def chain_bf16_linear(x, w, b, backend):
    if (x.device.type != 'cpu' or w.device.type != 'cpu' or x.dtype != torch.bfloat16
            or w.dtype != torch.float32 or (b is not None and
            (b.dtype != torch.float32 or b.device.type != 'cpu'))):
        raise ValueError('CPU bf16 activation / fp32 master weights and bias required')
    return _ChainBF16LinearFn.apply(x, w, b, backend)
