#!/bin/bash
# Packing test for single-thread units (s0322 p0, 16-belt, 1 contact x 2 baselines x 2 breaths = 6 solves each):
#  A. one unit alone (+ check against val/ref contact 0)
#  B. one unit per NUMA domain, concurrently
#  C. two units per NUMA domain, concurrently
# Reports per-unit wall, factor time and peak RSS. Writes only under eitfm/opt.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt
source $H/env.sh
hostname; awk '/Cpus_allowed_list/' /proc/self/status
W=$O/conc; rm -rf $W; mkdir -p $W/cases/s0322
cp $H/val/cases/s0322/prep.npz $H/val/cases/s0322/placements.json $H/val/cases/s0322/mesh_p0.npz $W/cases/s0322/
# allowed cores grouped by NUMA node: "node core" lines
python3 - > $W/cores.txt <<'PY'
import os, glob
cpus = sorted(os.sched_getaffinity(0))
node = {}
for d in glob.glob('/sys/devices/system/node/node*/cpulist'):
    n = int(d.split('node')[-1].split('/')[0])
    for part in open(d).read().strip().split(','):
        if part:
            a, b = (part.split('-') + [part])[:2]
            for c in range(int(a), int(b) + 1):
                node[c] = n
for c in cpus:
    print(node.get(c, -1), c)
PY
echo "allowed cores per NUMA node:"; awk '{print $1}' $W/cores.txt | sort -n | uniq -c | tr '\n' ' '; echo
first=$(awk '!s[$1]++ {print $2}' $W/cores.txt)                 # first allowed core of each node
second=$(awk 's[$1]++ == 1 {print $2}' $W/cores.txt)            # second allowed core of each node
unit() {   # unit <tag> <core>
  mkdir -p $W/$1; ln -sfn $W/cases $W/$1/cases
  CFG_OVERRIDE='{"contacts": 1, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=1 taskset -c $2 \
    python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $W/$1 > $W/$1.log 2>&1
}
report() {  # report <tag prefix>
  python3 - "$W" "$1" <<'PY'
import json, glob, sys
W, pre = sys.argv[1], sys.argv[2]
r = [json.load(open(f)) for f in sorted(glob.glob(f'{W}/{pre}*/parts/*.json'))]
if not r:
    print(pre, 'no results'); sys.exit()
g = lambda k: [x['timing'][k] for x in r]
fr = [(x['timing']['factor_s'] - x['timing']['factor_first_s']) / 5 for x in r]
print(f"{pre}: n={len(r)} unit_wall {min(g('unit_wall_s')):.0f}-{max(g('unit_wall_s')):.0f} s, refactor/solve "
      f"{min(fr):.1f}-{max(fr):.1f} s, first factor {min(g('factor_first_s')):.1f}-{max(g('factor_first_s')):.1f} s, "
      f"peak RSS {max(x['peak_rss_gb'] for x in r):.2f} GB, checkpoints {r[0]['peak_rss_checkpoints_gb']}")
PY
}
echo "== A. alone"; t0=$(date +%s); unit A $(echo $first | awk '{print $1}'); echo "wall $(( $(date +%s) - t0 )) s"; report A
python3 - <<'PY'
import numpy as np
H = '/home/share/songzhenlong/eitfm'
a = np.load(f'{H}/val/ref/s0322_p0_16_adjacent_c0.npz'); b = np.load(f'{H}/opt/conc/A/parts/s0322_p0_16_adjacent_c0.npz')
# 1 contact x 2 baselines x 2 breaths here vs 2 x 2 x 2 in val/ref: contact 0 is drawn from the same seeds
print('A vs val/ref c0 float32-identical:', all(np.array_equal(a[k], b[k]) for k in ('v_ref', 'v_cur', 'images', 'J_img')))
PY
echo "== B. one per NUMA node"; t0=$(date +%s); i=0
for c in $first; do unit B$i $c & i=$((i + 1)); done; wait; echo "wall $(( $(date +%s) - t0 )) s"; report B
echo "== C. two per NUMA node"; t0=$(date +%s); i=0
for c in $first $second; do unit C$i $c & i=$((i + 1)); done; wait; echo "wall $(( $(date +%s) - t0 )) s"; report C
echo CONC_DONE
