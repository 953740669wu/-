#!/bin/bash
# C2 validation and tuning on one 32-core NUMA-packed allocation:
#  1. smoke units (s0322, placement 0, 16-belt, 2 contacts x 2 baselines x 2 breaths) vs the amax MUMPS results
#  2. one small unit at 1-32 threads
#  3. 4 concurrent 8-thread jobs, for jobs-per-NUMA-domain throughput
set -e
H=/home/share/songzhenlong/eitfm; source $H/env.sh; cd $H/val
hostname; grep Cpus_allowed_list /proc/self/status
PY="python3 code/s6_corpus.py"
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))   # cores granted
cores() { echo "${CPUS[@]:$1:$2}" | tr ' ' ','; }                                                 # cores <first> <count>
# wall time and peak RSS of a command (compute nodes have no /usr/bin/time)
timed() { python3 -c "import resource, subprocess, sys, time; t = time.time(); r = subprocess.call(sys.argv[1:]); print('maxrss_kB', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, 'wall_s', round(time.time() - t, 1)); sys.exit(r)" "$@"; }

echo "== 1. validation"
rm -rf parts
CFG_OVERRIDE='{"contacts": 2, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=8 \
  timed $PY solve s0322 0 16_adjacent $PWD | cut -c1-300
python3 - <<'PY'
import numpy as np
for c in (0, 1):
    a = np.load(f'ref/s0322_p0_16_adjacent_c{c}.npz'); b = np.load(f'parts/s0322_p0_16_adjacent_c{c}.npz')
    rel = lambda x, y: float(np.linalg.norm(x.astype(float) - y.astype(float)) / np.linalg.norm(x.astype(float)))
    da = a['v_cur'] - a['v_ref'][a['base_of_pair']]; db = b['v_cur'] - b['v_ref'][b['base_of_pair']]
    print('contact', c, 'v_ref', rel(a['v_ref'], b['v_ref']), 'v_cur', rel(a['v_cur'], b['v_cur']), 'dv', rel(da, db),
          'images', rel(a['images'], b['images']), 'z equal', bool(np.array_equal(a['z'], b['z'])),
          'J', rel(a['J_img'], b['J_img']) if 'J_img' in a.files else '-')
PY

echo "== 2. threads (1 contact x 1 baseline x 2 breaths = 3 solves)"
for t in 1 2 4 8 16 32; do
  d=scale_t$t; rm -rf $d; mkdir -p $d; cp -r cases $d/
  CFG_OVERRIDE='{"contacts": 1, "baselines": 1, "breaths": 2}' OMP_NUM_THREADS=$t taskset -c $(cores 0 $t) \
    $PY solve s0322 0 16_adjacent $PWD/$d > $d/log.txt
  python3 -c "
import json; r = json.load(open('$d/parts/s0322_p0_16_adjacent_c0.json'))['timing']
print('threads $t', {k: round(v, 2) for k, v in r.items()}, 'per_solve_s', round((r['assembly_s'] + r['factor_s'] + r['solve_s']) / 3, 2))"
done

echo "== 3. 4 concurrent jobs x 8 threads"
for j in 0 1 2 3; do
  d=conc_$j; rm -rf $d; mkdir -p $d; cp -r cases $d/
  CFG_OVERRIDE='{"contacts": 1, "baselines": 1, "breaths": 2}' OMP_NUM_THREADS=8 taskset -c $(cores $((8*j)) 8) \
    $PY solve s0322 0 16_adjacent $PWD/$d > $d/log.txt &
done
wait
for j in 0 1 2 3; do python3 -c "
import json; r = json.load(open('conc_$j/parts/s0322_p0_16_adjacent_c0.json'))['timing']
print('concurrent job $j per_solve_s', round((r['assembly_s'] + r['factor_s'] + r['solve_s']) / 3, 2), 'unit_wall_s', round(r['unit_wall_s'], 1))"; done
echo VAL_DONE
