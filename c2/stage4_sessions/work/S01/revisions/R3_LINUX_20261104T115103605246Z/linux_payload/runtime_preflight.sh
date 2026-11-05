#!/bin/bash
# S01 isolated runner. Same tag and model env-assignment interface as the frozen launcher.
set -euo pipefail
H=/home/share/songzhenlong/eitfm
S01_RUN=${S01_RUN:?set an absolute unique S01 run directory}
[[ "$S01_RUN" = /* ]] || { echo 'S01_RUN must be absolute' >&2; exit 1; }
K=/opt/HPCKit/kml-lib/sme/kblas/multi
B=/opt/HPCKit/bisheng-lib
export S01_RUN OMP_PLACES=cores OMP_PROC_BIND=close
export KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$S01_RUN/candidate
export LD_PRELOAD=$S01_RUN/lib/libkml_sgemm_shim.so
export PYTHONDONTWRITEBYTECODE=1 PYTHONFAULTHANDLER=1
export DEVICE=cpu AMP=fp32 KML_LINEAR=1 LINEAR_DTYPE=fp32 OMP_NUM_THREADS=1
exec python3 -B "$S01_RUN/runtime_probe.py"
