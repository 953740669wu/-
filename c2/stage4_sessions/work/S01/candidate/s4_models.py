"""Stage 4: timing of reconstruction-side components on demo frames.

- One-step Gauss-Newton with NOSER prior (baseline): precompute and per-frame time, demo-only error.
- EIT-FM measurement-token encoder (12 layers, width 512, 8 heads) with masked measurement modelling.
- Conditional diffusion U-Net decoder (cross-attention to encoder tokens), training step.
- Physics-guided DDIM sampling (S samples x K steps, data-consistency gradient through J).
Numbers here are timings on the demo data, not accuracy results.
Runs on CUDA or CPU. Env knobs (defaults reproduce the amax GPU run): DEVICE (cuda if available, else cpu),
AMP (bf16 | fp32; default bf16 on cuda, fp32 on cpu), BATCH (64), CHANNELS_LAST (0), COMPILE (0), MKLDNN (1), KML_CONV (0: 1 = U-Net convs as im2col + KML GEMM, kml_ops.py), KML_LINEAR (0) with LINEAR_DTYPE (fp32),
CKPT (0: 1 = activation checkpointing per encoder layer, ~1/6 of the activation memory for one extra layer forward),
SAMPLING (1: time guided sampling), GN (1: time the GN/NOSER baseline), REPS (20 timed training steps).
"""
import os, sys, json, time, math, glob, resource, platform
from runner import barrier as wait_barrier, publish_result
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

O = sys.argv[1]
CASES = sys.argv[2].split(',')
dev = os.environ.get('DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
AMP = os.environ.get('AMP', 'bf16' if dev == 'cuda' else 'fp32')
BATCH = int(os.environ.get('BATCH', 64)); REPS = int(os.environ.get('REPS', 20))
CL = os.environ.get('CHANNELS_LAST', '0') == '1'; COMPILE = os.environ.get('COMPILE', '0') == '1'
SAMPLING = os.environ.get('SAMPLING', '1') == '1'; GN = os.environ.get('GN', '1') == '1'
if os.environ.get('MKLDNN') == '0': torch.backends.mkldnn.enabled = False   # conv via im2col + BLAS sgemm_
BELTS = os.environ.get('BELTS', '16_adjacent,32_skip4').split(','); PARTS = os.environ.get('PARTS', 'pre,dec').split(',')
CKPT = os.environ.get('CKPT', '0') == '1'
KML_LINEAR = os.environ.get('KML_LINEAR', '0') == '1'   # all F.linear via KML (kml_ops; LINEAR_DTYPE fp32|bf16)
if KML_LINEAR:
    import kml_ops; kml_ops.patch_linear()


def amp():
    return torch.autocast(dev, torch.bfloat16, enabled=AMP == 'bf16')


def tt(a):
    """numpy -> torch via raw bytes (torch/numpy ABI mismatch in this env breaks torch.tensor(ndarray))."""
    a = np.ascontiguousarray(a, np.float32)
    return torch.frombuffer(bytearray(a.tobytes()), dtype=torch.float32).reshape(a.shape).to(dev)
torch.manual_seed(0); np.random.seed(0)
IMG = 64


def load():
    D = {}
    for c in CASES:
        z = np.load(os.path.join(O, 'cases', c, 'frames.npz'))
        D[c] = {k: z[k] for k in z.files}
    return D


def timed(fn, n=1, sync=dev == 'cuda'):
    if sync: torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(n): r = fn()
    if sync: torch.cuda.synchronize()
    return (time.perf_counter() - t0) / n, r


# ------------------------------------------------------------------ baseline: one-step GN + NOSER
def gn_noser(D, out):
    res = {}
    for belt in ('16_adjacent', '32_skip4'):
        pre, per, errs = [], [], []
        for c, d in D.items():
            J = d[f'{belt}_J_img'].astype(np.float64)
            dv = (d[f'{belt}_v_cur'] - d[f'{belt}_v_ref']).astype(np.float64)
            t0 = time.perf_counter()
            JtJ = J.T @ J
            lam = 1e-2 * np.trace(JtJ) / JtJ.shape[0]       # fixed demo hyperparameter, not tuned
            Rm = np.linalg.solve(JtJ + lam * np.diag(np.diag(JtJ)) + 1e-12 * np.eye(len(JtJ)), J.T)
            pre.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            X = dv @ Rm.T
            per.append((time.perf_counter() - t0) / len(dv))
            Y = d['images'].reshape(len(dv), -1)
            errs += list(np.linalg.norm(X - Y, axis=1) / np.maximum(np.linalg.norm(Y, axis=1), 1e-12))
        res[belt] = dict(precompute_s_per_subject=float(np.mean(pre)), per_frame_ms=float(np.mean(per) * 1e3),
                         demo_rel_error_median=float(np.median(errs)), n_frames=len(errs))
    out['gn_noser'] = res


# ------------------------------------------------------------------ EIT-FM encoder
class Encoder(nn.Module):
    def __init__(self, width=512, depth=12, heads=8, nfreq=8):
        super().__init__()
        self.nfreq = nfreq
        self.val = nn.Linear(1, width)
        self.pos = nn.Linear(4 * 2 * nfreq + 1, width)
        self.mask_tok = nn.Parameter(torch.zeros(width))
        layer = nn.TransformerEncoderLayer(width, heads, 4 * width, 0.0, batch_first=True, norm_first=True)
        self.tf = nn.TransformerEncoder(layer, depth)
        self.head_v = nn.Linear(width, 1)
        self.head_coarse = nn.Linear(width, 16 * 16)

    def pe(self, ang, belt):
        f = torch.arange(1, self.nfreq + 1, device=ang.device).float()
        a = ang[..., None] * f
        return torch.cat([torch.sin(a).flatten(-2), torch.cos(a).flatten(-2), belt[..., None]], -1)

    def forward(self, v, ang, belt, mask=None):
        t = self.val(v[..., None]) + self.pos(self.pe(ang, belt))
        if mask is not None:
            t = torch.where(mask[..., None], self.mask_tok.expand_as(t), t)
        return self.tf(t)


def protocol_angles(L, skip):
    drives = [(i, (i + skip) % L) for i in range(L)]
    ang = []
    for a, b in drives:
        for c, e in drives:
            if not ({a, b} & {c, e}):
                ang.append([a, b, c, e])
    return torch.tensor(ang, dtype=torch.float32) * 2 * math.pi / L


# ------------------------------------------------------------------ diffusion U-Net with cross-attention
class Block(nn.Module):
    def __init__(self, ci, co, tdim, ctx=None):
        super().__init__()
        self.n1, self.c1 = nn.GroupNorm(32, ci), nn.Conv2d(ci, co, 3, padding=1)
        self.t = nn.Linear(tdim, co)
        self.n2, self.c2 = nn.GroupNorm(32, co), nn.Conv2d(co, co, 3, padding=1)
        self.skip = nn.Conv2d(ci, co, 1) if ci != co else nn.Identity()
        self.attn = nn.MultiheadAttention(co, 8, kdim=ctx, vdim=ctx, batch_first=True) if ctx else None
        self.na = nn.GroupNorm(32, co) if ctx else None

    def forward(self, x, t, h):
        y = self.c1(F.silu(self.n1(x))) + self.t(t)[..., None, None]
        y = self.c2(F.silu(self.n2(y))) + self.skip(x)
        if self.attn is not None:
            B, C, H, W = y.shape
            q = self.na(y).flatten(2).transpose(1, 2)
            y = y + self.attn(q, h, h, need_weights=False)[0].transpose(1, 2).reshape(B, C, H, W)
        return y


class UNet(nn.Module):
    def __init__(self, ch=(128, 256, 256, 512), ctx=512, tdim=512):
        super().__init__()
        self.tdim = tdim
        self.tm = nn.Sequential(nn.Linear(tdim, tdim), nn.SiLU(), nn.Linear(tdim, tdim))
        self.inp = nn.Conv2d(1, ch[0], 3, padding=1)
        self.down, self.up = nn.ModuleList(), nn.ModuleList()
        c = ch[0]; skips = []
        for i, co in enumerate(ch):
            self.down.append(Block(c, co, tdim, ctx if i >= 2 else None)); c = co; skips.append(c)
        self.mid = Block(c, c, tdim, ctx)
        for i, co in reversed(list(enumerate(ch))):
            self.up.append(Block(c + skips[i], co, tdim, ctx if i >= 2 else None)); c = co
        self.out = nn.Sequential(nn.GroupNorm(32, c), nn.SiLU(), nn.Conv2d(c, 1, 3, padding=1))

    def temb(self, t):
        half = self.tdim // 2
        f = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
        a = t[:, None].float() * f
        return self.tm(torch.cat([a.sin(), a.cos()], 1))

    def forward(self, x, t, h):
        te = self.temb(t); x = self.inp(x); hs = []
        for i, b in enumerate(self.down):
            x = b(x, te, h); hs.append(x)
            if i < len(self.down) - 1: x = F.avg_pool2d(x, 2)
        x = self.mid(x, te, h)
        for i, b in enumerate(self.up):
            s = hs.pop()
            if x.shape[-1] != s.shape[-1]: x = F.interpolate(x.float(), size=s.shape[-2:]).to(s.dtype)
            x = b(torch.cat([x, s], 1), te, h)
        return self.out(x)


def nparams(m):
    return sum(p.numel() for p in m.parameters()) / 1e6


def barrier(name):
    """Bounded, rank-aware barrier with peer failure propagation."""
    wait_barrier(name)


def main():
    D = load()
    hw = torch.cuda.get_device_name(0) if dev == 'cuda' else f'{platform.machine()} cpu, {torch.get_num_threads()} threads'
    out = dict(gpu=hw, device=dev, torch=torch.__version__, cases=CASES,
               config=dict(amp=AMP, batch=BATCH, channels_last=CL, compile=COMPILE, reps=REPS,
                           kml_conv=os.environ.get('KML_CONV', '0') == '1', kml_blas=os.environ.get('KML_BLAS_LIB', ''),
                           ckpt=CKPT, kml_linear=KML_LINEAR, linear_dtype=os.environ.get('LINEAR_DTYPE', 'fp32') if KML_LINEAR else None))
    if GN: gn_noser(D, out)

    enc = Encoder().to(dev); dec = UNet().to(dev)
    if CKPT:                                       # recompute each layer in backward; parameters and keys unchanged
        from torch.utils.checkpoint import checkpoint
        for l in enc.tf.layers:
            l.forward = lambda *a, _f=l.forward, **k: checkpoint(_f, *a, use_reentrant=False, **k)
    if CL: dec = dec.to(memory_format=torch.channels_last)
    if out['config']['kml_conv']:
        import kml_ops; out['config']['kml_convs_swapped'] = kml_ops.swap_convs(dec)
    out['params_M'] = dict(encoder=nparams(enc), decoder=nparams(dec))
    opt = torch.optim.AdamW(list(enc.parameters()) + list(dec.parameters()), 1e-4)
    encf, decf = (torch.compile(enc), torch.compile(dec)) if COMPILE else (enc, dec)
    T = 1000
    beta = torch.linspace(1e-4, 0.02, T, device=dev); abar = torch.cumprod(1 - beta, 0)
    imgs = tt(np.concatenate([d['images'] for d in D.values()]))
    scale = imgs.abs().max()

    for belt, (L, skip) in {'16_adjacent': (16, 1), '32_skip4': (32, 5)}.items():
        if belt not in BELTS: continue
        dv = np.concatenate([d[f'{belt}_v_cur'] - d[f'{belt}_v_ref'] for d in D.values()])
        vr = np.concatenate([d[f'{belt}_v_ref'] for d in D.values()])
        x = tt(dv / np.abs(vr).mean(1, keepdims=True))
        ang = protocol_angles(L, skip).to(dev); M = ang.shape[0]
        R = {}
        for B in (BATCH,):
            idx = torch.randint(0, len(x), (B,), device=dev)
            v = x[idx] * 1e2; a = ang.expand(B, M, 4); bt = torch.full((B, M), float(L == 32), device=dev)
            y0 = (imgs[idx] / scale)[:, None]
            if CL: y0 = y0.contiguous(memory_format=torch.channels_last)

            def pre_step():
                mask = torch.rand(B, M, device=dev) < 0.5
                with amp():
                    h = encf(v, a, bt, mask)
                    loss = F.mse_loss(enc.head_v(h)[..., 0][mask], v[mask]) + \
                        F.mse_loss(enc.head_coarse(h.mean(1)), F.adaptive_avg_pool2d(y0, 16).flatten(1))
                opt.zero_grad(); loss.backward(); opt.step()

            def dec_step():
                t = torch.randint(0, T, (B,), device=dev); e = torch.randn_like(y0)
                xt = abar[t].sqrt()[:, None, None, None] * y0 + (1 - abar[t]).sqrt()[:, None, None, None] * e
                with amp():
                    h = encf(v, a, bt)
                    loss = F.mse_loss(decf(xt, t, h), e)
                opt.zero_grad(); loss.backward(); opt.step()

            for f in (pre_step, dec_step): f(); f()          # warm-up
            if dev == 'cuda': torch.cuda.reset_peak_memory_stats()
            if 'pre' in PARTS:
                barrier(f'{belt}_pre'); tp, _ = timed(pre_step, REPS)
                R[f'pretrain_step_s_B{B}'] = tp; R['pretrain_frames_per_s'] = B / tp
            if 'dec' in PARTS:
                barrier(f'{belt}_dec'); td, _ = timed(dec_step, REPS)
                R[f'decoder_step_s_B{B}'] = td; R['decoder_frames_per_s'] = B / td
            R['peak_mem_GB'] = torch.cuda.max_memory_allocated() / 1e9 if dev == 'cuda' else \
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6     # CPU: process peak RSS
        if not SAMPLING:
            out[belt] = R; continue

        # physics-guided DDIM sampling for one frame: S samples, K steps, data-consistency gradient through J
        J = tt(D[CASES[0]][f'{belt}_J_img'])
        dvf = tt(D[CASES[0]][f'{belt}_v_cur'][0] - D[CASES[0]][f'{belt}_v_ref'][0])
        for S, K in ((16, 50), (4, 20)):
            def sample():
                with torch.no_grad(), amp():
                    h = encf(x[:1] * 1e2, ang[None], torch.full((1, M), float(L == 32), device=dev)).expand(S, -1, -1)
                xt = torch.randn(S, 1, IMG, IMG, device=dev)
                ts = torch.linspace(T - 1, 0, K, device=dev).long()
                for i, t in enumerate(ts):
                    xt = xt.detach().requires_grad_(True)
                    with amp():
                        eps = decf(xt, t.expand(S), h).float()
                    x0 = (xt - (1 - abar[t]).sqrt() * eps) / abar[t].sqrt()
                    r = ((dvf - (x0.flatten(1) * scale) @ J.T) ** 2).sum()
                    g = torch.autograd.grad(r, xt)[0]
                    an = abar[ts[i + 1]] if i + 1 < K else torch.tensor(1.0, device=dev)
                    xt = an.sqrt() * x0 + (1 - an).sqrt() * eps - 1e-3 * g / (g.norm() + 1e-12)
                return xt.mean(0), xt.std(0)
            sample()
            ts_, _ = timed(sample, 3)
            R[f'guided_sampling_ms_per_frame_S{S}_K{K}'] = ts_ * 1e3
        out[belt] = R
    publish_result(out, O)
    print(json.dumps(out, indent=1, default=float))


if __name__ == '__main__':
    os.makedirs(os.path.join(O, 'reports'), exist_ok=True)
    main()
