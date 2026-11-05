#!/bin/bash
# KML SME sgemm called through ctypes inside torch, with ONE OpenMP runtime (sw/torch_kml: torch's libgomp -> libomp).
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
t() { echo "== $1"; shift; timeout 400 "$@" 2>&1 | grep -v -i warn | tail -12; echo "exit ${PIPESTATUS[0]}"; }
t "torch_kml + ctypes kml" env PYTHONPATH=$H/sw/torch_kml python3 $H/opt/code/kml_after_torch.py 1024 2048 4096
t "torch_kml + ctypes kml, OMP_PROC_BIND=false" env OMP_PROC_BIND=false PYTHONPATH=$H/sw/torch_kml python3 $H/opt/code/kml_after_torch.py 2048 4096
echo KML_TORCH6_DONE
