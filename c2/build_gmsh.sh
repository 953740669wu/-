#!/bin/bash
# Build gmsh 4.15.1 (the version on amax) as a shared library + Python API for the system python3.9 on a C2
# compute node. Only what s2_mesh.py's volume step uses: STL import, geo kernel, size fields, HXT (OpenMP).
# Then mesh s0322 placement 0 with VOLUME_ONLY=1 and compare with the amax mesh.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; PKG=$H/pkg; SW=$H/sw
CXX=$SW/gxx/usr/bin/g++                       # relocated login-node g++ 10.3.1 (compute nodes have no g++), read only
export PATH=$SW/venv/bin:$PATH                 # cmake (read only; sw/build, sw/venv belong to the PETSc build)
mkdir -p $SW/gmsh_src; cd $SW/gmsh_src
echo "== node"; hostname; awk '/Cpus_allowed_list/' /proc/self/status
rm -rf gmsh-gmsh_4_15_1 gmsh_build; tar xzf $PKG/gmsh_4_15_1.tar.gz
mkdir gmsh_build; cd gmsh_build
cmake ../gmsh-gmsh_4_15_1 -DCMAKE_INSTALL_PREFIX=$SW/gmsh -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=$CXX -DENABLE_BUILD_DYNAMIC=1 -DENABLE_OPENMP=1 \
  -DENABLE_FLTK=0 -DENABLE_OCC=0 -DENABLE_MPI=0 -DENABLE_PETSC=0 -DENABLE_SLEPC=0 -DENABLE_MED=0 -DENABLE_CGNS=0 \
  -DENABLE_BLAS_LAPACK=0 -DENABLE_MMG=0 -DENABLE_OS_SPECIFIC_INSTALL=0 2>&1 | tail -25
make -j 32 2>&1 | grep -E "error|Error|warning: unused" | head -20 || true
make install 2>&1 | tail -3
ls $SW/gmsh/lib*

echo "== python API"
GL=$(dirname $(find $SW/gmsh -name gmsh.py | head -1)); echo "gmsh.py in $GL"; echo $GL > $SW/gmsh_pylib.txt
export PYTHONPATH=$GL
/usr/bin/python3 -c "import gmsh; print('gmsh', gmsh.__version__)"

echo "== s0322 placement 0, volume only"
T=$H/val/gmsh_test; rm -rf $T; mkdir -p $T/cases/s0322
cp $H/val/cases/s0322/prep.npz $H/val/body_base_s0322.stl $T/cases/s0322/
mv $T/cases/s0322/body_base_s0322.stl $T/cases/s0322/body_base.stl
cd $H/val
for th in 4 16; do
  VOLUME_ONLY=1 GMSH_THREADS=$th MESH_OUT=mesh_p0_t$th PLANE=0.000000000,0.086089077,0.996287444,0.173619534 \
    /usr/bin/time -f "maxrss_kB %M wall %e" /usr/bin/python3 code/s2_mesh.py s0322 $T
done
/usr/bin/python3 - <<'PY'
import json, numpy as np
T = '/home/share/songzhenlong/eitfm/val/gmsh_test/cases/s0322/'
a = json.load(open('/home/share/songzhenlong/eitfm/val/mesh_p0_amax.json'))
print('amax  ', {k: a[k] for k in ('nodes', 'tets', 'surface_triangles', 'mesh_volume_L', 'min_vol_m3')}, a['timing'])
for th in (4, 16):
    b = json.load(open(T + f'mesh_p0_t{th}.json'))
    print(f'c2 t{th:<2}', {k: b[k] for k in ('nodes', 'tets', 'surface_triangles', 'mesh_volume_L', 'min_vol_m3')}, b['timing'])
PY
echo GMSH_DONE
