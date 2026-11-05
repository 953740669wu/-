#!/bin/bash
# One OpenMP runtime: a copy of sw/torch (sw/torch_kml) whose bundled libgomp is replaced by BiSheng libomp
# (GOMP ABI), then KML SME kblas interposed for sgemm_. Also ctypes-after-torch with passive waits on stock torch.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
T=$H/sw/torch_kml
if [ ! -d $T ]; then cp -a $H/sw/torch $T; G=$(ls $T/torch.libs/libgomp-*.so*); mv $G $G.orig; ln -s $B/libomp.so $G; fi
ls -la $T/torch.libs | grep gomp
t() { echo "== $1"; shift; timeout 400 "$@" 2>&1 | grep -v -i warn | tail -12; echo "exit ${PIPESTATUS[0]}"; }
t "torch_kml, libomp only" env PYTHONPATH=$T python3 $H/opt/code/diag_mm.py libomp_only
t "torch_kml + preload kblas" env PYTHONPATH=$T LD_PRELOAD=$K/libkblas.so python3 $H/opt/code/diag_mm.py libomp_kblas
t "stock torch, ctypes kml, passive" env PYTHONPATH=$H/sw/torch OMP_WAIT_POLICY=PASSIVE KMP_BLOCKTIME=0 python3 $H/opt/code/kml_after_torch.py 2048 4096
t "torch_kml + preload kblas: s4 pieces fp32" env PYTHONPATH=$T:$H/opt/code NOBF16=1 LD_PRELOAD=$K/libkblas.so python3 $H/opt/code/diag_s4.py 16
echo KML_TORCH5_DONE
