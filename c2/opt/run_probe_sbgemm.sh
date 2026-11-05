#!/bin/bash
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=4 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} PYTHONPATH=$H/sw/torch_kml

timeout 300 python3 $H/opt/code/probe_sbgemm.py 2>&1 | grep -v -i warn
echo PROBE_SB_DONE
