# New C bounds/API checks — Linux NOT RUN in this round

S00 must review this exact SHA package and execute it in its own isolated round
directory with the agreed 36-core allocation. These commands submit no job and
load no library. Do not run the old 25-case suite again or preload either old or
new .so into a model. No real HBM, page-pool modifications or performance tests.

The complete new round is self-contained; `frozen/hbm_alloc.c` is the previously
accepted candidate, not the original production allocator. From the copied round
root, on an existing 64-bit Linux/glibc toolchain:

```bash
set -eu
export LC_ALL=C
unset LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH HBM_NODE HBM_MB HBM_MIN_KB HBM_STATS
sha256sum -c ARTIFACT_SHA256.txt
mkdir -p build linux_evidence
python3 -B tests/verify_delivery.py --json linux_evidence/package_integrity.json
"${CC:-cc}" --version > linux_evidence/compiler.txt
uname -a > linux_evidence/uname.txt
getconf GNU_LIBC_VERSION > linux_evidence/glibc.txt
printf '%s\n' \
  '-std=gnu11 -O1 -g -Wall -Wextra -pthread -fsanitize=undefined -fno-sanitize-recover=all' \
  > linux_evidence/harness_flags.txt
export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1

# New tests against the preserved previous candidate: 21 failures and 29 controls
# are EXPECTATIONS, not yet observed. The runner must validate each one and
# reject infrastructure failure; its own successful expectation audit exits 0.
"${CC:-cc}" -std=gnu11 -O1 -g -Wall -Wextra -pthread \
  -fsanitize=undefined -fno-sanitize-recover=all \
  '-DS03_SOURCE="../frozen/hbm_alloc.c"' tests/bounds_harness.c \
  -o build/bounds_previous > linux_evidence/build_previous.txt 2>&1
python3 -B tests/run_cases.py build/bounds_previous \
  --source frozen/hbm_alloc.c --version previous \
  --json linux_evidence/previous_cases.json \
  > linux_evidence/previous_cases.txt 2>&1

# Same new tests and sanitizer settings, actual new candidate C.
"${CC:-cc}" -std=gnu11 -O1 -g -Wall -Wextra -pthread \
  -fsanitize=undefined -fno-sanitize-recover=all tests/bounds_harness.c \
  -o build/bounds_candidate > linux_evidence/build_candidate.txt 2>&1
python3 -B tests/run_cases.py build/bounds_candidate \
  --source candidate/hbm_alloc.c --version candidate \
  --json linux_evidence/candidate_cases.json \
  > linux_evidence/candidate_cases.txt 2>&1

# Independent production-form build: no test substitutions and no sanitizer.
"${CC:-cc}" -std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra \
  candidate/hbm_alloc.c -o build/libhbm_alloc_s03_round2.so \
  > linux_evidence/build_library.txt 2>&1
printf '%s\n' '-std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra' \
  > linux_evidence/library_flags.txt
sha256sum frozen/hbm_alloc.c candidate/hbm_alloc.c build/* \
  > linux_evidence/built_sha256.txt
readelf -h build/libhbm_alloc_s03_round2.so > linux_evidence/elf_header.txt
readelf -Ws build/libhbm_alloc_s03_round2.so > linux_evidence/elf_symbols.txt
ldd build/libhbm_alloc_s03_round2.so > linux_evidence/ldd.txt
```

Keep compiler warnings, command/child exits, all per-case stdout/stderr and
sanitizer messages. If UBSan/compiler support is missing, record a build blocker;
do not silently drop the sanitizer or call a build failure a detected allocator
defect. The previous-version runner expects exit 1 plus CHECK_FAIL for targeted
contract failures; only sum_last_safe/pointer_wrap additionally allow an exit-1
UBSan `runtime error:`. Signals/timeouts or other infrastructure errors do not
count as those expected failures. Its 29 controls must pass. The candidate must
pass all 50 new cases with no sanitizer failures. This is distinct from the
previous 25-case suite and does not rerun it.

Each child maps at most 64 MB of ordinary anonymous virtual memory and touches
small API buffers; the near-end case touches one last 64 KB block. Extreme-length
mmap probes fail in a substitute before reserving anything. Node rejection
checks zero page I/O/policy calls: the old code's invalid-node I/O is stopped by
the substitute to avoid deliberately executing an out-of-range stack write.
Allocation failures for posix_memalign/realloc are deterministic substitutes;
normal DDR allocation/copy/free uses glibc. Test names rename allocator exports
to avoid interposing on the test runner or sanitizer runtime.

No actual kernel NUMA policy, hugetlb pool, physical placement, full allocator
API/concurrency or training behavior is accepted by this suite. This round's
Windows host has not compiled or executed any C, Bash command block, or .so.
