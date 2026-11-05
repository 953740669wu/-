#!/bin/bash
# Operator profiles of the 32-belt pretraining step with KML_LINEAR, fp32 vs bf16 GEMMs (phase B1/C2).
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
p() { env "$@" timeout 2400 python3 $H/opt/code/prof_s4.py 2>&1 | grep -v -i warn; echo "exit ${PIPESTATUS[0]}"; }
p L=32 PART=pre AMP=fp32 KML_LINEAR=1 LINEAR_DTYPE=fp32
p L=32 PART=pre AMP=fp32 KML_LINEAR=1 LINEAR_DTYPE=bf16
echo PROF_S4_DONE
