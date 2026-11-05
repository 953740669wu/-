"""Load KML SME kblas (multi) AFTER torch with ctypes (no interposition) and run cblas_sgemm on torch tensor
buffers next to torch's own matmul. argv: <n> ..."""
import ctypes, sys, time, torch
lib = ctypes.CDLL('/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so', mode=ctypes.RTLD_LOCAL)
f = lib.cblas_sgemm
f.argtypes = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
print('loaded; torch threads', torch.get_num_threads(), flush=True)
for n in map(int, sys.argv[1:]):
    A, B = torch.randn(n, n), torch.randn(n, n); C = torch.empty(n, n)
    kml = lambda: f(101, 111, 111, n, n, n, 1.0, A.data_ptr(), n, B.data_ptr(), n, 0.0, C.data_ptr(), n)
    for name, fn in (('torch', lambda: A @ B), ('kml', kml)):
        fn(); t0 = time.perf_counter()
        for _ in range(3): fn()
        print(f'{name:6s} n={n} {3 * 2 * n ** 3 / (time.perf_counter() - t0) / 1e9:8.1f} GFLOP/s', flush=True)
    print('  max rel diff kml vs torch', float((C - A @ B).abs().max() / (A @ B).abs().max()), flush=True)
