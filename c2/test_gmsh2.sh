#!/bin/bash
# gmsh on a C2 node, s0322 placement 0 (VOLUME_ONLY=1):
#  1. one single-thread mesh with gmsh's per-stage wall/CPU times
#  2. 8, then 16 concurrent single-thread meshes, one pinned core each: throughput per allocation
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; SW=$H/sw
export PYTHONPATH=$(cat $SW/gmsh_pylib.txt) OMP_PLACES=cores OMP_PROC_BIND=close
hostname; awk '/Cpus_allowed_list/' /proc/self/status
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
T=$H/val/gmsh_test2; rm -rf $T; mkdir -p $T/cases/s0322
cp $H/val/cases/s0322/prep.npz $T/cases/s0322/
cp $H/val/body_base_s0322.stl $T/cases/s0322/body_base.stl
cd $H/val
PL=0.000000000,0.086089077,0.996287444,0.173619534
mesh() {   # mesh <out name> <core>
  VOLUME_ONLY=1 GMSH_THREADS=1 OMP_NUM_THREADS=1 MESH_OUT=$1 PLANE=$PL taskset -c $2 /usr/bin/python3 code/s2_mesh.py s0322 $T
}

echo "== 1. profile, 1 thread"
GMSH_VERBOSE=1 mesh prof ${CPUS[0]} 2>&1 | grep -E "Wall|Done|Meshing|Optimiz|Info    : [0-9]+ (nodes|elements)|HXT|Tetrahedrizing|Reconstructing|Total" | cut -c1-160 > $T/prof.txt || true
cat $T/prof.txt

for n in 8 16; do
  echo "== 2. $n concurrent single-thread meshes"
  t0=$(date +%s.%N)
  for j in $(seq 0 $((n - 1))); do mesh c${n}_$j ${CPUS[$j]} > $T/c${n}_$j.log 2>&1 & done
  wait
  t1=$(date +%s.%N)
  python3 - $n $t0 $t1 <<'PY'
import json, sys
n, t0, t1 = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
T = '/home/share/songzhenlong/eitfm/val/gmsh_test2/cases/s0322/'
r = [json.load(open(T + f'c{n}_{j}.json')) for j in range(n)]
v = [x['timing']['gmsh_volume_s'] for x in r]
print(f'{n} concurrent: allocation wall {t1 - t0:.0f} s, per-mesh gmsh_volume_s min {min(v):.0f} max {max(v):.0f}, '
      f'effective {(t1 - t0) / n:.0f} s/mesh, nodes {min(x["nodes"] for x in r)}-{max(x["nodes"] for x in r)}')
PY
done
python3 -c "
import json; r = json.load(open('$T/cases/s0322/prof.json')); print('1 thread alone: gmsh_volume_s', round(r['timing']['gmsh_volume_s']), 'nodes', r['nodes'])"
echo GMSH_TEST2_DONE
