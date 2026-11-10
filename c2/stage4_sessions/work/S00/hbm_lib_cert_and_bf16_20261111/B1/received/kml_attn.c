/* 11-08 BF16 tiles with the frozen C2 locking namespace and checked native ABI. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <math.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*sbgemm_t)(int, int, int, int, int, int, float, const uint16_t *, int, const uint16_t *, int, float, float *, int);
static sbgemm_t sbg;
static void *locking_handle;
enum { ROW = 101, N_ = 111, T_ = 112 };

/* The tiles need a BLAS whose concurrent single-thread calls run in parallel. On C2 that is only KML's serial
   thread-safe build, sme/kblas/locking (bench_kblas_concurrent.c, 36 threads: 2.4 TFLOP/s together; nolocking
   serializes to 0.25, multi inside a parallel region likewise). It shares the soname libkblas.so.1 with the multi
   build torch's shim uses, so it is loaded in its own link namespace. Returns 0 on success (else the caller must stop). */
int kml_attn_load(const char *path) {
    void *h = dlmopen(LM_ID_NEWLM, path, RTLD_NOW | RTLD_LOCAL);
    void *f = h ? dlsym(h, "cblas_sbgemm") : 0;
    if (!f) {
        if (h) dlclose(h);
        return -1;
    }
    locking_handle = h;
    sbg = (sbgemm_t)f; return 0;
}

int kml_attn_locking_info(void **handle, long *namespace_id, const char **path, void **gemm) {
    struct link_map *map = NULL;
    Lmid_t id = LM_ID_BASE;
    Dl_info symbol;
    void *symbol_map = NULL;
    if (!locking_handle || !sbg || dlinfo(locking_handle, RTLD_DI_LMID, &id) != 0 || id == LM_ID_BASE ||
        dlinfo(locking_handle, RTLD_DI_LINKMAP, &map) != 0 || !map || !map->l_name || !*map->l_name ||
        !dladdr1((void *)sbg, &symbol, &symbol_map, RTLD_DL_LINKMAP) || symbol_map != map)
        return -1;
    *handle = locking_handle;
    *namespace_id = id;
    *path = map->l_name;
    *gemm = (void *)sbg;
    return 0;
}

/* exp(x) for x <= 0 (scores minus their row max or log-sum-exp): 2^n * e^r, r = x - n ln2, |r| <= ln2/2, degree-6
   Taylor (rel. error ~1e-7). Written so that gcc vectorizes the loops calling it (fmaxnm, frintx, fma, integer add
   on the bit pattern; build with -fno-math-errno), which the first version (union pun, add-subtract rounding) blocked:
   those loops took as long as the GEMMs (KML_ATTN_PROF, logs/opt_attn_prof.log). */
static inline float fexp(float x) {
    x = fmaxf(x, -87.0f);
    float n = __builtin_rintf(x * 1.44269504f);
    float r = fmaf(n, -0.693145752f, x); r = fmaf(n, -1.42860677e-6f, r);   /* Cody-Waite ln2 split */
    float p = 1.0f + r * (1.0f + r * (0.5f + r * (0.166666672f + r * (0.0416666679f + r * (0.00833333377f + r * 0.00138888892f)))));
    uint32_t i; memcpy(&i, &p, 4); i += (uint32_t)(int32_t)n << 23; memcpy(&p, &i, 4);
    return p;
}

typedef struct { const float *p; long s0, s1, s2; } view;
#define AT(v, b, h) ((v).p + (long)(b) * (v).s0 + (long)(h) * (v).s1)

/* KML_ATTN_PROF=1: per-call seconds summed over threads, split into sgemm and the elementwise loops, on stderr. */
static int prof = -1;
static double tg_, te_;
#define TIC(t) double t = prof ? omp_get_wtime() : 0
#define TOC(acc, t) do { if (prof) { double _n = omp_get_wtime(); acc += _n - t; t = _n; } } while (0)
static void prof_init(void) { if (prof < 0) prof = getenv("KML_ATTN_PROF") && atoi(getenv("KML_ATTN_PROF")); tg_ = te_ = 0; }
static void prof_print(const char *w, int B, int H, int Nq, int Nk, int bq) {
    if (prof) fprintf(stderr, "kml_attn %s B%d H%d Nq%d Nk%d bq%d: thread-s sgemm %.3f elementwise %.3f\n", w, B, H, Nq, Nk, bq, tg_, te_);
}

static int nested_off(void) { int l = omp_get_max_active_levels(); omp_set_max_active_levels(1); return l; }

/* KML_ATTN_GROUP: consecutive tiles (query or key chunks of one batch x head) per OpenMP task, so that the head's
   K/V (or Q/dO) stay in the thread's L2 (768 KB) across them instead of being re-read from memory for every tile;
   0 = all chunks of a head in one task. Default 1 (one tile per task). */
static int group(int nchunks) { const char *e = getenv("KML_ATTN_GROUP"); int g = e ? atoi(e) : 1; return g <= 0 ? nchunks : g; }

/* ---------------------------------------------------------------- bf16 variant (kml_attn_fwd_bf / kml_attn_bwd_bf)
   The roundings of CUDA flash attention under bf16 autocast: q, k, v, dO, P and dS in bf16; scores, softmax, D and
   every GEMM accumulator in fp32 (KML sbgemm: bf16 A/B, fp32 C). In the locking build, 36 concurrent single-thread
   sbgemms on these tile shapes run at 5.3-6.1 TFLOP/s against 1.9-2.4 for sgemm (logs/opt_kblas_concurrent2.log).
   Inputs and outputs stay fp32 (same views and API as the fp32 kernels); q/k/v/dO are cast once per call into
   contiguous (b, h, n, d) bf16 copies. sbgemm's C is always zeroed first (some tiles ignore beta = 0). */
static inline uint16_t f2b(float x) {
    uint32_t u; memcpy(&u, &x, 4); return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}

/* bf16 copy of a strided (B, H, N, d) view into contiguous memory; NULL on allocation failure. */
static uint16_t *cast_bhnd(view X, int B, int H, int N, int d) {
    uint16_t *y = 0;
    if (posix_memalign((void **)&y, 64, sizeof(uint16_t) * (size_t)B * H * N * d)) return 0;
    #pragma omp parallel for schedule(static)
    for (long r = 0; r < (long)B * H * N; r++) {
        long bh = r / N; int b = bh / H, h = bh % H, n = r % N;
        const float *x = AT(X, b, h) + (long)n * X.s2; uint16_t *o = y + r * d;
        #pragma omp simd
        for (int i = 0; i < d; i++) o[i] = f2b(x[i]);
    }
    return y;
}

static void zero_rows(float *p, int m, int n, long ld) { for (int i = 0; i < m; i++) memset(p + (long)i * ld, 0, sizeof(float) * n); }

int kml_attn_fwd_bf(int B, int H, int Nq, int Nk, int d, float scale, int bq,
                     const float *q, long q0, long q1, long q2, const float *k, long k0, long k1, long k2,
                     const float *v, long v0, long v1, long v2, float *o, long o0, long o1, long o2, float *lse, unsigned long *tiles) {
    if (!sbg || bq != 16) return -2;
    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2};
    int nc = (Nq + bq - 1) / bq, lv = nested_off(), gq = group(nc);
    prof_init();
    uint16_t *qb = cast_bhnd(Q, B, H, Nq, d), *kb = cast_bhnd(K, B, H, Nk, d), *vb = cast_bhnd(V, B, H, Nk, d);
    int failed = !qb || !kb || !vb;
    unsigned long count = 0;
    if (!failed) {
        #pragma omp parallel reduction(|:failed) reduction(+:count)
        {
            double tg = 0, te = 0;
            float *s = 0; uint16_t *pb = 0;
            if (posix_memalign((void **)&s, 64, sizeof(float) * (size_t)bq * Nk)) s = 0;
            if (posix_memalign((void **)&pb, 64, sizeof(uint16_t) * (size_t)bq * Nk)) pb = 0;
            failed = !s || !pb;
            #pragma omp for schedule(dynamic, gq)
            for (long it = 0; it < (long)B * H * nc; it++) {
                if (!s || !pb) continue;
                long bh = it / nc; int c = it % nc, b = bh / H, h = bh % H, n0 = c * bq, m = Nq - n0 < bq ? Nq - n0 : bq;
                float *op = o + (long)b * o0 + (long)h * o1 + (long)n0 * o2;
                TIC(t);
                memset(s, 0, sizeof(float) * (size_t)m * Nk);
                sbg(ROW, N_, T_, m, Nk, d, scale, qb + ((size_t)bh * Nq + n0) * d, d, kb + (size_t)bh * Nk * d, d, 0.0f, s, Nk);
                TOC(tg, t);
                for (int i = 0; i < m; i++) {
                    float *r = s + (size_t)i * Nk, mx = r[0], sum = 0.0f; uint16_t *pr = pb + (size_t)i * Nk;
                    #pragma omp simd reduction(max:mx)
                    for (int j = 1; j < Nk; j++) mx = fmaxf(mx, r[j]);
                    #pragma omp simd reduction(+:sum)
                    for (int j = 0; j < Nk; j++) { r[j] = fexp(r[j] - mx); sum += r[j]; }
                    float inv = 1.0f / sum;
                    #pragma omp simd
                    for (int j = 0; j < Nk; j++) pr[j] = f2b(r[j] * inv);
                    lse[(size_t)bh * Nq + n0 + i] = mx + logf(sum);
                }
                zero_rows(op, m, d, o2);
                TOC(te, t);
                sbg(ROW, N_, N_, m, d, Nk, 1.0f, pb, Nk, vb + (size_t)bh * Nk * d, d, 0.0f, op, o2);
                count++;
                TOC(tg, t);
            }
            free(s); free(pb);
            if (prof) {
                #pragma omp atomic
                tg_ += tg;
                #pragma omp atomic
                te_ += te;
            }
        }
    }
    free(qb); free(kb); free(vb);
    omp_set_max_active_levels(lv);
    prof_print("fwd bf16", B, H, Nq, Nk, bq);
    *tiles = count;
    return failed ? -1 : 0;
}

/* Same two passes as kml_attn_bwd, on the bf16 copies; pass 1 forms S^T and dP^T before either elementwise step. */
int kml_attn_bwd_bf(int B, int H, int Nq, int Nk, int d, float scale, int bq,
                     const float *q, long q0, long q1, long q2, const float *k, long k0, long k1, long k2,
                     const float *v, long v0, long v1, long v2, const float *o, long o0, long o1, long o2,
                     const float *g, long g0, long g1, long g2, const float *lse,
                     float *dq, long dq0, long dq1, long dq2, float *dk, long dk0, long dk1, long dk2,
                     float *dv, long dv0, long dv1, long dv2, unsigned long *tiles) {
    if (!sbg || bq != 16) return -2;
    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2}, O = {o, o0, o1, o2}, G = {g, g0, g1, g2};
    float *D = malloc(sizeof(float) * (size_t)B * H * Nq);
    int lv = nested_off(), nck = (Nk + bq - 1) / bq, ncq = (Nq + bq - 1) / bq, gk = group(nck), gq = group(ncq);
    long n1 = (long)B * H * nck, n2 = (long)B * H * ncq;
    prof_init();
    uint16_t *qb = cast_bhnd(Q, B, H, Nq, d), *kb = cast_bhnd(K, B, H, Nk, d), *vb = cast_bhnd(V, B, H, Nk, d),
             *gb = cast_bhnd(G, B, H, Nq, d);
    int failed = !D || !qb || !kb || !vb || !gb;
    unsigned long count = 0;
    if (!failed) {
        #pragma omp parallel reduction(|:failed) reduction(+:count)
        {
            double tg = 0, te = 0;
            size_t n = (size_t)bq * (Nq > Nk ? Nq : Nk);
            float *p = 0, *dp = 0; uint16_t *pb = 0, *sb = 0;
            if (posix_memalign((void **)&p, 64, sizeof(float) * 2 * n)) p = 0;
            if (posix_memalign((void **)&pb, 64, sizeof(uint16_t) * 2 * n)) pb = 0;
            if (p) dp = p + n;
            if (pb) sb = pb + n;
            failed = !p || !pb;
            #pragma omp for schedule(static)
            for (long r = 0; r < (long)B * H * Nq; r++) {                /* D = rowsum(dO * O), fp32 */
                long bh = r / Nq; int b = bh / H, h = bh % H, i = r % Nq; float acc = 0.0f;
                const float *gp = AT(G, b, h) + (long)i * g2, *op = AT(O, b, h) + (long)i * o2;
                #pragma omp simd reduction(+:acc)
                for (int c = 0; c < d; c++) acc += gp[c] * op[c];
                D[r] = acc;
            }
            #pragma omp for schedule(dynamic, gk)                          /* pass 1: dK, dV per key block */
            for (long it = 0; it < n1; it++) {
                if (!p || !pb) continue;
                long bh = it / nck; int b = bh / H, h = bh % H, j0 = (it % nck) * bq, mk = Nk - j0 < bq ? Nk - j0 : bq;
                const uint16_t *qp = qb + (size_t)bh * Nq * d, *gp = gb + (size_t)bh * Nq * d;
                const uint16_t *kbk = kb + ((size_t)bh * Nk + j0) * d, *vbk = vb + ((size_t)bh * Nk + j0) * d;
                const float *l = lse + bh * Nq, *dr = D + bh * Nq;
                float *dvp = dv + (long)b * dv0 + (long)h * dv1 + (long)j0 * dv2, *dkp = dk + (long)b * dk0 + (long)h * dk1 + (long)j0 * dk2;
                TIC(t);
                memset(p, 0, sizeof(float) * (size_t)mk * Nq); memset(dp, 0, sizeof(float) * (size_t)mk * Nq);
                sbg(ROW, N_, T_, mk, Nq, d, scale, kbk, d, qp, d, 0.0f, p, Nq);            /* S^T */
                sbg(ROW, N_, T_, mk, Nq, d, 1.0f, vbk, d, gp, d, 0.0f, dp, Nq);            /* dP^T */
                TOC(tg, t);
                for (int j = 0; j < mk; j++) {
                    float *restrict r = p + (size_t)j * Nq, *restrict e = dp + (size_t)j * Nq;
                    uint16_t *restrict pr = pb + (size_t)j * Nq, *restrict sr = sb + (size_t)j * Nq;
                    #pragma omp simd
                    for (int i = 0; i < Nq; i++) {
                        float pv = fexp(r[i] - l[i]);
                        pr[i] = f2b(pv); sr[i] = f2b(pv * (e[i] - dr[i]));                  /* P^T, dS^T */
                    }
                }
                zero_rows(dvp, mk, d, dv2); zero_rows(dkp, mk, d, dk2);
                TOC(te, t);
                sbg(ROW, N_, N_, mk, d, Nq, 1.0f, pb, Nq, gp, d, 0.0f, dvp, dv2);          /* dV = P^T dO */
                sbg(ROW, N_, N_, mk, d, Nq, scale, sb, Nq, qp, d, 0.0f, dkp, dk2);         /* dK = scale dS^T Q */
                count++;
                TOC(tg, t);
            }
            #pragma omp for schedule(dynamic, gq)                          /* pass 2: dQ per query block */
            for (long it = 0; it < n2; it++) {
                if (!p || !pb) continue;
                long bh = it / ncq; int b = bh / H, h = bh % H, i0 = (it % ncq) * bq, m = Nq - i0 < bq ? Nq - i0 : bq;
                const uint16_t *qbb = qb + ((size_t)bh * Nq + i0) * d, *gbb = gb + ((size_t)bh * Nq + i0) * d;
                const uint16_t *kp = kb + (size_t)bh * Nk * d, *vp = vb + (size_t)bh * Nk * d;
                const float *l = lse + bh * Nq + i0, *dr = D + bh * Nq + i0;
                float *dqp = dq + (long)b * dq0 + (long)h * dq1 + (long)i0 * dq2;
                TIC(t);
                memset(p, 0, sizeof(float) * (size_t)m * Nk); memset(dp, 0, sizeof(float) * (size_t)m * Nk);
                sbg(ROW, N_, T_, m, Nk, d, scale, qbb, d, kp, d, 0.0f, p, Nk);             /* S */
                sbg(ROW, N_, T_, m, Nk, d, 1.0f, gbb, d, vp, d, 0.0f, dp, Nk);             /* dP */
                TOC(tg, t);
                for (int i = 0; i < m; i++) {
                    float *restrict r = dp + (size_t)i * Nk; const float *sr = p + (size_t)i * Nk; float li = l[i], di = dr[i];
                    uint16_t *restrict so = sb + (size_t)i * Nk;
                    #pragma omp simd
                    for (int j = 0; j < Nk; j++) so[j] = f2b(fexp(sr[j] - li) * (r[j] - di));  /* dS */
                }
                zero_rows(dqp, m, d, dq2);
                TOC(te, t);
                sbg(ROW, N_, N_, m, d, Nk, scale, sb, Nk, kp, d, 0.0f, dqp, dq2);         /* dQ = scale dS K */
                count++;
                TOC(tg, t);
            }
            free(p); free(pb);
            if (prof) {
                #pragma omp atomic
                tg_ += tg;
                #pragma omp atomic
                te_ += te;
            }
        }
    }
    free(D); free(qb); free(kb); free(vb); free(gb);
    omp_set_max_active_levels(lv);
    prof_print("bwd bf16", B, H, Nq, Nk, bq);
    *tiles = count;
    return failed ? -1 : 0;
}
