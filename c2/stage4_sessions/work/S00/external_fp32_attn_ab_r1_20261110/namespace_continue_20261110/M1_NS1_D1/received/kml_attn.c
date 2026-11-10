/* Fused attention (no mask, no dropout, fp32) for s4_models on C2, called from kml_ops.py through ctypes.
   One OpenMP loop over (batch x head x query chunk) tiles; each tile runs single-threaded KML SME sgemms on views
   of q/k/v (row stride at least head width, unit column stride) with a per-thread score buffer of BQ x Nk, so the N x N scores never
   reach memory. Forward saves the per-row log-sum-exp; backward recomputes the scores from it (FlashAttention-2
   style) and loops over query chunks inside one head, so dK/dV accumulate without atomics.
   Tensors are addressed as x[b*s0 + h*s1 + n*s2 + i] (i < d). Each tile calls the locking KML namespace.
   Build in a job (gcc of the compute nodes):
     gcc -O3 -mcpu=native -fno-math-errno -fopenmp -fPIC -c kml_attn.c && gcc -shared -o libkml_attn.so kml_attn.o <torch_kml>/torch.libs/libgomp-*.so -ldl
   Linking against torch's libgomp (BiSheng libomp in sw/torch_kml) keeps a single OpenMP runtime in the process. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <link.h>
#include <math.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*sgemm_t)(int, int, int, int, int, int, float, const float *, int, const float *, int, float, float *, int);
static sgemm_t sg;
static void *locking_handle;
enum { ROW = 101, N_ = 111, T_ = 112 };

/* The tiles need a BLAS whose concurrent single-thread calls run in parallel. On C2 that is only KML's serial
   thread-safe build, sme/kblas/locking (bench_kblas_concurrent.c, 36 threads: 2.4 TFLOP/s together; nolocking
   serializes to 0.25, multi inside a parallel region likewise). It shares the soname libkblas.so.1 with the multi
   build torch's shim uses, so it is loaded in its own link namespace. Returns 0 on success (else the caller must stop). */
int kml_attn_load(const char *path) {
    void *h = dlmopen(LM_ID_NEWLM, path, RTLD_NOW | RTLD_LOCAL);
    void *f = h ? dlsym(h, "cblas_sgemm") : 0;
    if (!f) return -1;
    locking_handle = h;
    sg = (sgemm_t)f; return 0;
}

int kml_attn_locking_info(void **handle, long *namespace_id, const char **path, void **gemm) {
    struct link_map *map = NULL;
    Lmid_t id = LM_ID_BASE;
    Dl_info symbol;
    void *symbol_map = NULL;
    if (!locking_handle || !sg || dlinfo(locking_handle, RTLD_DI_LMID, &id) != 0 || id == LM_ID_BASE ||
        dlinfo(locking_handle, RTLD_DI_LINKMAP, &map) != 0 || !map || !map->l_name || !*map->l_name ||
        !dladdr1((void *)sg, &symbol, &symbol_map, RTLD_DL_LINKMAP) || symbol_map != map)
        return -1;
    *handle = locking_handle;
    *namespace_id = id;
    *path = map->l_name;
    *gemm = (void *)sg;
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

/* o = softmax(scale q k^T) v; lse[(b*H + h)*Nq + n] */
int kml_attn_fwd(int B, int H, int Nq, int Nk, int d, float scale, int bq,
                  const float *q, long q0, long q1, long q2, const float *k, long k0, long k1, long k2,
                  const float *v, long v0, long v1, long v2, float *o, long o0, long o1, long o2, float *lse) {
    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2};
    int nc = (Nq + bq - 1) / bq, lv = nested_off(), gq = group(nc);
    prof_init();
    int failed = 0;
    #pragma omp parallel reduction(|:failed)
    {
        double tg = 0, te = 0;
        float *s = 0;
        if (posix_memalign((void **)&s, 64, sizeof(float) * (size_t)bq * Nk)) { s = 0; failed = 1; }
        #pragma omp for schedule(dynamic, gq)
        for (long it = 0; it < (long)B * H * nc; it++) {
            if (!s) continue;
            int bh = it / nc, c = it % nc, b = bh / H, h = bh % H, n0 = c * bq, m = Nq - n0 < bq ? Nq - n0 : bq;
            const float *qp = AT(Q, b, h) + n0 * q2;
            TIC(t);
            sg(ROW, N_, T_, m, Nk, d, scale, qp, q2, AT(K, b, h), k2, 0.0f, s, Nk);
            TOC(tg, t);
            for (int i = 0; i < m; i++) {
                float *r = s + (size_t)i * Nk, mx = r[0], sum = 0.0f;
                #pragma omp simd reduction(max:mx)
                for (int j = 1; j < Nk; j++) mx = fmaxf(mx, r[j]);
                #pragma omp simd reduction(+:sum)
                for (int j = 0; j < Nk; j++) { r[j] = fexp(r[j] - mx); sum += r[j]; }
                float inv = 1.0f / sum;
                for (int j = 0; j < Nk; j++) r[j] *= inv;
                lse[(size_t)bh * Nq + n0 + i] = mx + logf(sum);
            }
            TOC(te, t);
            sg(ROW, N_, N_, m, d, Nk, 1.0f, s, Nk, AT(V, b, h), v2, 0.0f, o + (long)b * o0 + (long)h * o1 + (long)n0 * o2, o2);
            TOC(tg, t);
        }
        free(s);
        if (prof) {
            #pragma omp atomic
            tg_ += tg;
            #pragma omp atomic
            te_ += te;
        }
    }
    omp_set_max_active_levels(lv);
    prof_print("fwd", B, H, Nq, Nk, bq);
    return failed ? -1 : 0;
}

/* Gradients of kml_attn_fwd (default), FlashAttention-2 style in two passes with the scores recomputed in each, so
   every GEMM has the forward shapes (inner dimension d or the full token count, no transposed A) and there are
   B*H*chunks independent tasks:
     pass 1, per (b, h, key block of bq rows): S^T = scale K_blk Q^T, P^T = exp(S^T - lse), dV_blk = P^T dO,
             dP^T = V_blk dO^T, dS^T = P^T * (dP^T - D), dK_blk = scale dS^T Q;
     pass 2, per (b, h, query block): S = scale Q_blk K^T, P = exp(S - lse), dP = dO_blk V^T, dS = P * (dP - D),
             dQ_blk = scale dS K;
   with D = rowsum(dO * O) per query row, computed first. */
int kml_attn_bwd(int B, int H, int Nq, int Nk, int d, float scale, int bq,
                  const float *q, long q0, long q1, long q2, const float *k, long k0, long k1, long k2,
                  const float *v, long v0, long v1, long v2, const float *o, long o0, long o1, long o2,
                  const float *g, long g0, long g1, long g2, const float *lse,
                  float *dq, long dq0, long dq1, long dq2, float *dk, long dk0, long dk1, long dk2,
                  float *dv, long dv0, long dv1, long dv2) {
    view Q = {q, q0, q1, q2}, K = {k, k0, k1, k2}, V = {v, v0, v1, v2}, O = {o, o0, o1, o2}, G = {g, g0, g1, g2};
    float *D = malloc(sizeof(float) * (size_t)B * H * Nq);
    if (!D) return -1;
    int lv = nested_off(), nck = (Nk + bq - 1) / bq, ncq = (Nq + bq - 1) / bq, gk = group(nck), gq = group(ncq);
    long n1 = (long)B * H * nck, n2 = (long)B * H * ncq;
    prof_init();
    int failed = 0;
    #pragma omp parallel reduction(|:failed)
    {
        double tg = 0, te = 0;
        size_t n = (size_t)bq * (Nq > Nk ? Nq : Nk);
        float *p = 0, *dp = 0;
        if (posix_memalign((void **)&p, 64, sizeof(float) * 2 * n)) { p = 0; failed = 1; }
        if (p) dp = p + n;
        #pragma omp for schedule(static)
        for (long r = 0; r < (long)B * H * Nq; r++) {                    /* D = rowsum(dO * O) */
            long bh = r / Nq; int b = bh / H, h = bh % H, i = r % Nq; float acc = 0.0f;
            const float *gp = AT(G, b, h) + (long)i * g2, *op = AT(O, b, h) + (long)i * o2;
            #pragma omp simd reduction(+:acc)
            for (int c = 0; c < d; c++) acc += gp[c] * op[c];
            D[r] = acc;
        }
        #pragma omp for schedule(dynamic, gk)                              /* pass 1: dK, dV per key block */
        for (long it = 0; it < n1; it++) {
            if (!p) continue;
            long bh = it / nck; int b = bh / H, h = bh % H, j0 = (it % nck) * bq, mk = Nk - j0 < bq ? Nk - j0 : bq;
            const float *qp = AT(Q, b, h), *gp = AT(G, b, h), *l = lse + bh * Nq, *dr = D + bh * Nq;
            const float *kb = AT(K, b, h) + (long)j0 * k2, *vb = AT(V, b, h) + (long)j0 * v2;
            TIC(t);
            sg(ROW, N_, T_, mk, Nq, d, scale, kb, k2, qp, q2, 0.0f, p, Nq);         /* S^T */
            TOC(tg, t);
            for (int j = 0; j < mk; j++) {
                float *restrict r = p + (size_t)j * Nq;
                #pragma omp simd
                for (int i = 0; i < Nq; i++) r[i] = fexp(r[i] - l[i]);
            }
            TOC(te, t);
            sg(ROW, N_, N_, mk, d, Nq, 1.0f, p, Nq, gp, g2, 0.0f, dv + (long)b * dv0 + (long)h * dv1 + (long)j0 * dv2, dv2);
            sg(ROW, N_, T_, mk, Nq, d, 1.0f, vb, v2, gp, g2, 0.0f, dp, Nq);          /* dP^T */
            TOC(tg, t);
            for (int j = 0; j < mk; j++) {
                float *restrict r = dp + (size_t)j * Nq; const float *pr = p + (size_t)j * Nq;
                #pragma omp simd
                for (int i = 0; i < Nq; i++) r[i] = pr[i] * (r[i] - dr[i]);
            }
            TOC(te, t);
            sg(ROW, N_, N_, mk, d, Nq, scale, dp, Nq, qp, q2, 0.0f, dk + (long)b * dk0 + (long)h * dk1 + (long)j0 * dk2, dk2);
            TOC(tg, t);
        }
        #pragma omp for schedule(dynamic, gq)                              /* pass 2: dQ per query block */
        for (long it = 0; it < n2; it++) {
            if (!p) continue;
            long bh = it / ncq; int b = bh / H, h = bh % H, i0 = (it % ncq) * bq, m = Nq - i0 < bq ? Nq - i0 : bq;
            const float *qb = AT(Q, b, h) + (long)i0 * q2, *gb = AT(G, b, h) + (long)i0 * g2, *kp = AT(K, b, h), *vp = AT(V, b, h);
            const float *l = lse + bh * Nq + i0, *dr = D + bh * Nq + i0;
            TIC(t);
            sg(ROW, N_, T_, m, Nk, d, scale, qb, q2, kp, k2, 0.0f, p, Nk);           /* S */
            sg(ROW, N_, T_, m, Nk, d, 1.0f, gb, g2, vp, v2, 0.0f, dp, Nk);           /* dP */
            TOC(tg, t);
            for (int i = 0; i < m; i++) {
                float *restrict r = dp + (size_t)i * Nk; const float *sr = p + (size_t)i * Nk; float li = l[i], di = dr[i];
                #pragma omp simd
                for (int j = 0; j < Nk; j++) r[j] = fexp(sr[j] - li) * (r[j] - di);   /* dS */
            }
            TOC(te, t);
            sg(ROW, N_, N_, m, d, Nk, scale, dp, Nk, kp, k2, 0.0f, dq + (long)b * dq0 + (long)h * dq1 + (long)i0 * dq2, dq2);
            TOC(tg, t);
        }
        free(p);
        if (prof) {
            #pragma omp atomic
            tg_ += tg;
            #pragma omp atomic
            te_ += te;
        }
    }
    free(D);
    omp_set_max_active_levels(lv);
    prof_print("bwd", B, H, Nq, Nk, bq);
    return failed ? -1 : 0;
}

