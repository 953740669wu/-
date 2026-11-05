"""Phase B2/C1: KML SME sgemm vs bgemm vs torch at the s4 linear-layer shapes, one domain. cblas_bgemm (no header on
C2; probe_bgemm.py + disassembly) is all-bf16: alpha/beta in h0/h1 and a bf16 C; it is checked against an fp32 GEMM of
the same bf16-rounded inputs. Env: KML_BLAS_LIB. argv: [reps]."""
import os, sys, time, ctypes, struct
import torch
reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
lib = ctypes.CDLL(os.environ['KML_BLAS_LIB'], mode=ctypes.RTLD_LOCAL)
argt = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                             ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
sg, bg, sb = lib.cblas_sgemm, lib.cblas_bgemm, lib.cblas_sbgemm   # sbgemm: bf16 A/B, fp32 alpha/beta/C (OpenBLAS form),
# but some tiles ignore beta=0 and accumulate into C (probe_sbgemm.py), so C is zeroed first (timed with the call)
sg.argtypes = bg.argtypes = sb.argtypes = argt
ROW, NT, T = 101, 111, 112
BF1, BF0 = (struct.unpack('<f', struct.pack('<I', b))[0] for b in (0x3F80, 0))   # bf16 1.0 / 0.0 in the low half
torch.manual_seed(0)


def call(f, a, b, c, ta, tb, M, N, K):
    one, zero = (BF1, BF0) if f is bg else (1.0, 0.0)
    f(ROW, T if ta else NT, T if tb else NT, M, N, K, one, a.data_ptr(), a.shape[1], b.data_ptr(), b.shape[1],
      zero, c.data_ptr(), N)


def timeit(fn):
    fn(); t0 = time.perf_counter()
    for _ in range(reps): fn()
    return (time.perf_counter() - t0) / reps


# (name, M, N, K, transA, transB): Linear y = x W^T (fwd), dX = dY W, dW = dY^T X; T tokens = 64 x 928 or 64 x 208
shapes = [('square 4096', 4096, 4096, 4096, False, False)]
for tok, tag in ((59392, '32b'), (13312, '16b')):
    for name, i, o in (('qkv', 512, 1536), ('ff1', 512, 2048), ('ff2', 2048, 512), ('out', 512, 512)):
        shapes += [(f'{tag} {name} fwd', tok, o, i, False, True), (f'{tag} {name} dX', tok, i, o, False, False),
                   (f'{tag} {name} dW', o, i, tok, True, False)]
print(f'threads {torch.get_num_threads()}  {"shape":18s} {"M":>6s} {"N":>5s} {"K":>6s}  sgemm TF/s  bgemm TF/s sbgemm TF/s  torch TF/s  bgemm relerr sbgemm relerr', flush=True)
for name, M, N, K, ta, tb in shapes:
    A = torch.randn(*((K, M) if ta else (M, K))); B = torch.randn(*((N, K) if tb else (K, N)))
    Ab, Bb = A.bfloat16(), B.bfloat16()
    C = torch.empty(M, N); Cb = torch.empty(M, N, dtype=torch.bfloat16); Cr = torch.empty(M, N)
    fl = 2 * M * N * K
    ts = timeit(lambda: call(sg, A, B, C, ta, tb, M, N, K))
    tb_ = timeit(lambda: call(bg, Ab, Bb, Cb, ta, tb, M, N, K))
    C2 = torch.empty(M, N)
    tsb = timeit(lambda: (C2.zero_(), call(sb, Ab, Bb, C2, ta, tb, M, N, K)))
    tt = timeit(lambda: (A.t() if ta else A) @ (B.t() if tb else B))
    call(sg, Ab.float().contiguous(), Bb.float().contiguous(), Cr, ta, tb, M, N, K)        # fp32 GEMM of bf16 inputs
    err = float((Cb.float() - Cr).abs().max() / Cr.abs().max())
    err2 = float((C2 - Cr).abs().max() / Cr.abs().max())
    print(f'           {name:18s} {M:6d} {N:5d} {K:6d}  {fl / ts / 1e12:10.2f}  {fl / tb_ / 1e12:10.2f}  {fl / tsb / 1e12:10.2f}  {fl / tt / 1e12:10.2f}  {err:.1e}  {err2:.1e}', flush=True)
