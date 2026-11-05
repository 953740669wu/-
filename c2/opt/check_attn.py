"""gemm_attention vs torch SDPA: outputs, gradients and fwd+bwd time at the s4 encoder/decoder shapes."""
import time, torch, torch.nn.functional as F
import kml_ops
torch.manual_seed(0)
sdpa = kml_ops._sdpa
for (B, H, N, Nk, d) in ((2, 2, 37, 53, 16), (64, 8, 208, 208, 64), (64, 8, 928, 928, 64), (64, 8, 256, 928, 64)):
    q, k, v = (torch.randn(B, H, n, d) for n in (N, Nk, Nk)); g = torch.randn(B, H, N, d)
    res = {}
    for name, fn in (('sdpa', sdpa), ('gemm', kml_ops.gemm_attention)):
        qq, kk, vv = (x.clone().requires_grad_(True) for x in (q, k, v))
        o = fn(qq, kk, vv); o.backward(g)                      # warm-up
        qq.grad = kk.grad = vv.grad = None
        t0 = time.perf_counter(); o = fn(qq, kk, vv); t1 = time.perf_counter(); o.backward(g); t2 = time.perf_counter()
        res[name] = (o.detach(), qq.grad, kk.grad, vv.grad, t1 - t0, t2 - t1)
    r = lambda a, b: float((a - b).abs().max() / b.abs().max())
    a, b = res['gemm'], res['sdpa']
    print(f'B{B} H{H} N{N} Nk{Nk} d{d}: o {r(a[0], b[0]):.1e} dq {r(a[1], b[1]):.1e} dk {r(a[2], b[2]):.1e} dv {r(a[3], b[3]):.1e} | '
          f'sdpa fwd {b[4]:.3f} bwd {b[5]:.3f} s, gemm fwd {a[4]:.3f} bwd {a[5]:.3f} s', flush=True)
