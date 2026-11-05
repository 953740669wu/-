#!/bin/bash
# CHOLMOD supernodal fails only multithreaded: check each KML BLAS variant's OpenMP runtime and test it at 8 threads,
# with and without CHOLMOD's own OpenMP loops (CHOLMOD_OMP_NUM_THREADS is not read by CHOLMOD; PETSc options cannot set
# Common->nthreads_max, so OMP_NUM_THREADS drives both CHOLMOD and KML).
H=/home/share/songzhenlong/eitfm; source $H/env.sh; KML=/opt/HPCKit/kml-lib
for v in locking nolocking multi; do echo "== $v deps"; ldd $KML/sme/kblas/$v/libkblas.so | grep -i -E "omp|pthread|kservice"; done
echo "== libcholmod deps"; ldd $H/sw/petsc/lib/libcholmod.so.5 | grep -i -E "omp|blas|lapack"
cat > /tmp/eitfm_diag2_$$.py <<'PY'
import numpy as np, scipy.sparse as sp, time
from petsc4py import PETSc
fails = 0
for trial, n in enumerate((200, 300)):
    L1 = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1])
    A = (sp.kronsum(L1, L1) + 1e-3 * sp.eye(n * n)).tocsr()
    M = PETSc.Mat().createAIJ(size=A.shape, csr=(A.indptr.astype(PETSc.IntType), A.indices.astype(PETSc.IntType), A.data))
    M.setOption(PETSc.Mat.Option.SPD, True)
    for rep in range(3):
        k = PETSc.KSP().create(); k.setOperators(M); k.setType('preonly')
        pc = k.getPC(); pc.setType('cholesky'); pc.setFactorSolverType('cholmod')
        try:
            t = time.perf_counter(); k.setUp(); tf = time.perf_counter() - t
            x, b = M.createVecs(); xs = np.random.default_rng(rep).standard_normal(n * n); b.setArray(A @ xs); k.solve(b, x)
            e = np.linalg.norm(x.getArray() - xs) / np.linalg.norm(xs); fails += e > 1e-10
            print('    n=%d rep %d relerr %.1e factor_s %.3f' % (n * n, rep, e, tf))
        except PETSc.Error as err:
            fails += 1; print('    n=%d rep %d FAILED %d' % (n * n, rep, err.ierr))
print('    fails', fails)
PY
echo "== bisheng libgomp"; ls -l /opt/HPCKit/bisheng-lib/libgomp.so /opt/HPCKit/bisheng-lib/libomp.so
# one OpenMP runtime: LLVM libomp also implements the GOMP_* ABI, so preloading it makes gcc-built CHOLMOD/PETSc use it
for case in "1 -" "2 libomp" "8 libomp" "8 libomp+multi"; do set -- $case; t=$1; pre=
  echo "== $t threads, preload $2"
  case $2 in libomp*) pre=/opt/HPCKit/bisheng-lib/libomp.so;; esac
  lp=$LD_LIBRARY_PATH; [ "$2" = libomp+multi ] && lp=$KML/sme/kblas/multi:$lp
  OMP_NUM_THREADS=$t LD_PRELOAD=$pre LD_LIBRARY_PATH=$lp python3 /tmp/eitfm_diag2_$$.py 2>&1 | grep -v "^CHOLMOD warning"
done
rm -f /tmp/eitfm_diag2_$$.py
