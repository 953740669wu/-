#!/bin/bash
# C2 corpus worker for one allocation: one single-thread task per allowed core, pulled from a shared queue.
#   <out>/cases/<case>/{prep.npz, body_base.stl} come from amax (stage 1 + body surface); everything else is made here:
#   1. placements (serial, numpy only)  2. volume meshes, VOLUME_ONLY=1, GMSH_THREADS=1 (deterministic)
#   3. corpus units (s6_corpus solve, OMP_NUM_THREADS=1)  4. manifest
# Resumable: finished meshes and units are skipped. An unpacked allocation gives one core per NUMA domain, which
# avoids the per-domain bandwidth contention measured in opt_conc2 (7+ units in one domain: up to 2x slower).
# Usage: run_c2_tasks.sh <out> <case list file> [belts, default "16_adjacent 32_skip4"]
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$1; CL=$2; BELTS=${3:-"16_adjacent 32_skip4"}
source $H/env.sh
export PYTHONPATH=$(cat $H/sw/gmsh_pylib.txt):$PYTHONPATH O
cd $O; mkdir -p logs
hostname; awk '/Cpus_allowed_list/' /proc/self/status
export CPULIST=$(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))")
NS=$(echo $CPULIST | wc -w)
CASES=$(grep -v '^#' $CL | awk 'NF {print $1}')
NP=$(python3 -c "import sys; sys.path.insert(0, 'code'); import s6_corpus as S; print(S.CFG['placements'])")
echo "$(echo $CASES | wc -w) cases, $NP placements, belts: $BELTS, $NS slots"

# one slot = one core: GNU xargs gives each running command its slot number
pool() {   # pool <task file>: run each line as "bash -c 'task $line'" on the slot's core
  xargs -a $1 -P $NS -L 1 --process-slot-var=SLOT bash -c '
    core=$(echo $CPULIST | cut -d" " -f$((SLOT + 1)))
    task_$0 "$@" $core || echo "FAILED $0 $*"'
}
task_mesh() {   # case k core
  [ -f cases/$1/mesh_p$2.npz ] && return 0
  env $(sed -n "$(($2 + 1))p" logs/$1_placements.txt) VOLUME_ONLY=1 GMSH_THREADS=1 OMP_NUM_THREADS=1 \
    taskset -c $3 python3 code/s2_mesh.py $1 $O > logs/$1_mesh_p$2.log 2>&1
}
task_solve() {  # case k belt core
  OMP_NUM_THREADS=1 taskset -c $4 python3 code/s6_corpus.py solve $1 $2 $3 $O >> logs/solve_$1_p$2_$3.log 2>&1
}
export -f task_mesh task_solve

t0=$(date +%s)
for c in $CASES; do python3 code/s6_corpus.py placements $c $O > logs/${c}_placements.txt; done
echo "placements done ($(( $(date +%s) - t0 )) s)"
for c in $CASES; do for k in $(seq 0 $((NP - 1))); do echo "mesh $c $k"; done; done > logs/tasks_mesh.txt
pool logs/tasks_mesh.txt
echo "meshes done ($(( $(date +%s) - t0 )) s): $(ls cases/*/mesh_p*.npz 2>/dev/null | wc -l) present"
# longest units first (32-electrode belts) so the queue ends evenly
for b in $(echo $BELTS | tr ' ' '\n' | sort -r); do for c in $CASES; do for k in $(seq 0 $((NP - 1))); do
  echo "solve $c $k $b"; done; done; done > logs/tasks_solve.txt
pool logs/tasks_solve.txt
echo "units done ($(( $(date +%s) - t0 )) s)"
python3 code/s6_corpus.py manifest $O
echo C2_TASKS_DONE
