"""cblas_sgemm GFLOP/s of a shared BLAS library via ctypes. argv: <lib path> <n> [reps]. Checks C against numpy."""
import ctypes, sys, time, numpy as np
lib = ctypes.CDLL(sys.argv[1]); n = int(sys.argv[2]); reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
A = np.random.rand(n, n).astype(np.float32); B = np.random.rand(n, n).astype(np.float32); C = np.zeros((n, n), np.float32)
p = lambda x: x.ctypes.data_as(ctypes.c_void_p)
f = lib.cblas_sgemm
f.argtypes = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
call = lambda: f(101, 111, 111, n, n, n, 1.0, p(A), n, p(B), n, 0.0, p(C), n)
call(); t0 = time.perf_counter()
for _ in range(reps): call()
dt = (time.perf_counter() - t0) / reps
ref = A[:64].astype(np.float64) @ B.astype(np.float64)
err = float(np.abs(C[:64] - ref).max() / np.abs(ref).max())
print(f'{sys.argv[1].split("/")[-2] + "/" + sys.argv[1].split("/")[-1]:45s} n={n} {2 * n ** 3 / dt / 1e9:9.1f} GFLOP/s relerr {err:.1e}', flush=True)
