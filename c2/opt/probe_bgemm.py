"""Find cblas_bgemm's calling convention empirically (no header on C2): alpha/beta as fp32 vs bf16 (low half of the
FP register), C as fp32 vs bf16. Small GEMM vs a float64 reference of the bf16-rounded inputs."""
import os, ctypes, struct, torch
lib = ctypes.CDLL(os.environ['KML_BLAS_LIB'], mode=ctypes.RTLD_LOCAL)
f = getattr(lib, os.environ.get('FN', 'cblas_bgemm'))
f.argtypes = [ctypes.c_int] * 6 + [ctypes.c_float, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                                   ctypes.c_float, ctypes.c_void_p, ctypes.c_int]
bfbits = lambda x: struct.unpack('<f', struct.pack('<I', struct.unpack('<I', struct.pack('<f', x))[0] >> 16))[0]
torch.manual_seed(0)
M, N, K = 64, 48, 32
A = torch.randn(M, K).bfloat16(); B = torch.randn(K, N).bfloat16()
ref = (A.double() @ B.double())
for tn, (Ai, Bi) in (('A,B bf16', (A, B)), ('A bf16 B fp32', (A, B.float())), ('A fp32 B bf16', (A.float(), B))):
  print('--', tn, flush=True)
  for an, (al, be) in (('fp32 alpha', (1.0, 0.0)), ('bf16 alpha', (bfbits(1.0), bfbits(0.0)))):
      for cn, C in (('C fp32', torch.full((M, N), 7.0)), ('C bf16', torch.full((M, N), 7.0).bfloat16())):
          f(101, 111, 111, M, N, K, al, Ai.data_ptr(), K, Bi.data_ptr(), N, be, C.data_ptr(), N)
          err = float((C.double() - ref).abs().max() / ref.abs().max())
          print(f'{an:11s} {cn}: rel err {err:.2e}  C[0,:3] {C[0, :3].tolist()}  ref {ref[0, :3].tolist()}', flush=True)
