#!/bin/bash
# Production layout: k concurrent single-thread units in every NUMA domain of one whole node (k = 1, 2, 3, 5; 5 x ~5.5 GB
# fits a domain's ~32 GB). s0322 p0, 16-belt, 1 contact x 2 baselines x 2 breaths (6 solves), optimized code in opt/code,
# same unit as opt/run_conc2_opt.sh so times compare with the peer's 1-unit (refactor 12.5-13.1 s) and 16-spread runs.
# Reports per-round wall time, refactor/solve/Jacobian ranges, peak RSS, and that every unit matches val/ref c0.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt
source $H/env.sh
hostname; awk '/Cpus_allowed_list/' /proc/self/status
W=$H/val/density; rm -rf $W; mkdir -p $W/cases/s0322
cp $H/val/cases/s0322/prep.npz $H/val/cases/s0322/placements.json $H/val/cases/s0322/mesh_p0.npz $W/cases/s0322/
# cores_for k: k allowed cores from each NUMA domain, space separated; fails if a domain has fewer than k
cores_for() { python3 - $1 <<'PY'
import glob, os, sys
k, allowed, out = int(sys.argv[1]), os.sched_getaffinity(0), []
for d in sorted(glob.glob('/sys/devices/system/node/node[0-9]*'), key=lambda p: int(p.rsplit('node', 1)[1])):
    cs = []
    for part in filter(None, open(d + '/cpulist').read().strip().split(',')):   # memory-only nodes have no CPUs
        a, _, b = part.partition('-'); cs += range(int(a), int(b or a) + 1)
    cs = [c for c in cs if c in allowed]
    if cs and len(cs) < k: sys.exit(f'{d} has only {len(cs)} allowed cores')
    out += cs[:k] if cs else []
print(' '.join(map(str, out)))
PY
}
echo "domains with allowed cores: $(cores_for 1 | wc -w)"
unit() {   # unit <tag> <core>
  mkdir -p $W/$1; ln -sfn $W/cases $W/$1/cases
  CFG_OVERRIDE='{"contacts": 1, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=1 taskset -c $2 \
    python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $W/$1 > $W/$1.log 2>&1
}
report() {
  python3 - "$W" "$1" <<'PY'
import json, glob, sys, numpy as np
W, pre = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(f'{W}/{pre}_*/parts/*.json')); r = [json.load(open(f)) for f in fs]
g = lambda k: [x['timing'][k] for x in r]
fr = [(x['timing']['factor_s'] - x['timing']['factor_first_s']) / 5 for x in r]
sv = [x['timing']['solve_s'] / 6 for x in r]
ref = np.load('/home/share/songzhenlong/eitfm/val/ref/s0322_p0_16_adjacent_c0.npz')
same = all(all(np.array_equal(ref[k], np.load(f[:-5] + '.npz')[k]) for k in ('v_ref', 'v_cur', 'images', 'J_img')) for f in fs)
print(f"{pre}: n={len(r)} unit_wall {min(g('unit_wall_s')):.0f}-{max(g('unit_wall_s')):.0f} s, refactor "
      f"{min(fr):.1f}-{np.median(fr):.1f}-{max(fr):.1f} s (min-median-max), solve {min(sv):.2f}-{max(sv):.2f} s, "
      f"jacobian {min(g('jacobian_s')):.1f}-{max(g('jacobian_s')):.1f} s, peak RSS {max(x['peak_rss_gb'] for x in r):.2f} GB, "
      f"all match val/ref: {same}")
PY
}
for k in 1 2 3 5; do
  CS=($(cores_for $k)); n=${#CS[@]}
  echo "== $k per domain, $n units"; t0=$(date +%s)
  for i in $(seq 0 $((n - 1))); do unit K${k}_$i ${CS[$i]} & done; wait
  echo "wall $(( $(date +%s) - t0 )) s"; report K$k
done
echo DENSITY_DONE
