#!/bin/bash
# One shard of the C2 corpus on one whole node (dsub cpu=608 with numa[count=16,...]; without the numa option the job
# gets one core per domain). Runs the frozen prod_tasks.sh (placements, 1-thread meshes, units, manifest) restricted
# to SLOTS_PER_DOMAIN cores in each NUMA domain, so the worker's slot pool has 3 x 16 = 48 single-thread slots.
# Resumable: finished meshes and units are skipped, so a failed or timed-out shard is simply resubmitted.
# Usage: prod_c2.sh <out> <shard file>
set -e -o pipefail
O=$1; SH=$2; K=${SLOTS_PER_DOMAIN:-3}
hostname; awk '/Cpus_allowed_list/' /proc/self/status
miss=$(for c in $(cat $SH); do for f in prep.npz body_base.stl; do [ -f $O/cases/$c/$f ] || echo "$c/$f"; done; done)
[ -z "$miss" ] || { echo "missing inputs:" $miss; exit 1; }
CORES=$(python3 - $K <<'PY'
import glob, os, sys
k, allowed, out = int(sys.argv[1]), os.sched_getaffinity(0), []
for d in sorted(glob.glob('/sys/devices/system/node/node[0-9]*'), key=lambda p: int(p.rsplit('node', 1)[1])):
    cs = []
    for part in filter(None, open(d + '/cpulist').read().strip().split(',')):   # memory-only nodes have no CPUs
        a, _, b = part.partition('-'); cs += range(int(a), int(b or a) + 1)
    out += [c for c in cs if c in allowed][:k]
print(','.join(map(str, out)))
PY
)
echo "slots on cores $CORES"
taskset -c $CORES bash $O/code/prod_tasks.sh $O $SH
n=$(python3 -c "
import sys; sys.path.insert(0, '$O/code'); import s6_corpus as S, os
cs = open('$SH').read().split()
want = [f'{c}_p{k}_{b}_c{j}' for c in cs for k in range(S.CFG['placements']) for b in S.CFG['belts'] for j in range(S.CFG['contacts'])]
print(sum(os.path.exists(f'$O/parts/{u}.json') for u in want), len(want))")
echo "shard $(basename $SH): units present $n"
echo PROD_SHARD_DONE
