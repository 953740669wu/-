# S03 first-round pre-implementation contract

Scope: capacity under the existing 16-page reserve, and temporary calling-thread
NUMA policy failures. Keep public allocation functions, 64 MB activation minimum,
HBM_MB/default cap, size classes and DDR allocation path unchanged.

| Injected condition | Required behavior |
|---|---|
| No HBM_NODE | No policy/mapping calls; original DDR path |
| free pages 0/15/16/17/47 | No mapping; arena off (remaining MB < 64) |
| free pages 48/49 | Cap to 64/66 MB respectively |
| free pages 2020, default HBM_MB | 3800 MB arena requested |
| free pages 2020, HBM_MB=9000 | Cap to 4008 MB, preserving 16 pages |
| HBM_MB=63/64, sufficient pages | Off / request 64 MB |
| fopen/fscanf failure or negative count | Unknown capacity: arena off before any policy change |
| get_mempolicy fails | Arena off, no set/mmap; do not use an invalid snapshot |
| Temporary set_mempolicy fails | No mmap; conservatively attempt original-policy restoration, then DDR if successful |
| mmap fails | Restore original policy, then DDR; preserve mmap errno for reporting |
| mbind fails | Original policy already restored; unmap and DDR |
| Restore fails after set failure, mmap success or mmap failure | Do not publish arena or continue model; diagnostic, unmap any successful mapping, _exit(EXIT_FAILURE) |
| Success with original DEFAULT/BIND/PREFERRED/LOCAL | Restore captured mode and full captured mask before mbind/publication |

Restoration after even a failed temporary bind is a conservative single cleanup
path. If this cleanup itself fails, terminate rather than assert that policy is
safe. The implementation cannot guarantee successful restoration when the kernel
rejects it; termination is the explicit containment behavior.

Tests are written before candidate changes. Local Python checks reproduce the
original 64-bit arithmetic and check source contracts; they are static evidence,
not C execution. The Linux harness includes the actual source and replaces
page-count I/O, policy syscalls and hugepage mmap with controlled substitutes.
That harness must be run on Linux/glibc by S00 after package review. Even a pass
does not prove physical HBM residency, kernel policy behavior or concurrency.
