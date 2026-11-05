#!/bin/bash
# CHOLMOD on OpenBLAS vs KML on the real s0322 mesh (1 contact x 1 baseline x 2 breaths = 3 solves), one run at a time
# on the first t cores of the allocation. The 2D test in build_openblas.sh slowed down 64x with 8 OpenBLAS threads; the
# 3D supernodes are much larger, so this checks whether BLAS threads pay off there. Voltages are compared with KML.
set -e
H=/home/share/songzhenlong/eitfm; cd $H/val
hostname; grep Cpus_allowed_list /proc/self/status
PY="python3 code/s6_corpus.py"
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
cores() { echo "${CPUS[@]:0:$1}" | tr ' ' ','; }
SMALL='{"contacts": 1, "baselines": 1, "breaths": 2}'
U=s0322_p0_16_adjacent_c0
report() { python3 -c "
import json, numpy as np
r = json.load(open('$1/parts/$U.json'))['timing']
a, b = np.load('$1/parts/$U.npz'), np.load('ob_kml_1/parts/$U.npz')
d = max(float(np.abs(a[k] - b[k]).max() / max(np.abs(b[k]).max(), 1e-300)) for k in b.files if a[k].dtype.kind == 'f')
print('$2', 'factor_per_solve_s', round(r['factor_s'] / 3, 1), 'per_solve_s', round((r['assembly_s'] + r['factor_s'] + r['solve_s']) / 3, 1),
      'unit_wall_s', round(r['unit_wall_s'], 1), 'max_rel_diff_vs_kml %.1e' % d)"; }
# run NAME ENVFILE CORES OMP OPENBLAS
run() { rm -rf ob_$1; mkdir -p ob_$1; cp -r cases ob_$1/
  ( source $H/$2; CFG_OVERRIDE="$SMALL" OMP_NUM_THREADS=$4 OPENBLAS_NUM_THREADS=$5 taskset -c $(cores $3) $PY solve s0322 0 16_adjacent $PWD/ob_$1 ) > ob_$1/log.txt 2>&1 \
    && report ob_$1 "  $1" || echo "  $1 FAILED: $(grep -v '^CHOLMOD warning' ob_$1/log.txt | tail -2 | tr '\n' ' ')"; }
run kml_1 env.sh 1 1 1
run ob_1 env_ob.sh 1 1 1
run ob_blas2 env_ob.sh 2 1 2
run ob_blas4 env_ob.sh 4 1 4
run ob_blas8 env_ob.sh 8 1 8
run ob_omp8 env_ob.sh 8 8 1
echo DIAG_OB_DONE
