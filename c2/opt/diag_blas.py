"""Matmul / conv / attention throughput of the torch CPU build under the current env (threads, OPENBLAS_CORETYPE,
mkldnn on/off). One line per kernel: GFLOP/s."""
import os, time, glob
import torch, torch.nn.functional as F


def rate(name, fn, flop, n=3):
    fn(); t0 = time.perf_counter()
    for _ in range(n): fn()
    dt = (time.perf_counter() - t0) / n
    print(f'  {name:34s} {dt * 1e3:9.1f} ms {flop / dt / 1e9:9.1f} GFLOP/s', flush=True)


tag = ' '.join(f'{k}={os.environ[k]}' for k in ('OMP_NUM_THREADS', 'OPENBLAS_CORETYPE', 'MKLDNN', 'ONEDNN_DEFAULT_FPMATH_MODE') if k in os.environ)
print(f'== {tag} threads={torch.get_num_threads()} mkldnn={torch.backends.mkldnn.enabled}', flush=True)
if os.environ.get('MKLDNN') == '0': torch.backends.mkldnn.enabled = False
n = 2048
for dt in (torch.float32, torch.bfloat16):
    A, B = torch.randn(n, n, dtype=dt), torch.randn(n, n, dtype=dt)
    rate(f'matmul {n} {dt}', lambda: A @ B, 2 * n ** 3)
    W = torch.randn(512, 2048, dtype=dt); X = torch.randn(64 * 208, 512, dtype=dt)
    rate(f'linear 13312x512x2048 {dt}', lambda: F.linear(X, W.T.contiguous().T), 2 * 13312 * 512 * 2048)
    x = torch.randn(64, 256, 32, 32, dtype=dt); w = torch.randn(256, 256, 3, 3, dtype=dt)
    rate(f'conv3x3 64x256x32x32 {dt}', lambda: F.conv2d(x, w, padding=1), 2 * 64 * 256 * 256 * 9 * 32 * 32)
