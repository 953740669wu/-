"""Stage 4 CPU diagnostic: wall time of single forward/backward pieces of the s4_models networks, then the top
operators of one decoder training step (torch.profiler). Prints as it goes. argv: <threads> <belt L>."""
import os, sys, time, math
import torch, torch.nn.functional as F
sys.argv = [sys.argv[0], '/nonexistent', 'x'] + sys.argv[1:]
import s4_models as S
L = int(sys.argv[3]) if len(sys.argv) > 3 else 16
torch.manual_seed(0)
if os.environ.get('MKLDNN') == '0': torch.backends.mkldnn.enabled = False   # conv -> im2col + sgemm_
print('threads', torch.get_num_threads(), 'interop', torch.get_num_interop_threads(), 'cap', torch.backends.cpu.get_cpu_capability(), flush=True)


def tm(name, fn, n=2):
    fn(); t0 = time.perf_counter()
    for _ in range(n): fn()
    print(f'{name:40s} {(time.perf_counter() - t0) / n:8.3f} s', flush=True)


B = 64
ang = S.protocol_angles(L, 1 if L == 16 else 5); M = ang.shape[0]
enc, dec = S.Encoder(), S.UNet()
v = torch.randn(B, M); a = ang.expand(B, M, 4); bt = torch.full((B, M), float(L == 32))
x = torch.randn(B, 1, 64, 64); t = torch.randint(0, 1000, (B,))
mm = lambda n: (torch.randn(n, n) @ torch.randn(n, n))
tm('matmul 2048^3 (fp32)', lambda: mm(2048))
tm('matmul 2048^3 (bf16)', lambda: torch.randn(2048, 2048, dtype=torch.bfloat16) @ torch.randn(2048, 2048, dtype=torch.bfloat16))
with torch.no_grad():
    tm(f'encoder fwd B{B} M{M}', lambda: enc(v, a, bt))
    h = enc(v, a, bt)
    y = dec(x, t, h).double()
    print('checksum enc', h.double().norm().item(), 'dec', y.norm().item(), y.sum().item(), flush=True)
    tm(f'decoder fwd B{B}', lambda: dec(x, t, h))
for amp in (('fp32',) if os.environ.get('NOBF16') == '1' else ('fp32', 'bf16')):
    def step():
        with torch.autocast('cpu', torch.bfloat16, enabled=amp == 'bf16'):
            loss = F.mse_loss(dec(x, t, enc(v, a, bt)), x)
        loss.backward()
    tm(f'enc+dec fwd+bwd {amp}', step, 1)
from torch.profiler import profile, ProfilerActivity
with profile(activities=[ProfilerActivity.CPU]) as prof:
    loss = F.mse_loss(dec(x, t, enc(v, a, bt)), x); loss.backward()
print(prof.key_averages().table(sort_by='self_cpu_time_total', row_limit=18), flush=True)
