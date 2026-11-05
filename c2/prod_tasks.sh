#!/bin/bash
# C2 production worker for one allocation (run by prod_c2.sh): one single-thread task per allowed core, from a queue.
# Same stages as opt/run_c2_tasks.sh (placements, 1-thread meshes, units, manifest), but a solve task is ONE UNIT
# (case, placement, belt, contact) instead of a whole task: with 25 contacts a task is 25 units in series (~13 h), while
# units fill the 48 slots evenly. s6_corpus solve runs every contact of a task whose part file is missing, so each unit
# runs in its own folder <out>/run/<unit> holding empty placeholder parts for the other contacts (as pilot_c2.sh did
# for pilots 2-4); seeds depend only on the unit's coordinates. A finished unit's npz, then json, move to <out>/parts.
# Resumable: finished meshes and units are skipped.
# Usage: prod_tasks.sh <out> <case list file> [belts, default "16_adjacent 32_skip4"]
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$1; CL=$2; BELTS=${3:-"16_adjacent 32_skip4"}
source $H/env.sh
export PYTHONPATH=$(cat $H/sw/gmsh_pylib.txt):$PYTHONPATH O
cd $O; mkdir -p logs parts run
hostname; awk '/Cpus_allowed_list/' /proc/self/status
export CPULIST=$(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))")
NS=$(echo $CPULIST | wc -w)
CASES=$(grep -v '^#' $CL | awk 'NF {print $1}')
read NP NC < <(python3 -c "import sys; sys.path.insert(0, 'code'); import s6_corpus as S; print(S.CFG['placements'], S.CFG['contacts'])")
export NC
echo "$(echo $CASES | wc -w) cases, $NP placements, $NC contacts, belts: $BELTS, $NS slots"

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
task_unit() {   # case k belt contact core
  local u=$1_p$2_$3_c$4 D=$O/run/$1_p$2_$3_c$4
  [ -f parts/$u.json ] && return 0
  rm -rf $D; mkdir -p $D/parts; ln -s $O/cases $D/cases
  for o in $(seq 0 $((NC - 1))); do [ $o = $4 ] || touch $D/parts/$1_p$2_$3_c$o.json; done
  OMP_NUM_THREADS=1 taskset -c $5 python3 code/s6_corpus.py solve $1 $2 $3 $D > logs/unit_$u.log 2>&1
  mv $D/parts/$u.npz parts/ && mv $D/parts/$u.json parts/ && rm -rf $D
}
export -f task_mesh task_unit

t0=$(date +%s)
for c in $CASES; do python3 code/s6_corpus.py placements $c $O > logs/${c}_placements.txt; done
echo "placements done ($(( $(date +%s) - t0 )) s)"
for c in $CASES; do for k in $(seq 0 $((NP - 1))); do echo "mesh $c $k"; done; done > logs/tasks_mesh_$(basename $CL)
pool logs/tasks_mesh_$(basename $CL)
echo "meshes done ($(( $(date +%s) - t0 )) s): $(ls cases/*/mesh_p*.npz 2>/dev/null | wc -l) present"
# longest units first (32-electrode belts), then each task's contact 0 (it also builds the Jacobian)
for b in $(echo $BELTS | tr ' ' '\n' | sort -r); do for j in $(seq 0 $((NC - 1))); do for c in $CASES; do
  for k in $(seq 0 $((NP - 1))); do echo "unit $c $k $b $j"; done; done; done; done > logs/tasks_unit_$(basename $CL)
pool logs/tasks_unit_$(basename $CL)
echo "units done ($(( $(date +%s) - t0 )) s)"
python3 code/s6_corpus.py manifest $O
echo C2_TASKS_DONE
