#!/bin/bash
# torch (sw/torch_kml, one OpenMP runtime) with sgemm_ forwarded to KML SME kblas by a lazy LD_PRELOAD shim.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
mkdir -p $H/sw/kml_shim; gcc -O2 -shared -fPIC -o $H/sw/kml_shim/libkml_sgemm_shim.so $H/opt/code/kml_sgemm_shim.c -ldl -lpthread || exit 1
S=$H/sw/kml_shim/libkml_sgemm_shim.so
t() { echo "== $1"; shift; timeout 1200 "$@" 2>&1 | grep -v -i warn | tail -40; echo "exit ${PIPESTATUS[0]}"; }
t "matmul, shim" env PYTHONPATH=$H/sw/torch_kml KML_SHIM_VERBOSE=1 LD_PRELOAD=$S python3 $H/opt/code/diag_mm.py kml_shim
t "s4 pieces, stock torch (reference)" env PYTHONPATH=$H/sw/torch:$H/opt/code NOBF16=1 python3 $H/opt/code/diag_s4.py 16
t "s4 pieces, shim, mkldnn on" env PYTHONPATH=$H/sw/torch_kml:$H/opt/code NOBF16=1 LD_PRELOAD=$S python3 $H/opt/code/diag_s4.py 16
t "s4 pieces, shim, mkldnn off" env PYTHONPATH=$H/sw/torch_kml:$H/opt/code NOBF16=1 MKLDNN=0 LD_PRELOAD=$S python3 $H/opt/code/diag_s4.py 16
echo KML_SHIM_DONE
