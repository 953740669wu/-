/* LD_PRELOAD shim: torch's BLAS sgemm_ -> KML SME kblas, loaded lazily on the first call (loading KML before
   torch finishes its static initialisation deadlocks). KML_BLAS_LIB names the kblas library to forward to. */
#include <dlfcn.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
typedef void (*sgemm_fn)(const char *, const char *, const int *, const int *, const int *, const float *,
                         const float *, const int *, const float *, const int *, const float *, float *, const int *);
static sgemm_fn real_sgemm;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static void load(void) {
    const char *path = getenv("KML_BLAS_LIB");
    void *h = dlopen(path ? path : "libkblas.so", RTLD_NOW | RTLD_LOCAL);
    if (!h) { fprintf(stderr, "kml shim: %s\n", dlerror()); abort(); }
    real_sgemm = (sgemm_fn)dlsym(h, "sgemm_");
    if (!real_sgemm) { fprintf(stderr, "kml shim: no sgemm_\n"); abort(); }
    if (getenv("KML_SHIM_VERBOSE")) fprintf(stderr, "kml shim: sgemm_ -> %s\n", path);
}
void sgemm_(const char *ta, const char *tb, const int *m, const int *n, const int *k, const float *alpha,
            const float *a, const int *lda, const float *b, const int *ldb, const float *beta, float *c, const int *ldc) {
    pthread_once(&once, load);
    real_sgemm(ta, tb, m, n, k, alpha, a, lda, b, ldb, beta, c, ldc);
}
