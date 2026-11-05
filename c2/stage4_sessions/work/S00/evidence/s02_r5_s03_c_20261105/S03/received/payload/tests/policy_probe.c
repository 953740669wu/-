/* Real Linux syscalls with the independently built LD_PRELOAD library.
 * A policy/data smoke check; successful mmap is not proof of HBM residency. */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

int main(void) {
    int before_mode, after_mode;
    unsigned long before[16] = {0}, after[16] = {0};
    if (syscall(SYS_get_mempolicy, &before_mode, before, 1024, 0, 0) != 0) {
        perror("probe get_mempolicy before"); return 2;
    }
    void *p = NULL;
    int rc = posix_memalign(&p, 64, 256u << 10);
    if (rc) { fprintf(stderr, "probe allocation: %s\n", strerror(rc)); return 3; }
    if (syscall(SYS_get_mempolicy, &after_mode, after, 1024, 0, 0) != 0) {
        perror("probe get_mempolicy after"); free(p); return 2;
    }
    if (before_mode != after_mode || memcmp(before, after, sizeof before)) {
        fputs("FAIL calling-thread policy changed\n", stderr); free(p); return 4;
    }
    if ((uintptr_t)p % 64) { fputs("FAIL alignment\n", stderr); free(p); return 5; }
    memset(p, 0x5a, 256u << 10); /* Touch every byte; SIGBUS is not intercepted. */
    for (size_t i = 0; i < (256u << 10); i++) {
        if (((unsigned char *)p)[i] != 0x5a) { free(p); return 6; }
    }
    printf("PASS policy_mode=%d mask_equal=1 alignment=64 data_bytes=%u address=%p\n",
           before_mode, 256u << 10, p);
    free(p);
    return 0;
}
