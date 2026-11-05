#!/bin/bash
# Build PETSc 3.25.3 (no MPI, no Fortran) with SuiteSparse/CHOLMOD on KML BLAS/LAPACK, plus petsc4py for the
# system python3.9, on a C2 compute node. Picks the fastest KML BLAS variant that passes a dgemm/dpotrf check.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; PKG=$H/pkg; SW=$H/sw; KML=/opt/HPCKit/kml-lib
mkdir -p $SW/build; cd $SW/build
echo "== node"; hostname; awk '/Cpus_allowed_list/' /proc/self/status
# Cython 3.3 rejects petsc4py 3.25.3 (PC.pyx: "Invalid index type 'int'"), hence cython<3.2
# STAGE=install reuses an existing configured and compiled tree and only runs make install + the petsc4py test
# build tools go into a private venv used only as an install target (pip --user trips over an unreadable system
# egg-info); the system python3 (numpy/scipy) sees them through PYTHONPATH
[ -d $SW/venv ] || python3 -m venv $SW/venv
$SW/venv/bin/python -m pip install --no-index --find-links $PKG/wheels cmake "cython<3.2" "setuptools<75" wheel 2>&1 | tail -1
export PATH=$SW/venv/bin:$PATH PYTHONPATH=$SW/venv/lib/python3.9/site-packages
# petsc4py is built with the venv python: /usr/bin/python3 makes setuptools scan /usr/lib/python3.9/site-packages, whose
# syssentry egg-info is unreadable; the venv has no system site-packages, so numpy (in ~/.local) is added explicitly
export PYTHONPATH=$PYTHONPATH:$HOME/.local/lib/python3.9/site-packages
cmake --version | head -1; cython --version
# compute nodes have gcc but not g++; SW/gxx is the login node's gcc-c++/libstdc++-devel 10.3.1 copied as a relocatable
# tree (same gcc release, lib64 symlinks made absolute), which SuiteSparse needs
CXX=$SW/gxx/usr/bin/g++
printf '#include <vector>\n#include <iostream>\nint main() { std::vector<int> v(3, 7); std::cout << v[0] + v[2] << std::endl; }\n' > cxx_check.cc
$CXX -O2 -fopenmp cxx_check.cc -o cxx_check && [ "$(./cxx_check)" = 14 ] || { echo "C++ compiler check failed"; exit 1; }
echo "C++: $($CXX --version | head -1)"

echo "== KML libraries"; find $KML -name "*.so" | sort
# runtime folders KML's LAPACK needs: libkm (KML noarch) and the BiSheng C++ runtime (libc++, libc++abi)
CXXRT=$(dirname $(find /opt/HPCKit -name "libc++.so.1" | head -1))
RT="-L$KML/noarch -Wl,-rpath,$KML/noarch -L$CXXRT -Wl,-rpath,$CXXRT"
echo "C++ runtime: $CXXRT"
# libklapack_full.so lists libkm/libc++/libflang/libbsmath as NEEDED; SuiteSparse's CMake drops our -Wl,-rpath flags, so
# ld can only resolve them through LD_LIBRARY_PATH (env.sh sets the same path at run time)
export LD_LIBRARY_PATH=$KML/noarch:$CXXRT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
cat > blas_check.c <<'C'
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
void dgemm_(const char*, const char*, const int*, const int*, const int*, const double*, const double*, const int*,
            const double*, const int*, const double*, double*, const int*);
void dpotrf_(const char*, const int*, double*, const int*, int*);
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + 1e-9 * t.tv_nsec; }
int main(void) {
  int n = 256; double one = 1, zero = 0;
  double *a = malloc(8L * n * n), *b = malloc(8L * n * n), *c = malloc(8L * n * n);
  for (int i = 0; i < n * n; i++) { a[i] = (i % 7) * 0.1; b[i] = (i % 5) * 0.2; c[i] = 0; }
  dgemm_("N", "N", &n, &n, &n, &one, a, &n, b, &n, &zero, c, &n);
  double err = 0, ref = 0;
  for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) {
    double t = 0; for (int k = 0; k < n; k++) t += a[i + k * n] * b[k + j * n];
    err += (c[i + j * n] - t) * (c[i + j * n] - t); ref += t * t; }
  for (int i = 0; i < n * n; i++) a[i] = 0;
  for (int i = 0; i < n; i++) a[i + i * n] = 4.0;
  for (int i = 0; i < n - 1; i++) { a[i + 1 + i * n] = 1; a[i + (i + 1) * n] = 1; }
  int info; dpotrf_("L", &n, a, &n, &info);
  int m = 3000; double *x = malloc(8L * m * m), *y = malloc(8L * m * m), *z = malloc(8L * m * m);
  for (long i = 0; i < (long)m * m; i++) { x[i] = 1e-3 * (i % 11); y[i] = 1e-3 * (i % 13); }
  dgemm_("N", "N", &m, &m, &m, &one, x, &m, y, &m, &zero, z, &m);
  double t0 = now(); dgemm_("N", "N", &m, &m, &m, &one, x, &m, y, &m, &zero, z, &m); double dt = now() - t0;
  printf("relerr %.2e dpotrf_info %d gflops %.1f\n", err > 0 ? __builtin_sqrt(err / ref) : 0.0, info, 2.0 * m * m * m / dt / 1e9);
  return 0;
}
C
export OMP_NUM_THREADS=8
best=""; bestg=0
for lib in $(find $KML -name libkblas.so | sort); do
  d=$(dirname $lib)
  if gcc -O2 blas_check.c -o blas_check -L$d -L$KML/sve512 -Wl,-rpath,$d -Wl,-rpath,$KML/sve512 \
       $RT -lklapack_full -lkservice -lkblas -lgomp -lm 2>link.err; then
    out=$(timeout 300 ./blas_check 2>&1) || out="$out FAILED(exit $?)"
  else
    out="LINK FAILED: $(head -3 link.err | tr '\n' ' ')"
  fi
  echo "$d : $out"
  if echo "$out" | grep -q "dpotrf_info 0"; then
    re=$(echo "$out" | awk '{print $2}'); g=$(echo "$out" | awk '{print $6}')
    if awk -v r=$re 'BEGIN{exit !(r < 1e-12)}' && awk -v g=$g -v b=$bestg 'BEGIN{exit !(g > b)}'; then best=$d; bestg=$g; fi
  fi
done
[ -n "$best" ] || { echo "no KML BLAS variant passed"; exit 1; }
echo "== chosen BLAS: $best ($bestg GFLOP/s with 8 threads)"; echo $best > $SW/kblas_dir.txt

echo "== PETSc"
if [ "${STAGE:-all}" = install ]; then cd petsc-3.25.3; else
rm -rf petsc-3.25.3; tar xzf $PKG/petsc-3.25.3.tar.gz; cd petsc-3.25.3
BL="-Wl,-rpath,$best -L$best -Wl,-rpath,$KML/sve512 -L$KML/sve512 $RT -lklapack_full -lkservice -lkblas -lgomp -lm"
./configure --prefix=$SW/petsc --with-cc=gcc --with-cxx=$CXX --with-mpi=0 --with-fc=0 --with-debugging=0 --with-shared-libraries=1 --with-x=0 \
  --with-openmp=1 COPTFLAGS=-O3 CXXOPTFLAGS=-O3 --with-blaslapack-lib="$BL" \
  --download-suitesparse=$PKG/SuiteSparse-v7.12.2.tar.gz --with-cmake-exec=$(command -v cmake) \
  --with-petsc4py=1 --with-python-exec=$SW/venv/bin/python 2>&1 | tail -25
make PETSC_DIR=$PWD PETSC_ARCH=arch-linux-c-opt -j 32 all 2>&1 | tail -5
fi
make PETSC_DIR=$PWD PETSC_ARCH=arch-linux-c-opt install 2>&1 | tail -3

echo "== petsc4py + CHOLMOD test"
export PYTHONPATH=$SW/petsc/lib:$PYTHONPATH
/usr/bin/python3 - <<'PY'
import numpy as np, scipy.sparse as sp, time
from petsc4py import PETSc
n = 200
L1 = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1])
A = (sp.kronsum(L1, L1) + 1e-3 * sp.eye(n * n)).tocsr()
M = PETSc.Mat().createAIJ(size=A.shape, csr=(A.indptr.astype(PETSc.IntType), A.indices.astype(PETSc.IntType), A.data))
M.setOption(PETSc.Mat.Option.SPD, True)
for solver in ('cholmod', 'petsc'):
    k = PETSc.KSP().create(); k.setOperators(M); k.setType('preonly')
    pc = k.getPC(); pc.setType('cholesky'); pc.setFactorSolverType(solver)
    t = time.perf_counter(); k.setUp(); tf = time.perf_counter() - t
    x, b = M.createVecs(); xs = np.random.default_rng(0).standard_normal(n * n); b.setArray(A @ xs)
    k.solve(b, x)
    print(solver, 'factor_s', round(tf, 3), 'relerr', np.linalg.norm(x.getArray() - xs) / np.linalg.norm(xs))
print('petsc4py', PETSc.Sys.getVersion())
PY
echo BUILD_DONE
