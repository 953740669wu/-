#!/bin/bash
# Mesh s0322 placement 0 on a C2 node with the gmsh built by build_gmsh.sh (VOLUME_ONLY=1, from the amax
# body_base.stl) at several thread counts, and compare size, volume and quality with the amax mesh.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; SW=$H/sw
export PYTHONPATH=$(cat $SW/gmsh_pylib.txt)
hostname; awk '/Cpus_allowed_list/' /proc/self/status
T=$H/val/gmsh_test; rm -rf $T; mkdir -p $T/cases/s0322
cp $H/val/cases/s0322/prep.npz $T/cases/s0322/
cp $H/val/body_base_s0322.stl $T/cases/s0322/body_base.stl
cd $H/val
for th in 4 16 32; do
  echo "== gmsh threads $th"
  VOLUME_ONLY=1 GMSH_THREADS=$th MESH_OUT=mesh_p0_t$th PLANE=0.000000000,0.086089077,0.996287444,0.173619534 \
    /usr/bin/python3 -c "
import resource, subprocess, sys, time
t = time.perf_counter(); subprocess.run(sys.argv[1:], check=True, stdout=subprocess.DEVNULL)
print('maxrss_kB', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, 'wall_s', round(time.perf_counter() - t, 1))
" /usr/bin/python3 code/s2_mesh.py s0322 $T
done
/usr/bin/python3 - <<'PY'
import json
T = '/home/share/songzhenlong/eitfm/val/gmsh_test/cases/s0322/'
keys = ('nodes', 'tets', 'surface_triangles', 'mesh_volume_L', 'min_vol_m3')
a = json.load(open('/home/share/songzhenlong/eitfm/val/mesh_p0_amax.json'))
print('amax ', {k: a[k] for k in keys}, {k: round(v, 1) for k, v in a['timing'].items()})
for th in (4, 16, 32):
    b = json.load(open(T + f'mesh_p0_t{th}.json'))
    print(f'c2 t{th:<2}', {k: b[k] for k in keys}, {k: round(v, 1) for k, v in b['timing'].items()},
          'nodes_rel_diff', round(b['nodes'] / a['nodes'] - 1, 4), 'vol_rel_diff', f"{b['mesh_volume_L'] / a['mesh_volume_L'] - 1:.2e}")
PY
echo GMSH_TEST_DONE
