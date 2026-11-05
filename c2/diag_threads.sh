#!/bin/bash
# CHOLMOD on KML gets slower with every added thread (val.sh step 2). On the real s0322 mesh (1 contact x 1 baseline
# x 2 breaths = 3 solves) measure:
#  A. N concurrent 1-thread jobs (throughput without threading; memory-bandwidth contention)
#  B. one 8-thread job under OpenMP knobs: passive wait, no nesting, KML multithreaded BLAS, CHOLMOD-only threads
set -e
H=/home/share/songzhenlong/eitfm; source $H/env.sh; cd $H/val
hostname; grep Cpus_allowed_list /proc/self/status
PY="python3 code/s6_corpus.py"; KML=/opt/HPCKit/kml-lib
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
cores() { echo "${CPUS[@]:$1:$2}" | tr ' ' ','; }
SMALL='{"contacts": 1, "baselines": 1, "breaths": 2}'
report() { python3 -c "
import json; r = json.load(open('$1/parts/s0322_p0_16_adjacent_c0.json'))['timing']
print('$2', 'factor_per_solve_s', round(r['factor_s'] / 3, 1), 'per_solve_s', round((r['assembly_s'] + r['factor_s'] + r['solve_s']) / 3, 1), 'unit_wall_s', round(r['unit_wall_s'], 1))"; }
prep() { rm -rf $1; mkdir -p $1; cp -r cases $1/; }

echo "== A. concurrent 1-thread jobs"
for n in 4 8; do
  for j in $(seq 0 $((n - 1))); do prep conc1_$j
    CFG_OVERRIDE="$SMALL" OMP_NUM_THREADS=1 taskset -c $(cores $j 1) $PY solve s0322 0 16_adjacent $PWD/conc1_$j > conc1_$j/log.txt 2>&1 &
  done; wait
  for j in $(seq 0 $((n - 1))); do report conc1_$j "  $n concurrent, job $j"; done
done

echo "== B. one job, 8 threads, OpenMP variants"
variant() { local name=$1; shift; prep var_$name
  env CFG_OVERRIDE="$SMALL" OMP_NUM_THREADS=8 "$@" taskset -c $(cores 0 8) $PY solve s0322 0 16_adjacent $PWD/var_$name > var_$name/log.txt 2>&1 \
    && report var_$name "  $name" || echo "  $name FAILED: $(grep -v '^CHOLMOD warning' var_$name/log.txt | tail -2 | tr '\n' ' ')"; }
variant passive_wait OMP_WAIT_POLICY=passive KMP_BLOCKTIME=0
variant no_nesting OMP_MAX_ACTIVE_LEVELS=1
variant kblas_multi LD_LIBRARY_PATH=$KML/sme/kblas/multi:$LD_LIBRARY_PATH
variant kblas_multi_no_nesting LD_LIBRARY_PATH=$KML/sme/kblas/multi:$LD_LIBRARY_PATH OMP_MAX_ACTIVE_LEVELS=1 OMP_WAIT_POLICY=passive
variant no_bind OMP_PROC_BIND=false OMP_PLACES=
echo DIAG_DONE
