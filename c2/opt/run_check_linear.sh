#!/bin/bash
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
grep -n -E "^linear = |proj = linear\(|= linear\(" $H/sw/torch_kml/torch/nn/functional.py | head -5
for c in "L=16 B=16" "L=16 B=64" "L=32 B=64"; do env $c timeout 1800 python3 $H/opt/code/check_linear.py 2>&1 | grep -v -i warn; done
echo CHECK_LINEAR_DONE
