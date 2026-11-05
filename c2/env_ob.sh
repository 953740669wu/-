SW=/home/share/songzhenlong/eitfm/sw
# OpenBLAS stack (build_openblas.sh): only gcc's libgomp is loaded, so no libomp preload and no KML/BiSheng libraries.
# BLAS threads come from OPENBLAS_NUM_THREADS, CHOLMOD's own loops from OMP_NUM_THREADS.
export PYTHONPATH=$SW/petsc_ob/lib:$SW/venv/lib/python3.9/site-packages${PYTHONPATH:+:$PYTHONPATH}
export SOLVER=cholmod
export OMP_PLACES=cores OMP_PROC_BIND=close
