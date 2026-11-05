#!/bin/bash
# Why does LD_PRELOAD of KML SME kblas into torch fail? stderr and exit codes kept.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export PYTHONPATH=$H/sw/torch:$H/opt/code OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
ls $B | head -30
t() { echo "== $1"; shift; timeout 300 "$@" 2>&1 | grep -v -i warn | tail -6; echo "exit ${PIPESTATUS[0]}"; }
t "plain python + preload kblas" env LD_PRELOAD=$K/libkblas.so python3 -c "print('ok')"
t "numpy + preload kblas" env LD_PRELOAD=$K/libkblas.so python3 -c "import numpy; print('ok')"
t "torch import + preload kblas" env LD_PRELOAD=$K/libkblas.so python3 -c "import torch; print('ok')"
t "torch mm + preload libomp,kblas" env LD_PRELOAD=$B/libomp.so:$K/libkblas.so python3 $H/opt/code/diag_mm.py kml
t "torch mm + preload kblas, GOMP from torch" env LD_PRELOAD=$K/libkblas.so python3 $H/opt/code/diag_mm.py kml
echo KML_TORCH2_DONE
