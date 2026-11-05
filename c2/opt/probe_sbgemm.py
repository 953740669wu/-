"""Where does cblas_sbgemm (standard OpenBLAS signature per its disassembly) go wrong? Error map on small GEMMs, C
over-allocated with a guard band to catch out-of-bounds writes."""
import os, ctypes, torch
lib = ctypes.CDLL(os.environ['KML_BLAS_LIB'], mode=ctypes.RTLD_LOCAL)
f = lib.cblas_sbgemm
f.argtypes = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                                   ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
torch.manual_seed(0)
for M, N, K in ((32, 32, 32), (64, 48, 32), (64, 64, 64), (128, 128, 256)):
    A = torch.randn(M, K).bfloat16(); B = torch.randn(K, N).bfloat16(); ref = A.double() @ B.double()
    buf = torch.full((M * N * 4,), 7.0); C = buf[:M * N].view(M, N)
    f(101, 111, 111, M, N, K, 1.0, A.data_ptr(), K, B.data_ptr(), N, 0.0, C.data_ptr(), N)
    bad = ((C.double() - ref).abs() > 1e-3 * ref.abs().max())
    rows = bad.any(1).nonzero().flatten().tolist(); cols = bad.any(0).nonzero().flatten().tolist()
    print(f'{M}x{N}x{K}: bad {int(bad.sum())}/{M*N}  rows {rows[:8]}..{len(rows)}  cols {cols[:8]}..{len(cols)}  '
          f'guard touched {int((buf[M*N:] != 7).sum())}', flush=True)
    if bad.any():
        i, j = bad.nonzero()[0].tolist(); r = ref[i, j].item()
        hits = (ref - C[i, j].double()).abs().argmin().item()
        print(f'   C[{i},{j}]={C[i,j].item():.4f} ref {r:.4f}; nearest ref entry at {divmod(hits, N)};'
              f' C col-major match? {torch.allclose(C.double().flatten(), ref.t().flatten(), atol=1e-3)}', flush=True)
