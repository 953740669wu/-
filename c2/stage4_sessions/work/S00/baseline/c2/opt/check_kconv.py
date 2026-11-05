"""KConv2d (im2col + KML) vs F.conv2d: forward and gradients, then timing of the U-Net convs. argv: none."""
import time, torch, torch.nn as nn, torch.nn.functional as F
import kml_ops
torch.manual_seed(0)
for (B, ci, co, H, k) in ((4, 32, 64, 16, 3), (64, 256, 256, 32, 3), (64, 512, 256, 64, 1), (64, 256, 128, 64, 3)):
    c = nn.Conv2d(ci, co, k, padding=k // 2); kc = nn.Conv2d(ci, co, k, padding=k // 2); kc.load_state_dict(c.state_dict())
    kml_ops.swap_convs(nn.Sequential(kc)) if False else None
    m = nn.Sequential(kc); kml_ops.swap_convs(m); kc = m[0]
    x = torch.randn(B, ci, H, H, requires_grad=True); x2 = x.detach().clone().requires_grad_(True)
    g = torch.randn(B, co, H, H)
    def run(mod, xx):
        mod.zero_grad(); y = mod(xx); y.backward(g); return y
    t0 = time.perf_counter(); y1 = run(c, x); t1 = time.perf_counter(); y2 = run(kc, x2); t2 = time.perf_counter()
    t3 = time.perf_counter(); run(c, x); t4 = time.perf_counter(); run(kc, x2); t5 = time.perf_counter()
    r = lambda a, b: float((a - b).abs().max() / b.abs().max())
    print(f'B{B} {ci}->{co} {H}x{H} k{k}: y {r(y2, y1):.1e} dx {r(x2.grad, x.grad):.1e} dw {r(kc.weight.grad, c.weight.grad):.1e} '
          f'db {r(kc.bias.grad, c.bias.grad):.1e} | fwd+bwd onednn {t4 - t3:.3f} s  kml {t5 - t4:.3f} s', flush=True)
