#!/bin/bash
# KConv2d correctness + speed vs oneDNN conv, then the 16-belt s4 pieces with KML shim + KConv2d. One domain.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
timeout 1200 python3 $H/opt/code/check_kconv.py 2>&1 | grep -v -i warn
echo KCONV_DONE
