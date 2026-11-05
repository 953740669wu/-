#!/bin/bash
# Dense packing in one NUMA domain (NUMA-packed allocation): 1, 7 and 14 concurrent single-thread units
# (s0322 p0, 16-belt, 1 contact x 2 baselines x 2 breaths). 7 units fit the domain's ~32 GB at ~4.5 GB each;
# 14 spill to remote memory. Reports per-unit times and peak-RSS checkpoints; checks the lone unit against val/ref.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt
source $H/env.sh
hostname; awk '/Cpus_allowed_list/' /proc/self/status
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
W=$O/conc2; rm -rf $W; mkdir -p $W/cases/s0322
cp $H/val/cases/s0322/prep.npz $H/val/cases/s0322/placements.json $H/val/cases/s0322/mesh_p0.npz $W/cases/s0322/
unit() {   # unit <tag> <core>
  mkdir -p $W/$1; ln -sfn $W/cases $W/$1/cases
  CFG_OVERRIDE='{"contacts": 1, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=1 taskset -c $2 \
    python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $W/$1 > $W/$1.log 2>&1
}
report() {
  python3 - "$W" "$1" <<'PY'
import json, glob, sys
W, pre = sys.argv[1], sys.argv[2]
r = [json.load(open(f)) for f in sorted(glob.glob(f'{W}/{pre}_*/parts/*.json'))]
g = lambda k: [x['timing'][k] for x in r]
fr = [(x['timing']['factor_s'] - x['timing']['factor_first_s']) / 5 for x in r]
sv = [x['timing']['solve_s'] / 6 for x in r]
print(f"{pre}: n={len(r)} unit_wall {min(g('unit_wall_s')):.0f}-{max(g('unit_wall_s')):.0f} s, refactor "
      f"{min(fr):.1f}-{max(fr):.1f} s, solve {min(sv):.2f}-{max(sv):.2f} s, first factor "
      f"{min(g('factor_first_s')):.1f}-{max(g('factor_first_s')):.1f} s, jacobian {min(g('jacobian_s')):.1f}-{max(g('jacobian_s')):.1f} s, "
      f"peak RSS {max(x['peak_rss_gb'] for x in r):.2f} GB, checkpoints {r[0]['peak_rss_checkpoints_gb']}")
PY
}
for n in 1 7 14; do
  echo "== $n concurrent in one NUMA domain"; t0=$(date +%s)
  for i in $(seq 0 $((n - 1))); do unit N${n}_$i ${CPUS[$i]} & done; wait
  echo "wall $(( $(date +%s) - t0 )) s"; report N$n
done
python3 - <<'PY'
import numpy as np
H = '/home/share/songzhenlong/eitfm'
a = np.load(f'{H}/val/ref/s0322_p0_16_adjacent_c0.npz'); b = np.load(f'{H}/opt/conc2/N1_0/parts/s0322_p0_16_adjacent_c0.npz')
print('N1 vs val/ref c0 float32-identical:', all(np.array_equal(a[k], b[k]) for k in ('v_ref', 'v_cur', 'images', 'J_img')))
PY
echo CONC2_DONE
