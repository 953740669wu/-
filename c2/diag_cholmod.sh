#!/bin/bash
# Diagnose CHOLMOD "not positive definite" on an SPD test matrix: simplicial (no BLAS) vs supernodal (BLAS), thread count,
# and each KML BLAS variant swapped in through LD_LIBRARY_PATH (PETSc's RUNPATH yields to it).
H=/home/share/songzhenlong/eitfm; source $H/env.sh; KML=/opt/HPCKit/kml-lib
cat > /tmp/eitfm_diag_$$.py <<'PY'
import sys, numpy as np, scipy.sparse as sp
from petsc4py import PETSc
n = 200
L1 = sp.diags([-np.ones(n - 1), 2 * np.ones(n), -np.ones(n - 1)], [-1, 0, 1])
A = (sp.kronsum(L1, L1) + 1e-3 * sp.eye(n * n)).tocsr()
M = PETSc.Mat().createAIJ(size=A.shape, csr=(A.indptr.astype(PETSc.IntType), A.indices.astype(PETSc.IntType), A.data))
M.setOption(PETSc.Mat.Option.SPD, True)
for solver in sys.argv[1].split(','):
    k = PETSc.KSP().create(); k.setOperators(M); k.setType('preonly')
    pc = k.getPC(); pc.setType('cholesky'); pc.setFactorSolverType(solver); k.setFromOptions()
    try:
        k.setUp(); x, b = M.createVecs(); xs = np.random.default_rng(0).standard_normal(n * n); b.setArray(A @ xs)
        k.solve(b, x); print('   ', solver, 'relerr %.2e' % (np.linalg.norm(x.getArray() - xs) / np.linalg.norm(xs)))
    except PETSc.Error as e:
        print('   ', solver, 'FAILED', e.ierr)
PY
run() { echo "== $1"; shift; env "$@" python3 /tmp/eitfm_diag_$$.py cholmod,petsc 2>&1 | grep -v "^CHOLMOD warning" | grep -E "relerr|FAILED"; }
run "supernodal, 8 threads" OMP_NUM_THREADS=8
run "supernodal, 1 thread" OMP_NUM_THREADS=1
run "simplicial, 8 threads" OMP_NUM_THREADS=8 PETSC_OPTIONS="-mat_cholmod_factor simplicial"
for v in locking nolocking multi; do
  run "supernodal, kblas $v, 1 thread" OMP_NUM_THREADS=1 LD_LIBRARY_PATH=$KML/sme/kblas/$v:$LD_LIBRARY_PATH
done
echo "== linked BLAS/LAPACK of libpetsc"; ldd $H/sw/petsc/lib/libpetsc.so | grep -E "kblas|klapack|kservice|libkm|cholmod"
rm -f /tmp/eitfm_diag_$$.py
