#!/bin/bash
# Stage 3 benchmark job (one 32-core NUMA-packed allocation): old vs new path, CHOLMOD orderings, thread scaling of
# the refactorisation. Reads val/cases/s0322 only; writes nothing outside eitfm/opt.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt
source $H/env.sh                                  # PETSc/CHOLMOD/KML runtime of the main session (read only)
hostname; awk '/Cpus_allowed_list/' /proc/self/status
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
cores() { echo "${CPUS[@]:0:$1}" | tr ' ' ','; }
B="python3 $O/bench_s3.py $O/code $H/val/cases/s0322"
OMP_NUM_THREADS=1 taskset -c $(cores 1) $B compare
OMP_NUM_THREADS=1 taskset -c $(cores 1) $B orderings
for t in 1 2 4 8 16; do OMP_NUM_THREADS=$t taskset -c $(cores $t) $B refactor; done
echo BENCH_DONE
