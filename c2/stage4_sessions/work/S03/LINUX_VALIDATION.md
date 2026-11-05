# Linux/glibc validation — NOT RUN in this Windows round

These commands do not submit a job. S00 must review this exact package and choose
an isolated execution directory and resource allocation. Do not run the tests or
load this library into production. No shared-library destination is used here.
The harness allocates at most about 4 GB virtual anonymous memory, touches only
256 KB per successful case and releases it on child exit; it reserves no HBM.

Copy the complete S03 directory preserving its contents. On 64-bit Linux/glibc,
from that isolated S03 directory, use the following. `CC` may be set to the
already provisioned compiler. Keep all output, including warnings and exit codes.

```bash
set -eu
export LC_ALL=C
S03_ROOT="$(pwd -P)"
test -f "$S03_ROOT/candidate/hbm_alloc.c"
sha256sum -c ARTIFACT_SHA256.txt
mkdir -p build linux_evidence
"${CC:-cc}" --version > linux_evidence/compiler.txt
uname -a > linux_evidence/uname.txt
getconf GNU_LIBC_VERSION > linux_evidence/glibc.txt

# Same harness, actual frozen implementation: it must fail the intended contract.
"${CC:-cc}" -std=gnu11 -O0 -g -Wall -Wextra -pthread \
  '-DS03_SOURCE="../frozen/hbm_alloc.c"' tests/fault_harness.c \
  -o build/faults_frozen > linux_evidence/build_frozen.txt 2>&1
before_rc=0
python3 -B tests/run_faults.py build/faults_frozen \
  --json linux_evidence/frozen_faults.json \
  > linux_evidence/frozen_faults.txt 2>&1 || before_rc=$?
printf '%s\n' "$before_rc" > linux_evidence/frozen_exit.txt
test "$before_rc" -eq 1
# Review frozen_faults.json: low-page and policy-failure cases must expose the
# intended failures; a compiler/runtime infrastructure failure is not that proof.

# Same checks, actual candidate C, no copied allocator implementation in tests.
"${CC:-cc}" -std=gnu11 -O0 -g -Wall -Wextra -pthread \
  tests/fault_harness.c -o build/faults_candidate \
  > linux_evidence/build_candidate_harness.txt 2>&1
python3 -B tests/run_faults.py build/faults_candidate \
  --json linux_evidence/candidate_faults.json \
  > linux_evidence/candidate_faults.txt 2>&1

# Production-form independent library; no fault substitutes are compiled into it.
"${CC:-cc}" -std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra \
  candidate/hbm_alloc.c -o build/libhbm_alloc_s03.so \
  > linux_evidence/build_library.txt 2>&1
"${CC:-cc}" -std=gnu11 -O2 -Wall -Wextra tests/policy_probe.c \
  -o build/policy_probe > linux_evidence/build_probe.txt 2>&1
printf '%s\n' \
  'harness: -std=gnu11 -O0 -g -Wall -Wextra -pthread' \
  'library: -std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra' \
  'probe: -std=gnu11 -O2 -Wall -Wextra' > linux_evidence/build_flags.txt
sha256sum candidate/hbm_alloc.c frozen/hbm_alloc.c build/* \
  > linux_evidence/built_sha256.txt
readelf -h build/libhbm_alloc_s03.so > linux_evidence/elf_header.txt
readelf -Ws build/libhbm_alloc_s03.so > linux_evidence/elf_symbols.txt
ldd build/libhbm_alloc_s03.so > linux_evidence/ldd.txt

# Real syscall smoke check without enabling HBM. Tests the isolated preload path,
# policy equality and the original DDR allocation/data path. Run only on an
# environment where the initial real get_mempolicy call is permitted.
env -u HBM_NODE -u HBM_MB -u HBM_MIN_KB -u HBM_STATS \
  LD_PRELOAD="$S03_ROOT/build/libhbm_alloc_s03.so" \
  "$S03_ROOT/build/policy_probe" \
  > linux_evidence/ddr_probe.txt 2>&1
```

Frozen harness failures are recorded by the same 25-case runner. Candidate
acceptance requires all 25 cases pass, not simply a successful harness build.
Each ordinary scenario checks returned allocation/data, disabled/enabled arena,
syscall counts/order, temporary single-HBM-node mask, and restoration mask/mode.
Each fatal scenario requires exit 1, a fatal restore diagnostic, no publication,
no model-continuation marker, and unmap if mmap succeeded. The harness replaces
syscalls and hugepage mapping, so its success does not test a real kernel policy
transition, physical HBM placement, page-pool races or concurrent initialization.
No model, torch, KML, math or performance comparison is involved.

## Real HBM follow-up, scheduled only by S00

The following is a **template**, not a submitted run. S00 must choose actual
allowed nodes, confirm the HBM pool is the existing 2 MB hugetlb pool, and freeze
cpuset/cgroup limits and original policy. Do not drain or resize a shared pool to
create faults. The ordinary probe touches 256 KB; it does not touch the whole
arena and cannot establish an arena-wide no-SIGBUS guarantee.

```bash
# Set DDR_NODE and HBM_NODE to S00-reviewed allowed nodes, inside its allocation.
: "${DDR_NODE:?S00 must select a DDR node}"
: "${HBM_NODE:?S00 must select its paired HBM node}"
POOL="/sys/devices/system/node/node${HBM_NODE}/hugepages/hugepages-2048kB/free_hugepages"
cat "$POOL" > linux_evidence/free_hugepages_before.txt
numactl --show > linux_evidence/original_numactl.txt
env HBM_NODE="$HBM_NODE" HBM_MB=64 HBM_STATS=1 \
  numactl --membind="$DDR_NODE,$HBM_NODE" \
  env LD_PRELOAD="$S03_ROOT/build/libhbm_alloc_s03.so" \
  "$S03_ROOT/build/policy_probe" \
  > linux_evidence/hbm_probe.txt 2>&1
cat "$POOL" > linux_evidence/free_hugepages_after.txt
```

Before/after free-page counts from a process that has already exited cannot prove
placement. S00 still needs controlled in-process residency/numa_maps evidence,
real policy snapshots during initialization and after return, expected fallback
under naturally insufficient/unknown capacity, and absence of SIGBUS during
bounded full-arena touches. A real failed-restore kernel test, if available, must
be isolated in a disposable process and prove termination. Do not call a stubbed
syscall test that real-kernel proof. Full allocator API/concurrency acceptance and
training/HBM performance remain outside this round.
