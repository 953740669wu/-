/* Exercise the real allocator, kernel policy, page pool and DDR fallback. */
#define _GNU_SOURCE
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#define MIB (1u << 20)
#define BLOCK (2u * MIB - 64u)
#define THREADS 4

static pthread_barrier_t gate;
static void *blocks[THREADS];

static void require(int ok, const char *message) {
    if (!ok) {
        fprintf(stderr, "FAIL %s\n", message);
        exit(2);
    }
}

static void *allocate(size_t bytes) {
    void *p = NULL;
    require(posix_memalign(&p, 64, bytes) == 0 && p && (uintptr_t)p % 64 == 0,
            "posix_memalign");
    return p;
}

static void touch(void *p, size_t bytes, unsigned char pattern) {
    volatile unsigned char *b = p;
    for (size_t i = 0; i < bytes; i += 4096) b[i] = pattern;
    b[bytes - 1] = pattern;
    for (size_t i = 0; i < bytes; i += 4096) require(b[i] == pattern, "page data");
    require(b[bytes - 1] == pattern, "last byte");
}

static void *worker(void *arg) {
    const int n = *(int *)arg;
    for (int round = 0; round < 8; round++) {
        pthread_barrier_wait(&gate);
        void *p = allocate(BLOCK);
        touch(p, BLOCK, (unsigned char)(round + n + 1));
        pthread_barrier_wait(&gate);
        if (round == 7) blocks[n] = p;
        else free(p);
    }
    return NULL;
}

static void snapshot(const char *name, const char *target) {
    FILE *in = fopen(name, "r");
    FILE *out = fopen(target, "w");
    require(in && out, "open proc snapshot");
    char buf[4096];
    size_t count;
    while ((count = fread(buf, 1, sizeof buf, in)) != 0)
        require(fwrite(buf, 1, count, out) == count, "write proc snapshot");
    require(!ferror(in), "read proc snapshot");
    fclose(in);
    require(fclose(out) == 0, "close proc snapshot");
}

int main(int argc, char **argv) {
    require(argc == 2, "arena size argument");
    unsigned long cap = strtoul(argv[1], NULL, 10);
    require(cap >= 64 && cap <= 3800 && cap % 2 == 0, "arena bound");
    int mode_before, mode_after;
    unsigned long before[16] = {0}, after[16] = {0};
    require(syscall(SYS_get_mempolicy, &mode_before, before, 1024, 0, 0) == 0,
            "get_mempolicy before");
    void *first = allocate(BLOCK);
    touch(first, BLOCK, 0x5a);
    require(syscall(SYS_get_mempolicy, &mode_after, after, 1024, 0, 0) == 0 &&
            mode_before == mode_after && memcmp(before, after, sizeof before) == 0,
            "restore calling-thread policy");
    require(pthread_barrier_init(&gate, NULL, THREADS) == 0, "init worker barrier");
    pthread_t tids[THREADS];
    int ids[THREADS];
    for (int i = 0; i < THREADS; i++) {
        ids[i] = i;
        require(pthread_create(&tids[i], NULL, worker, &ids[i]) == 0, "start worker");
    }
    for (int i = 0; i < THREADS; i++)
        require(pthread_join(tids[i], NULL) == 0, "join worker");
    pthread_barrier_destroy(&gate);
    const size_t remainder = (cap - 2 * (1 + THREADS)) * MIB - 64;
    void *bulk = allocate(remainder);
    touch(bulk, remainder, 0xb3);
    void *fallback = allocate(BLOCK);
    touch(fallback, BLOCK, 0xda);
    const uintptr_t released = (uintptr_t)blocks[0];
    free(blocks[0]);
    blocks[0] = allocate(BLOCK);
    require((uintptr_t)blocks[0] == released, "exact size reuse while arena full");
    touch(blocks[0], BLOCK, 0xc4);
    printf("first=%p bulk=%p fallback=%p\n", first, bulk, fallback);
    for (int i = 0; i < THREADS; i++) printf("worker%d=%p\n", i, blocks[i]);
    snapshot("/proc/self/maps", "probe.maps");
    snapshot("/proc/self/numa_maps", "probe.numa_maps");
    snapshot("/proc/self/status", "probe.status");
    free(fallback);
    free(bulk);
    for (int i = 0; i < THREADS; i++) free(blocks[i]);
    free(first);
    printf("PASS policy_restored=1 worker_threads=%d reuse=1 arena_MiB=%lu\n", THREADS, cap);
    return 0;
}
