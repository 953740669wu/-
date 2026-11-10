"""Port only the frozen 11-08 BF16 tile kernels to the validated namespace ABI."""
from difflib import unified_diff
from pathlib import Path

from freeze_release import BASE, HERE, replace, sha


def checked(path, digest):
    raw = path.read_bytes()
    assert sha(raw) == digest
    return raw.decode()


def kernel(ns, external):
    header = ns[ns.index('#define _GNU_SOURCE'):ns.index('/* o = softmax(')]
    header = replace(header, 'typedef void (*sgemm_t)(int, int, int, int, int, int, float, const float *, int, const float *, int, float, float *, int);\nstatic sgemm_t sg;',
                     'typedef void (*sbgemm_t)(int, int, int, int, int, int, float, const uint16_t *, int, const uint16_t *, int, float, float *, int);\nstatic sbgemm_t sbg;')
    header = replace(header, '    if (!f) return -1;', '    if (!f) {\n        if (h) dlclose(h);\n        return -1;\n    }')
    header = header.replace('"cblas_sgemm"','"cblas_sbgemm"').replace('sg = (sgemm_t)f;', 'sbg = (sbgemm_t)f;')
    header = header.replace('!sg ||', '!sbg ||').replace('(void *)sg', '(void *)sbg')
    tail = external[external.index('/* ---------------------------------------------------------------- bf16 variant'):]
    tail = tail.replace('void kml_attn_fwd_bf(', 'int kml_attn_fwd_bf(').replace('void kml_attn_bwd_bf(', 'int kml_attn_bwd_bf(')
    for old, new in (
        ('float *lse) {','float *lse, unsigned long *tiles) {'),
        ('float *dv, long dv0, long dv1, long dv2) {','float *dv, long dv0, long dv1, long dv2, unsigned long *tiles) {'),
        ('    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2};',
         '    if (!sbg || bq != 16) return -2;\n    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2};'),
        ('    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2}, O = {o, o0, o1, o2}, G = {g, g0, g1, g2};',
         '    if (!sbg || bq != 16) return -2;\n    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2}, O = {o, o0, o1, o2}, G = {g, g0, g1, g2};'),
        ('    if (qb && kb && vb) {','    int failed = !qb || !kb || !vb;\n    unsigned long count = 0;\n    if (!failed) {'),
        ('    if (D && qb && kb && vb && gb) {','    int failed = !D || !qb || !kb || !vb || !gb;\n    unsigned long count = 0;\n    if (!failed) {'),
        ('            if (posix_memalign((void **)&pb, 64, sizeof(uint16_t) * (size_t)bq * Nk)) pb = 0;',
         '            if (posix_memalign((void **)&pb, 64, sizeof(uint16_t) * (size_t)bq * Nk)) pb = 0;\n            failed = !s || !pb;'),
        ('            if (pb) sb = pb + n;', '            if (pb) sb = pb + n;\n            failed = !p || !pb;'),
        ('sbg(ROW, N_, N_, m, d, Nk, 1.0f, pb, Nk, vb + (size_t)bh * Nk * d, d, 0.0f, op, o2);',
         'sbg(ROW, N_, N_, m, d, Nk, 1.0f, pb, Nk, vb + (size_t)bh * Nk * d, d, 0.0f, op, o2);\n                count++;'),
        ('/* dK = scale dS^T Q */', '/* dK = scale dS^T Q */\n                count++;'),
        ('/* dQ = scale dS K */', '/* dQ = scale dS K */\n                count++;'),
    ):
        tail = replace(tail, old, new)
    assert tail.count('        #pragma omp parallel\n') == 2
    tail = tail.replace('        #pragma omp parallel\n', '        #pragma omp parallel reduction(|:failed) reduction(+:count)\n')
    for direction in ('fwd', 'bwd'):
        line = f'    prof_print("{direction} bf16", B, H, Nq, Nk, bq);'
        tail = replace(tail, line, line+'\n    *tiles = count;\n    return failed ? -1 : 0;')
    return '/* 11-08 BF16 tiles with the frozen C2 locking namespace and checked native ABI. */\n'+header+tail


def dispatch(code):
    code = code.replace('Isolated FP32 dispatch', 'Isolated BF16-tile dispatch').replace('BQ = 64', 'BQ = 16')
    code = replace(code, "        for name in ('library', 'locking_kml'):",
                   "        if info['bq'] != BQ or info['bf16'] != 1:\n            raise RuntimeError('wrong BF16/BQ16 build receipt')\n        for name in ('library', 'locking_kml'):")
    code = code.replace('self.lib.kml_attn_fwd\n', 'self.lib.kml_attn_fwd_bf\n').replace('self.lib.kml_attn_bwd\n', 'self.lib.kml_attn_bwd_bf\n')
    code = code.replace('head + v * 4 + [ctypes.c_void_p]', 'head + v * 4 + [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]')
    code = code.replace('head + v * 5 + [ctypes.c_void_p] + v * 3', 'head + v * 5 + [ctypes.c_void_p] + v * 3 + [ctypes.POINTER(ctypes.c_ulong)]')
    code = code.replace('and SGEMM owner', 'and SBGEMM owner').replace('gemm_address=gemm.value', 'gemm_address=gemm.value, symbol="cblas_sbgemm"')
    code = code.replace('dict(forward=0, backward=0)', 'dict(forward=0, backward=0, forward_tiles=0, backward_tiles=0)')
    code = replace(code, '        status = getattr(self, direction)(*args)',
                   '        tiles = ctypes.c_ulong()\n        status = getattr(self, direction)(*args, ctypes.byref(tiles))')
    code = replace(code, "            raise RuntimeError(f'FP32 fused attention {direction} native status {status}')\n        self.counts[direction] += 1", '''            raise RuntimeError(f'BF16 fused attention {direction} native status {status}')
        batch, heads, nq, nk, _, _, bq = args[:7]
        expected = batch * heads * ((nq + bq - 1) // bq)
        if direction == 'backward':
            expected += batch * heads * ((nk + bq - 1) // bq)
        if bq != BQ or tiles.value != expected:
            raise RuntimeError(f'{direction} wrong BF16 tile count: {tiles.value}, expected {expected}')
        self.counts[direction] += 1
        self.counts[direction + '_tiles'] += tiles.value''')
    return code


if __name__ == '__main__':
    external = checked(Path('E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/kml_attn.c'),
                       '8bd18a4380d794eabab20c9387ff1005434ae544e7b64450106cf4b343bdac74')
    ns = checked(BASE/'received/kml_attn.c', '1569473ddf6fe7fe0ba66f4f5a6137aac7ff10bd4ea5741388dd6429c1933e4a')
    prior = checked(BASE/'received/payload/attn_dispatch.py', '69ed365b88d29cb365f8b4ea13a85e17c92e287af2ef9bf3040b37c5993265fc')
    out = HERE/'bf16_source'
    (out/'payload').mkdir(parents=True)
    new = kernel(ns, external)
    (out/'kml_attn.c').write_bytes(new.encode())
    (out/'payload/attn_dispatch.py').write_bytes(dispatch(prior).encode())
    (out/'UPSTREAM_KERNEL.diff').write_bytes(''.join(unified_diff(external.splitlines(True),new.splitlines(True),
          '11-08/c2/opt/kml_attn.c','bf16_source/kml_attn.c')).encode())
