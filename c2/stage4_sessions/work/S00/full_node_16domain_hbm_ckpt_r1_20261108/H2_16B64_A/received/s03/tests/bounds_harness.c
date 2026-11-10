/* 64-bit Linux/glibc. Test the included C implementation, not a copy of it. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

extern void *__libc_malloc(size_t);
extern void *__libc_memalign(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern void __libc_free(void *);
static const char *test_getenv(const char *);
static FILE *test_fopen(const char *, const char *);
static int test_fscanf(FILE *, const char *, ...);
static int test_fclose(FILE *);
static long test_syscall(long, ...);
static void *test_mmap(void *, size_t, int, int, int, off_t);
static void *test_malloc(size_t);
static void *test_memalign(size_t, size_t);
static void *test_realloc(void *, size_t);
static void test_free(void *);

#define getenv test_getenv
#define fopen test_fopen
#define fscanf test_fscanf
#define fclose test_fclose
#define syscall test_syscall
#define mmap test_mmap
#define __libc_malloc test_malloc
#define __libc_memalign test_memalign
#define __libc_realloc test_realloc
#define __libc_free test_free
#define posix_memalign tested_posix_memalign
#define free tested_free
#define realloc tested_realloc
#ifndef S03_SOURCE
#define S03_SOURCE "../candidate/hbm_alloc.c"
#endif
#include S03_SOURCE
#undef getenv
#undef fopen
#undef fscanf
#undef fclose
#undef syscall
#undef mmap
#undef __libc_malloc
#undef __libc_memalign
#undef __libc_realloc
#undef __libc_free
#undef posix_memalign
#undef free
#undef realloc

#define CHECK(c) do { if (!(c)) { \
    fprintf(stderr, "CHECK_FAIL line %d: %s\n", __LINE__, #c); return 1; \
} } while (0)

static const char *node_text = "16", *mb_text = "64", *min_text;
static int invalid_node, expected_node = 16;
static long free_pages = 48;
static int opens, gets, sets, maps, mbinds, mallocs, memaligns, reallocs, frees;
static int fail_mapping, fail_malloc, fail_memalign;
static size_t mapped_bytes;
static int policy_bound;
static unsigned char opaque_file;

static const char *test_getenv(const char *name) {
    if (!strcmp(name, "HBM_NODE")) return node_text;
    if (!strcmp(name, "HBM_MB")) return mb_text;
    if (!strcmp(name, "HBM_MIN_KB")) return min_text;
    return NULL;
}

static FILE *test_fopen(const char *path, const char *mode) {
    opens++;
    assert(!strcmp(mode, "r"));
    /* The previous candidate must fail the zero-I/O rejection assertion, without
       executing undefined node indexing or depending on any real sysfs file. */
    if (invalid_node) return NULL;
    char expected[128];
    snprintf(expected, sizeof expected, "/sys/devices/system/node/node%d/hugepages/hugepages-2048kB/free_hugepages", expected_node);
    assert(!strcmp(path, expected));
    return (FILE *)&opaque_file;
}

static int test_fscanf(FILE *f, const char *fmt, ...) {
    assert(f == (FILE *)&opaque_file && !strcmp(fmt, "%ld"));
    va_list ap;
    va_start(ap, fmt);
    *va_arg(ap, long *) = free_pages;
    va_end(ap);
    return 1;
}

static int test_fclose(FILE *f) { assert(f == (FILE *)&opaque_file); return 0; }

static void check_mask(const unsigned long *mask) {
    unsigned long expected[2] = {0, 0};
    assert(expected_node >= 0 && expected_node < 128);
    expected[expected_node / 64] = 1ul << (expected_node % 64);
    assert(mask[0] == expected[0] && mask[1] == expected[1]);
}

static long test_syscall(long number, ...) {
    va_list ap;
    va_start(ap, number);
    if (number == SYS_get_mempolicy) {
        int *mode = va_arg(ap, int *);
        unsigned long *mask = va_arg(ap, unsigned long *);
        assert(va_arg(ap, int) == 1024);
        assert(va_arg(ap, int) == 0 && va_arg(ap, int) == 0);
        *mode = 0;
        memset(mask, 0, 16 * sizeof *mask);
        gets++;
    } else if (number == SYS_set_mempolicy) {
        int mode = va_arg(ap, int);
        unsigned long *mask = va_arg(ap, unsigned long *);
        int maxnode = va_arg(ap, int);
        if (!sets) {
            assert(mode == 2 && maxnode == 128);
            check_mask(mask);
            policy_bound = 1;
        } else {
            assert(sets == 1 && mode == 0 && !mask && maxnode == 0);
            policy_bound = 0;
        }
        sets++;
    } else {
        assert(number == SYS_mbind);
        void *p = va_arg(ap, void *);
        size_t len = va_arg(ap, size_t);
        assert(p && p != MAP_FAILED && len == mapped_bytes && !policy_bound);
        assert(va_arg(ap, int) == 2);
        check_mask(va_arg(ap, unsigned long *));
        assert(va_arg(ap, int) == 128 && va_arg(ap, int) == 0);
        mbinds++;
    }
    va_end(ap);
    return 0;
}

static void *test_mmap(void *p, size_t len, int prot, int flags, int fd, off_t offset) {
    assert(!p && prot == (PROT_READ | PROT_WRITE));
    assert(flags == (MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB) && fd == -1 && offset == 0);
    assert(policy_bound);
    maps++;
    mapped_bytes = len;
    if (fail_mapping || !len) { errno = ENOMEM; return MAP_FAILED; }
    assert(len == (64u << 20)); /* No huge virtual mappings or actual HBM. */
    p = mmap(NULL, len, prot, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(p != MAP_FAILED);
    return p;
}

static void *test_malloc(size_t n) {
    mallocs++;
    if (fail_malloc) { errno = ENOMEM; return NULL; }
    return __libc_malloc(n);
}

static void *test_memalign(size_t align, size_t n) {
    memaligns++;
    if (fail_memalign) { errno = ENOMEM; return NULL; }
    return __libc_memalign(align, n);
}

static void *test_realloc(void *p, size_t n) { reallocs++; return __libc_realloc(p, n); }
static void test_free(void *p) { frees++; __libc_free(p); }
static void start(void) { pthread_once(&once, init); }

static int pattern(const void *p, size_t n) {
    const unsigned char *bytes = p;
    for (size_t i = 0; i < n; i++) if (bytes[i] != 0x5a) return 0;
    return 1;
}

static int node_case(const char *kind, const char *text) {
    node_text = text;
    invalid_node = !strcmp(kind, "invalid");
    if (!invalid_node) expected_node = (int)strtol(text, NULL, 10);
    void *p = NULL;
    CHECK(tested_posix_memalign(&p, 64, 256u << 10) == 0 && p);
    if (invalid_node) {
        CHECK(opens == 0 && gets == 0 && sets == 0 && maps == 0 && mbinds == 0);
        CHECK(!base && !in_arena(p) && memaligns == 1);
    } else {
        CHECK(base && in_arena(p) && opens == 1 && gets == 1 && sets == 2 && maps == 1 && mbinds == 1);
    }
    memset(p, 0x5a, 256u << 10);
    CHECK(pattern(p, 256u << 10));
    tested_free(p);
    return 0;
}

static int config_case(const char *name) {
    char text[64];
    if (!strcmp(name, "mb_overflow") || !strcmp(name, "mb_last_safe")) {
        free_pages = LONG_MAX;
        size_t mb = (SIZE_MAX >> 20) + (!strcmp(name, "mb_overflow") ? 1 : 0);
        snprintf(text, sizeof text, "%zu", mb);
        mb_text = text;
        fail_mapping = 1;
        start();
        if (!strcmp(name, "mb_overflow")) CHECK(!base && maps == 0 && gets == 0);
        else CHECK(!base && maps == 1 && mapped_bytes == SIZE_MAX - ((1u << 20) - 1));
    } else if (!strcmp(name, "min_overflow") || !strcmp(name, "min_last_safe")) {
        size_t kb = (SIZE_MAX >> 10) + (!strcmp(name, "min_overflow") ? 1 : 0);
        snprintf(text, sizeof text, "%zu", kb);
        min_text = text;
        start();
        if (!strcmp(name, "min_overflow")) CHECK(!base && opens == 0 && maps == 0 && gets == 0);
        else CHECK(base && min_req == SIZE_MAX - 1023);
    } else {
        assert(!strcmp(name, "mb_large_capped"));
        snprintf(text, sizeof text, "%zu", SIZE_MAX);
        mb_text = text;
        start();
        CHECK(base && maps == 1 && mapped_bytes == (64u << 20));
    }
    CHECK(!policy_bound);
    return 0;
}

static int request_case(const char *name) {
    start();
    CHECK(base);
    char *before = bump;
    if (!strcmp(name, "sum_max") || !strcmp(name, "sum_first_overflow") ||
        !strcmp(name, "sum_last_safe") || !strcmp(name, "pointer_wrap")) {
        size_t n = SIZE_MAX;
        if (!strcmp(name, "sum_first_overflow")) n = SIZE_MAX - HDR - (GRAIN - 1) + 1;
        if (!strcmp(name, "sum_last_safe")) n = SIZE_MAX - HDR - (GRAIN - 1);
        if (!strcmp(name, "pointer_wrap")) {
            CHECK((uintptr_t)bump > HDR + GRAIN);
            n = SIZE_MAX - (uintptr_t)bump + 1;
        }
        CHECK(arena_get(n) == NULL);
        CHECK(bump == before && n_hbm == 0 && high == 0);
    } else if (!strcmp(name, "api_sum_max")) {
        void *sentinel = (void *)(uintptr_t)0x12340, *p = sentinel;
        fail_memalign = 1;
        CHECK(tested_posix_memalign(&p, 64, SIZE_MAX) == ENOMEM);
        CHECK(p == sentinel && bump == before && memaligns == 1 && n_hbm == 0);
    } else if (!strcmp(name, "last_fit")) {
        bump = end - GRAIN;
        char *last = bump;
        void *p = arena_get(GRAIN - HDR);
        CHECK(p == last + HDR && bump == end);
        memset(p, 0x5a, GRAIN - HDR);
        CHECK(pattern(p, GRAIN - HDR) && !arena_get(1));
    } else if (!strcmp(name, "short_tail")) {
        bump = end - GRAIN + HDR;
        before = bump;
        CHECK(!arena_get(GRAIN - HDR) && bump == before);
    } else {
        size_t n = GRAIN - HDR;
        size_t expected = GRAIN;
        if (!strcmp(name, "grain_below")) n--;
        else if (!strcmp(name, "grain_above")) { n++; expected = 2 * GRAIN; }
        else assert(!strcmp(name, "grain_exact"));
        void *p = arena_get(n);
        CHECK(p == before + HDR && (size_t)(bump - before) == expected);
        memset(p, 0x5a, n);
        CHECK(pattern(p, n));
    }
    return 0;
}

static int align_case(const char *kind, size_t align) {
    void *sentinel = (void *)(uintptr_t)0x12340, *p = sentinel;
    int rc = tested_posix_memalign(&p, align, 256u << 10);
    if (!strcmp(kind, "invalid")) {
        CHECK(rc == EINVAL && p == sentinel);
        CHECK(!opens && !gets && !maps && !memaligns && !base);
    } else {
        CHECK(rc == 0 && p && (uintptr_t)p % align == 0);
        CHECK(!!in_arena(p) == (align <= HDR));
        CHECK(memaligns == (align > HDR));
        memset(p, 0x5a, 256u << 10);
        CHECK(pattern(p, 256u << 10));
        tested_free(p);
    }
    return 0;
}

static int api_case(const char *name) {
    if (!strcmp(name, "free_null")) {
        tested_free(NULL);
        CHECK(!opens && !frees && !base);
        return 0;
    }
    if (!strcmp(name, "ddr_forward")) {
        void *p = __libc_malloc(1024);
        CHECK(p);
        memset(p, 0x5a, 1024);
        void *q = tested_realloc(p, 2048);
        CHECK(q && pattern(q, 1024) && reallocs == 1);
        tested_free(q);
        q = tested_realloc(NULL, 64);
        CHECK(q && reallocs == 2);
        tested_free(q);
        CHECK(frees == 2 && !opens);
        return 0;
    }
    start();
    CHECK(base);
    if (!strcmp(name, "ddr_failure")) {
        void *sentinel = (void *)(uintptr_t)0x12340, *p = sentinel;
        fail_memalign = 1;
        CHECK(tested_posix_memalign(&p, 128, 256u << 10) == ENOMEM);
        CHECK(p == sentinel && memaligns == 1);
        return 0;
    }
    if (!strcmp(name, "full_fallback")) {
        bump = end;
        void *p = NULL;
        CHECK(tested_posix_memalign(&p, 64, 256u << 10) == 0 && p);
        CHECK(!in_arena(p) && memaligns == 1);
        memset(p, 0x5a, 256u << 10);
        CHECK(pattern(p, 256u << 10));
        tested_free(p);
        return 0;
    }
    void *p = arena_get(100000);
    CHECK(p);
    memset(p, 0x5a, 100000);
    if (!strcmp(name, "free_reuse")) {
        tested_free(p);
        bump = end; /* Reuse must still work when no fresh arena bytes remain. */
        void *q = arena_get(100000);
        CHECK(q == p && n_reuse == 1 && pattern(q, 100000) && !frees);
        tested_free(q);
    } else if (!strcmp(name, "realloc_failure")) {
        fail_malloc = 1;
        CHECK(!tested_realloc(p, 200000));
        CHECK(pattern(p, 100000) && mallocs == 1);
        void *q = arena_get(100000);
        CHECK(q && q != p && !n_reuse);
        tested_free(q);
        tested_free(p);
    } else {
        size_t n = !strcmp(name, "realloc_grow") ? 200000 : 4096;
        assert(!strcmp(name, "realloc_grow") || !strcmp(name, "realloc_shrink"));
        void *q = tested_realloc(p, n);
        CHECK(q && !in_arena(q) && pattern(q, n < 100000 ? n : 100000));
        CHECK(mallocs == 1);
        void *again = arena_get(100000);
        CHECK(again == p && n_reuse == 1);
        tested_free(again);
        tested_free(q);
    }
    return 0;
}

int main(int argc, char **argv) {
    assert(sizeof(size_t) == 8 && sizeof(unsigned long) == 8 && argc >= 3);
    int rc;
    if (!strcmp(argv[1], "node")) { assert(argc == 4); rc = node_case(argv[2], argv[3]); }
    else if (!strcmp(argv[1], "config")) rc = config_case(argv[2]);
    else if (!strcmp(argv[1], "request")) rc = request_case(argv[2]);
    else if (!strcmp(argv[1], "align")) { assert(argc == 4); rc = align_case(argv[2], strtoul(argv[3], NULL, 10)); }
    else { assert(!strcmp(argv[1], "api")); rc = api_case(argv[2]); }
    printf("TRACE opens=%d get=%d set=%d map=%d mbind=%d bytes=%zu arena=%d ddr=%d malloc=%d realloc=%d free=%d\n",
           opens, gets, sets, maps, mbinds, mapped_bytes, base != NULL, memaligns, mallocs, reallocs, frees);
    if (!rc) puts("RESULT PASS");
    return rc;
}
