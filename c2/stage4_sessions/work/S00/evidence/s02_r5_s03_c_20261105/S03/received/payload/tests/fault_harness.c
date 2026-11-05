/* Linux/glibc only. Include the exact allocator, replace only OS-facing calls.
 * mmap uses ordinary anonymous memory; this never proves HBM placement. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

static const char *s03_getenv(const char *name);
static FILE *s03_fopen(const char *path, const char *mode);
static int s03_fscanf(FILE *f, const char *format, ...);
static int s03_fclose(FILE *f);
static long s03_syscall(long number, ...);
static void *s03_mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off);
static int s03_munmap(void *addr, size_t len);
static void s03_exit(int code) __attribute__((noreturn));

#define getenv s03_getenv
#define fopen s03_fopen
#define fscanf s03_fscanf
#define fclose s03_fclose
#define syscall s03_syscall
#define mmap s03_mmap
#define munmap s03_munmap
#define _exit s03_exit
#define posix_memalign s03_posix_memalign
#define free s03_free
#define realloc s03_realloc
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
#undef munmap
#undef _exit
#undef posix_memalign
#undef free
#undef realloc

static const char *scenario;
static long pages = 2020;
static const char *requested_mb;
static int saved_mode = 2, current_mode = 2;
static unsigned long saved_mask[16], current_mask[16];
static int gets, binds, maps, restores, mbinds, unmaps;
static size_t mapped_len;
static int map_saw_hbm_only, mbind_saw_restored;

static int is(const char *name) { return strcmp(scenario, name) == 0; }

static void trace(void) {
    printf("TRACE get=%d bind=%d map=%d restore=%d mbind=%d unmap=%d "
           "mb=%zu mode=%d policy_ok=%d map_hbm=%d mbind_restored=%d arena=%d\n",
           gets, binds, maps, restores, mbinds, unmaps, mapped_len >> 20,
           current_mode,
           current_mode == saved_mode && !memcmp(current_mask, saved_mask, sizeof saved_mask),
           map_saw_hbm_only, mbind_saw_restored, base != NULL);
    fflush(stdout);
}

static const char *s03_getenv(const char *name) {
    if (!strcmp(name, "HBM_NODE")) return is("no_node") ? NULL : "16";
    if (!strcmp(name, "HBM_MB")) return requested_mb;
    return NULL;
}

static FILE *s03_fopen(const char *path, const char *mode) {
    assert(!strcmp(path, "/sys/devices/system/node/node16/hugepages/hugepages-2048kB/free_hugepages"));
    assert(!strcmp(mode, "r"));
    if (is("read_open_fail")) { errno = EACCES; return NULL; }
    return (FILE *)&pages; /* Opaque token, never passed to libc stdio. */
}

static int s03_fscanf(FILE *f, const char *format, ...) {
    assert(f == (FILE *)&pages && !strcmp(format, "%ld"));
    if (is("read_parse_fail")) return 0;
    va_list ap;
    va_start(ap, format);
    *va_arg(ap, long *) = pages;
    va_end(ap);
    return 1;
}

static int s03_fclose(FILE *f) { assert(f == (FILE *)&pages); return 0; }

static long s03_syscall(long number, ...) {
    va_list ap;
    va_start(ap, number);
    if (number == SYS_get_mempolicy) {
        int *mode = va_arg(ap, int *);
        unsigned long *mask = va_arg(ap, unsigned long *);
        assert(va_arg(ap, int) == 1024);
        assert(va_arg(ap, int) == 0);
        assert(va_arg(ap, int) == 0);
        va_end(ap);
        gets++;
        if (is("get_fail")) { errno = EPERM; return -1; }
        *mode = saved_mode;
        memcpy(mask, saved_mask, sizeof saved_mask);
        return 0;
    }
    if (number == SYS_set_mempolicy) {
        int mode = va_arg(ap, int);
        unsigned long *mask = va_arg(ap, unsigned long *);
        int maxnode = va_arg(ap, int);
        va_end(ap);
        if (!binds) {
            binds++;
            assert(mode == 2 && maxnode == 128);
            assert(mask[0] == (1ul << 16) && mask[1] == 0);
            if (is("set_fail") || is("set_restore_fail")) { errno = EINVAL; return -1; }
            current_mode = mode;
            memset(current_mask, 0, sizeof current_mask);
            memcpy(current_mask, mask, 2 * sizeof *mask);
        } else {
            restores++;
            assert(mode == saved_mode);
            assert(maxnode == (saved_mode ? 1024 : 0));
            assert(saved_mode ? mask != NULL : mask == NULL);
            if (mask) assert(!memcmp(mask, saved_mask, sizeof saved_mask));
            if (is("restore_fail") || is("map_restore_fail") || is("set_restore_fail")) {
                errno = EIO; return -1;
            }
            current_mode = mode;
            memcpy(current_mask, saved_mask, sizeof saved_mask);
        }
        return 0;
    }
    assert(number == SYS_mbind);
    void *addr = va_arg(ap, void *);
    size_t len = va_arg(ap, size_t);
    assert(addr != MAP_FAILED && addr != NULL && len == mapped_len);
    assert(va_arg(ap, int) == 2);
    unsigned long *mask = va_arg(ap, unsigned long *);
    assert(mask[0] == (1ul << 16) && mask[1] == 0);
    assert(va_arg(ap, int) == 128);
    assert(va_arg(ap, int) == 0);
    va_end(ap);
    mbinds++;
    mbind_saw_restored = current_mode == saved_mode && !memcmp(current_mask, saved_mask, sizeof saved_mask);
    if (is("mbind_fail")) { errno = EIO; return -1; }
    return 0;
}

static void *s03_mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off) {
    assert(!addr && prot == (PROT_READ | PROT_WRITE));
    assert(flags == (MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB));
    assert(fd == -1 && off == 0);
    maps++;
    mapped_len = len;
    map_saw_hbm_only = current_mode == 2 && current_mask[0] == (1ul << 16);
    for (size_t i = 1; i < 16; i++) if (current_mask[i]) map_saw_hbm_only = 0;
    if (is("map_fail") || is("map_restore_fail")) { errno = ENOMEM; return MAP_FAILED; }
    /* No physical HBM, no MAP_HUGETLB, and no large physical allocation. */
    void *p = mmap(NULL, len, prot, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) { perror("test anonymous mmap"); _exit(90); }
    return p;
}

static int s03_munmap(void *addr, size_t len) { unmaps++; return munmap(addr, len); }

static void s03_exit(int code) { trace(); _exit(code); }

int main(int argc, char **argv) {
    assert(argc == 2);
    scenario = argv[1];
    saved_mask[0] = current_mask[0] = (1ul << 3) | (1ul << 19);
    saved_mask[4] = current_mask[4] = (1ul << 7); /* Check all 1024 bits, not only HBM mask. */
    if (!strncmp(scenario, "pages_", 6)) pages = strtol(scenario + 6, NULL, 10);
    if (is("read_negative")) pages = -1;
    if (is("cap_9000")) requested_mb = "9000";
    if (is("cap_64")) requested_mb = "64";
    if (is("below_min")) requested_mb = "63";
    if (is("old_default") || is("old_local")) {
        saved_mode = current_mode = is("old_default") ? 0 : 4;
        memset(saved_mask, 0, sizeof saved_mask);
        memset(current_mask, 0, sizeof current_mask);
    }
    if (is("old_preferred")) saved_mode = current_mode = 1;
    pthread_once(&once, init); /* Exact included implementation; fatal branches cannot return. */
    trace();
    void *p = NULL;
    assert(s03_posix_memalign(&p, 64, 256u << 10) == 0 && p);
    assert(!!in_arena(p) == !!base);
    memset(p, 0x5a, 256u << 10);
    assert(((unsigned char *)p)[(256u << 10) - 1] == 0x5a);
    s03_free(p);
    puts("RESULT returned_and_allocation_ok");
    return 0;
}
