#!/bin/bash
# Second solver stack for the threading problem: OpenBLAS 0.3.32 (gcc, pthreads, LAPACK from C since there is no
# Fortran) and PETSc 3.25.3 + SuiteSparse/CHOLMOD + petsc4py on top of it, in sw/openblas and sw/petsc_ob. With KML,
# CHOLMOD factorization gets slower with every added thread (val.sh, diag_threads.sh); here BLAS threads
# (OPENBLAS_NUM_THREADS) are separate from CHOLMOD's OpenMP loops (OMP_NUM_THREADS) and only gcc's libgomp is loaded.
# The KML stack (build_petsc.sh, sw/petsc, env.sh) is left as is.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; PKG=$H/pkg; SW=$H/sw; OB=$SW/openblas
mkdir -p $SW/build_ob; cd $SW/build_ob
echo "== node"; hostname; awk '/Cpus_allowed_list/' /proc/self/status; lscpu | grep -E "Model name|Flags" | cut -c1-200
export PATH=$SW/venv/bin:$PATH PYTHONPATH=$SW/venv/lib/python3.9/site-packages:$HOME/.local/lib/python3.9/site-packages
CXX=$SW/gxx/usr/bin/g++

if [ "${STAGE:-all}" != petsc ]; then
echo "== OpenBLAS"
rm -rf OpenBLAS-0.3.32; tar xzf $PKG/OpenBLAS-v0.3.32.tar.gz; cd OpenBLAS-0.3.32
# ARMV8SVE kernels are vector-length agnostic (these nodes have 512-bit SVE); NUM_THREADS caps the thread pool
OBFLAGS="TARGET=ARMV8SVE CC=gcc NOFORTRAN=1 C_LAPACK=1 USE_THREAD=1 USE_OPENMP=0 NUM_THREADS=64 NO_STATIC=1"
make $OBFLAGS -j 32 > $H/logs/openblas_make.log 2>&1 || { tail -30 $H/logs/openblas_make.log; exit 1; }
make $OBFLAGS PREFIX=$OB install > $H/logs/openblas_install.log 2>&1 || { tail -30 $H/logs/openblas_install.log; exit 1; }
cd ..
echo "== OpenBLAS check (dgemm accuracy, dpotrf, GFLOP/s by thread count)"
cp $SW/build/blas_check.c . 2>/dev/null || { echo "blas_check.c missing (written by build_petsc.sh)"; exit 1; }
gcc -O2 blas_check.c -o blas_check_ob -L$OB/lib -Wl,-rpath,$OB/lib -lopenblas -lm
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
for t in 1 8 32; do echo "threads $t: $(OPENBLAS_NUM_THREADS=$t taskset -c $(echo "${CPUS[@]:0:$t}" | tr ' ' ',') ./blas_check_ob)"; done
fi

echo "== PETSc on OpenBLAS"
rm -rf petsc-3.25.3; tar xzf $PKG/petsc-3.25.3.tar.gz; cd petsc-3.25.3
./configure --prefix=$SW/petsc_ob --with-cc=gcc --with-cxx=$CXX --with-mpi=0 --with-fc=0 --with-debugging=0 --with-shared-libraries=1 --with-x=0 \
  --with-openmp=1 COPTFLAGS=-O3 CXXOPTFLAGS=-O3 --with-blaslapack-lib="-Wl,-rpath,$OB/lib -L$OB/lib -lopenblas -lm" \
  --download-suitesparse=$PKG/SuiteSparse-v7.12.2.tar.gz --with-cmake-exec=$(command -v cmake) \
  --with-petsc4py=1 --with-python-exec=$SW/venv/bin/python 2>&1 | tail -25
make PETSC_DIR=$PWD PETSC_ARCH=arch-linux-c-opt -j 32 all 2>&1 | tail -5
make PETSC_DIR=$PWD PETSC_ARCH=arch-linux-c-opt install 2>&1 | tail -3

echo "== petsc4py + CHOLMOD test (OMP threads x OpenBLAS threads)"
export PYTHONPATH=$SW/petsc_ob/lib:$PYTHONPATH
cat > /tmp/eitfm_obtest_$$.py <<'PY'
import numpy as np, scipy.sparse as sp, time
from petsc4py import PETSc
n = 300
L1 = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1])
A = (sp.kronsum(L1, L1) + 1e-3 * sp.eye(n * n)).tocsr()
M = PETSc.Mat().createAIJ(size=A.shape, csr=(A.indptr.astype(PETSc.IntType), A.indices.astype(PETSc.IntType), A.data))
M.setOption(PETSc.Mat.Option.SPD, True)
k = PETSc.KSP().create(); k.setOperators(M); k.setType('preonly')
pc = k.getPC(); pc.setType('cholesky'); pc.setFactorSolverType('cholmod')
t = time.perf_counter(); k.setUp(); tf = time.perf_counter() - t
x, b = M.createVecs(); xs = np.random.default_rng(0).standard_normal(n * n); b.setArray(A @ xs); k.solve(b, x)
print('    relerr %.1e factor_s %.3f' % (np.linalg.norm(x.getArray() - xs) / np.linalg.norm(xs), tf))
PY
for c in "1 1" "8 1" "1 8" "8 8"; do set -- $c
  echo "  OMP_NUM_THREADS=$1 OPENBLAS_NUM_THREADS=$2"
  OMP_NUM_THREADS=$1 OPENBLAS_NUM_THREADS=$2 /usr/bin/python3 /tmp/eitfm_obtest_$$.py 2>&1 | grep -v "^CHOLMOD warning"
done
rm -f /tmp/eitfm_obtest_$$.py
echo "== libraries"; ldd $SW/petsc_ob/lib/libpetsc.so | grep -E "openblas|omp|cholmod"
echo BUILD_OB_DONE
