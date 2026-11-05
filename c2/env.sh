# EIT-FM runtime on C2 compute nodes: system python3.9 (numpy/scipy) + our PETSc/petsc4py (CHOLMOD on KML BLAS).
SW=/home/share/songzhenlong/eitfm/sw
export PYTHONPATH=$SW/petsc/lib:$SW/venv/lib/python3.9/site-packages${PYTHONPATH:+:$PYTHONPATH}
export LD_LIBRARY_PATH=/opt/HPCKit/kml-lib/noarch:/opt/HPCKit/bisheng-lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
# KML's LAPACK pulls in BiSheng's libomp while gcc-built PETSc/CHOLMOD use libgomp; two OpenMP runtimes make
# multithreaded CHOLMOD supernodal factorization fail ("not positive definite"). libomp also implements the GOMP ABI,
# so preloading it leaves one runtime (diag_cholmod2.sh: correct at 1/2/8 threads)
export LD_PRELOAD=/opt/HPCKit/bisheng-lib/libomp.so${LD_PRELOAD:+:$LD_PRELOAD}
export SOLVER=cholmod
export OMP_PLACES=cores OMP_PROC_BIND=close
