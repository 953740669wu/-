#!/bin/bash
# Phase B2/C1 GEMM benchmark on one domain (sme kblas multi; torch_kml so torch and KML share libomp).
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml
nm -D $K/libkblas.so | grep -i -E " T .*(sbgemm|shgemm|bf16|bfloat)" | head; timeout 2400 python3 $H/opt/code/bench_gemm.py 3 2>&1 | grep -v -i warn; echo "exit ${PIPESTATUS[0]}"
echo BENCH_GEMM_DONE
