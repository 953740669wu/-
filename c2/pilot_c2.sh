#!/bin/bash
# Rerun of the amax Phase 4 pilot (/mnt/lvliannas/szl/thorax_eitfm_pilot_20261101) on one whole C2 node with the optimized
# code (opt/code): the same prep, placements and meshes, copied from amax into pilot_c2/cases. Every unit (one contact)
# gets its own single-thread process; all are launched at once, round-robin over the 16 NUMA domains (50 units = 3 or 4
# per domain). s6_corpus solve runs every contact of a task whose part file is missing, so each unit runs in its own out
# dir holding empty placeholder parts for the other contacts. Seeds depend only on the unit's coordinates, not on which
# contacts run together. Finished units are moved to <W>/parts and skipped on a rerun.
# W (env, default pilot_c2): the run folder; it needs cases/ (a symlink to pilot_c2/cases is fine). The code is
# taken from <W>/code when present (frozen for that run), else from opt/code.
# Usage: [W=<run folder>] pilot_c2.sh <unit list file>   (lines: case placement belt contact)
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; W=${W:-$H/pilot_c2}; UL=$1
CODE=$H/opt/code; [ -f $W/code/s6_corpus.py ] && CODE=$W/code
source $H/env.sh
cd $W; mkdir -p parts run
echo "run folder $W, code $CODE ($(md5sum < $CODE/s6_corpus.py | cut -c1-10))"
hostname; awk '/Cpus_allowed_list/' /proc/self/status
mapfile -t U < $UL; n=${#U[@]}
CS=($(python3 - $n <<'PY'
import glob, os, sys
n, allowed, doms = int(sys.argv[1]), os.sched_getaffinity(0), []
for d in sorted(glob.glob('/sys/devices/system/node/node[0-9]*'), key=lambda p: int(p.rsplit('node', 1)[1])):
    cs = []
    for part in filter(None, open(d + '/cpulist').read().strip().split(',')):   # memory-only nodes have no CPUs
        a, _, b = part.partition('-'); cs += range(int(a), int(b or a) + 1)
    cs = [c for c in cs if c in allowed]
    if cs: doms.append(cs)
print(' '.join(str(doms[i % len(doms)][i // len(doms)]) for i in range(n)))
PY
))
echo "$n units on cores ${CS[*]}"
t0=$(date +%s)
for i in $(seq 0 $((n - 1))); do set -- ${U[$i]}; u=${1}_p${2}_${3}_c$4; D=$W/run/$u
  [ -f parts/$u.json ] && continue
  rm -rf $D; mkdir -p $D/parts; ln -s $W/cases $D/cases
  for o in 0 1 2 3 4; do [ $o = $4 ] || touch $D/parts/${1}_p${2}_${3}_c$o.json; done
  ( OMP_NUM_THREADS=1 taskset -c ${CS[$i]} python3 $CODE/s6_corpus.py solve $1 $2 $3 $D > $D/log.txt 2>&1 \
      && mv $D/parts/$u.json $D/parts/$u.npz parts/ || echo "FAILED $u" ) &
done; wait
echo "wall $(( $(date +%s) - t0 )) s, $(ls parts/*.json | wc -l) units in parts"
echo PILOT_C2_DONE
