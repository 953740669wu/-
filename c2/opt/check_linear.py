"""KML linear (kml_ops.patch_linear) vs stock F.linear: one encoder+decoder training step (loss, every gradient),
fp32 and bf16, then fwd+bwd time of the step. Env: L (belt electrodes), B. Uses s4_models' networks."""
import os, sys, time, copy
import torch, torch.nn.functional as F
sys.argv = [sys.argv[0], '/nonexistent', 'x']
import s4_models as S, kml_ops
L = int(os.environ.get('L', 16)); B = int(os.environ.get('B', 16))
torch.manual_seed(0)
ang = S.protocol_angles(L, 1 if L == 16 else 5); M = ang.shape[0]
enc0, dec0 = S.Encoder(), S.UNet()
v = torch.randn(B, M); a = ang.expand(B, M, 4); bt = torch.full((B, M), float(L == 32))
y0 = torch.randn(B, 1, 64, 64); t = torch.randint(0, 1000, (B,))


def run(mode):
    enc, dec = copy.deepcopy(enc0), copy.deepcopy(dec0)
    F.linear = kml_ops._linear if mode == 'stock' else kml_ops.kml_linear
    kml_ops.LINEAR_DTYPE = torch.bfloat16 if mode == 'bf16' else torch.float32
    def step():
        enc.zero_grad(); dec.zero_grad()
        loss = F.mse_loss(dec(y0, t, enc(v, a, bt)), y0); loss.backward(); return loss
    step(); t0 = time.perf_counter(); loss = step(); dt = time.perf_counter() - t0
    g = torch.cat([p.grad.flatten() for p in list(enc.parameters()) + list(dec.parameters()) if p.grad is not None])
    return float(loss), g, dt


ref = run('stock')
for mode in ('fp32', 'bf16'):
    loss, g, dt = run(mode)
    print(f'L{L} B{B} {mode}: loss {loss:.6f} vs stock {ref[0]:.6f} (rel {abs(loss - ref[0]) / ref[0]:.1e}), '
          f'grad rel {float((g - ref[1]).norm() / ref[1].norm()):.1e}, step {dt:.2f} s vs stock {ref[2]:.2f} s', flush=True)
