/* LD_PRELOAD allocator: large posix_memalign requests (torch's CPU allocator, c10::alloc_cpu) are served from an arena
   of 2 MB hugetlb pages bound (mbind MPOL_BIND) to the HBM node HBM_NODE; everything else, and anything that does not
   fit, goes to glibc (DDR). The process mempolicy must allow HBM_NODE (numactl --membind=d,16+d), or the hugetlb
   reservation fails and the arena stays off.
   Arena: a 64-byte header before each block holds its size class (sizes rounded up to 64 KB); freed blocks go on an
   exact-size free list and are reused first, otherwise bump allocation. Steady-state training repeats the same sizes,
   so after the first step the arena holds a fixed set of buffers.
   Env: HBM_NODE (required), HBM_MB (arena size, default 3800, capped by the node's free hugepages), HBM_MIN_KB (smallest request served, default 256),
   HBM_STATS=1 (counts to stderr at exit). */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

extern void *__libc_memalign(size_t, size_t);
extern void __libc_free(void *);
extern void *__libc_malloc(size_t);
extern void *__libc_realloc(void *, size_t);

#define HDR 64
#define GRAIN (64u << 10)
#define NBUCKET 4096
typedef struct blk { struct blk *next; size_t size; } blk;
typedef struct { size_t size; blk *head; } bucket;

static char *base, *bump, *end;
static size_t min_req;
static bucket tab[NBUCKET];
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static size_t n_hbm, n_ddr, n_reuse, b_hbm, b_ddr, high;

static void init(void) {
    const char *nd = getenv("HBM_NODE");
    if (!nd) return;
    char *tail;
    errno = 0;
    long parsed_node = strtol(nd, &tail, 10);
    if (errno || tail == nd || *tail || parsed_node < 0 || parsed_node >= 128) {
        fprintf(stderr, "hbm_alloc: invalid HBM_NODE, arena off\n"); return;
    }
    int node = (int)parsed_node;
    size_t mb = getenv("HBM_MB") ? strtoul(getenv("HBM_MB"), 0, 10) : 3800;
    size_t min_kb = getenv("HBM_MIN_KB") ? strtoul(getenv("HBM_MIN_KB"), 0, 10) : 256;
    if (min_kb > (SIZE_MAX >> 10)) { fprintf(stderr, "hbm_alloc: HBM_MIN_KB overflow, arena off\n"); return; }
    min_req = min_kb << 10;
    /* Faults are bound to `node`, so a short pool there means SIGBUS mid-run. The reservation at mmap counts only
       the nodes of the calling thread's mempolicy (5.10: allowed_mems_nr), so bind the thread to `node` just for the
       mmap: a shortfall is then ENOMEM here. The arena is also sized from the node's free pages (16 kept spare). */
    char fn[128]; long nfree = -1;
    snprintf(fn, sizeof fn, "/sys/devices/system/node/node%d/hugepages/hugepages-2048kB/free_hugepages", node);
    FILE *f = fopen(fn, "r"); if (f) { if (fscanf(f, "%ld", &nfree) != 1) nfree = -1; fclose(f); }
    if (nfree < 0) { fprintf(stderr, "hbm_alloc: cannot read free hugepages on node %d, arena off\n", node); return; }
    size_t available_mb = nfree > 16 ? (size_t)(nfree - 16) * 2 : 0;
    if (available_mb < mb) mb = available_mb;
    if (mb < 64) { fprintf(stderr, "hbm_alloc: node %d has %ld free hugepages, arena off\n", node, nfree); return; }
    if (mb > (SIZE_MAX >> 20)) { fprintf(stderr, "hbm_alloc: HBM_MB overflow, arena off\n"); return; }
    size_t len = mb << 20;
    unsigned long mask[2] = {0, 0}, old[16] = {0};
    int oldmode = 0;
    mask[node / 64] = 1ul << (node % 64);
    if (syscall(SYS_get_mempolicy, &oldmode, old, 1024, 0, 0) != 0) {
        fprintf(stderr, "hbm_alloc: get_mempolicy failed: %s, arena off\n", strerror(errno)); return;
    }
    int bound = syscall(SYS_set_mempolicy, 2 /* MPOL_BIND */, mask, 128) == 0;
    void *p = bound ? mmap(0, len, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, -1, 0) : MAP_FAILED;
    int err = errno;
    if (syscall(SYS_set_mempolicy, oldmode, oldmode ? old : 0, oldmode ? 1024 : 0) != 0) {
        int restore_err = errno;
        if (p != MAP_FAILED) munmap(p, len);
        fprintf(stderr, "hbm_alloc: fatal: restore mempolicy failed: %s\n", strerror(restore_err));
        _exit(EXIT_FAILURE);
    }
    if (!bound) { fprintf(stderr, "hbm_alloc: set_mempolicy node %d failed: %s, arena off\n", node, strerror(err)); return; }
    if (p == MAP_FAILED) { fprintf(stderr, "hbm_alloc: mmap %zu MB on node %d failed: %s\n", mb, node, strerror(err)); return; }
    if (syscall(SYS_mbind, p, len, 2 /* MPOL_BIND */, mask, 128, 0) != 0) {
        fprintf(stderr, "hbm_alloc: mbind node %d failed: %s\n", node, strerror(errno)); munmap(p, len); return;
    }
    base = bump = p; end = base + len;
    if (getenv("HBM_STATS")) fprintf(stderr, "hbm_alloc: arena %zu MB on node %d, requests >= %zu KB\n", mb, node, min_req >> 10);
}

static int in_arena(void *p) { return base && (char *)p >= base && (char *)p < end; }

static bucket *slot(size_t sz) {
    size_t h = (sz / GRAIN) * 2654435761u % NBUCKET;
    for (size_t i = 0; i < NBUCKET; i++) {
        bucket *b = &tab[(h + i) % NBUCKET];
        if (b->size == sz || b->size == 0) { b->size = sz; return b; }
    }
    return 0;
}

static void *arena_get(size_t n) {
    if (n > SIZE_MAX - HDR - (GRAIN - 1)) return 0;
    size_t sz = (n + HDR + GRAIN - 1) / GRAIN * GRAIN;
    char *p = 0;
    pthread_mutex_lock(&mu);
    bucket *b = slot(sz);
    if (b && b->head) { p = (char *)b->head; b->head = b->head->next; n_reuse++; }
    else if (sz <= (size_t)(end - bump)) { p = bump; bump += sz; if ((size_t)(bump - base) > high) high = bump - base; }
    if (p) { ((blk *)p)->size = sz; n_hbm++; b_hbm += sz; }
    pthread_mutex_unlock(&mu);
    return p ? p + HDR : 0;
}

static void arena_put(void *q) {
    char *p = (char *)q - HDR; size_t sz = ((blk *)p)->size;
    pthread_mutex_lock(&mu);
    bucket *b = slot(sz);
    ((blk *)p)->next = b->head; b->head = (blk *)p;
    pthread_mutex_unlock(&mu);
}

int posix_memalign(void **out, size_t align, size_t n) {
    if (align < sizeof(void *) || (align & (align - 1))) return EINVAL;
    pthread_once(&once, init);
    if (base && n >= min_req && align <= HDR) {
        void *p = arena_get(n);
        if (p) { *out = p; return 0; }
    }
    if (n >= min_req) { __atomic_add_fetch(&n_ddr, 1, __ATOMIC_RELAXED); __atomic_add_fetch(&b_ddr, n, __ATOMIC_RELAXED); }
    void *p = __libc_memalign(align, n);
    if (!p) return ENOMEM;
    *out = p; return 0;
}

void free(void *p) {
    if (!p) return;
    if (in_arena(p)) arena_put(p); else __libc_free(p);
}

void *realloc(void *p, size_t n) {
    if (!in_arena(p)) return __libc_realloc(p, n);
    size_t old = ((blk *)((char *)p - HDR))->size - HDR;
    void *q = __libc_malloc(n);
    if (q) { memcpy(q, p, old < n ? old : n); arena_put(p); }
    return q;
}

__attribute__((destructor)) static void stats(void) {
    if (base && getenv("HBM_STATS"))
        fprintf(stderr, "hbm_alloc: hbm allocs %zu (%.1f GB, %zu reused), ddr large allocs %zu (%.1f GB), arena high-water %.2f GB\n",
                n_hbm, b_hbm / 1e9, n_reuse, n_ddr, b_ddr / 1e9, high / 1e9);
}
