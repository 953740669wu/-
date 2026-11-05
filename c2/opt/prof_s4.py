"""Operator profile of one s4_models training step on CPU. Env: L (16|32), PART (pre|dec), AMP (fp32|bf16), B (64).
pre = masked-pretraining step (encoder + heads), dec = decoder step (encoder + U-Net). Prints wall time of the
profiled step and the top operators by self CPU time, with input shapes for the top bf16 offenders."""
import os, sys, time
import torch, torch.nn.functional as F
sys.argv = [sys.argv[0], '/nonexistent', 'x']
import s4_models as S
L = int(os.environ.get('L', 32)); PART = os.environ.get('PART', 'pre'); AMP = os.environ.get('AMP', 'fp32')
B = int(os.environ.get('B', 64))
torch.manual_seed(0)
ang = S.protocol_angles(L, 1 if L == 16 else 5); M = ang.shape[0]
enc, dec = S.Encoder(), S.UNet()
v = torch.randn(B, M); a = ang.expand(B, M, 4); bt = torch.full((B, M), float(L == 32))
y0 = torch.randn(B, 1, 64, 64); t = torch.randint(0, 1000, (B,))
opt = torch.optim.AdamW(list(enc.parameters()) + list(dec.parameters()), 1e-4)
amp = lambda: torch.autocast('cpu', torch.bfloat16, enabled=AMP == 'bf16')


def step():
    with amp():
        if PART == 'pre':
            mask = torch.rand(B, M) < 0.5
            h = enc(v, a, bt, mask)
            loss = F.mse_loss(enc.head_v(h)[..., 0][mask], v[mask]) + \
                F.mse_loss(enc.head_coarse(h.mean(1)), F.adaptive_avg_pool2d(y0, 16).flatten(1))
        else:
            loss = F.mse_loss(dec(y0, t, enc(v, a, bt)), y0)
    opt.zero_grad(); loss.backward(); opt.step()


print(f'== L={L} M={M} PART={PART} AMP={AMP} B={B} threads={torch.get_num_threads()}', flush=True)
t0 = time.perf_counter(); step(); print(f'warm-up step {time.perf_counter() - t0:.2f} s', flush=True)
from torch.profiler import profile, ProfilerActivity
with profile(activities=[ProfilerActivity.CPU], record_shapes=True) as prof:
    t0 = time.perf_counter(); step(); dt = time.perf_counter() - t0
print(f'profiled step {dt:.2f} s', flush=True)
ka = prof.key_averages()
print(ka.table(sort_by='self_cpu_time_total', row_limit=16), flush=True)
print(prof.key_averages(group_by_input_shape=True).table(sort_by='self_cpu_time_total', row_limit=8, max_name_column_width=40,
                                                          max_shapes_column_width=90), flush=True)
