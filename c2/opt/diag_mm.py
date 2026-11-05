"""fp32/bf16 2048^3 matmul GFLOP/s at the current torch thread count (argv[1]: label)."""
import sys, time, torch
n = 2048
for dt in (torch.float32, torch.bfloat16):
    A, B = torch.randn(n, n, dtype=dt), torch.randn(n, n, dtype=dt); A @ B
    t0 = time.perf_counter()
    for _ in range(3): A @ B
    r = 3 * 2 * n ** 3 / (time.perf_counter() - t0) / 1e9
    print(f'{sys.argv[1]:48s} threads={torch.get_num_threads():3d} {str(dt):15s} {r:8.1f} GFLOP/s', flush=True)
