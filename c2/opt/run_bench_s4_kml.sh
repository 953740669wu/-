#!/bin/bash
# s4_models.py training steps + guided sampling with torch's sgemm_ on KML SME kblas (lazy shim, one OpenMP runtime).
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
tag=${1:-kml_t38}; shift
env TIMING_OUT=$tag.json REPS=${REPS:-5} SAMPLING=${SAMPLING:-1} GN=0 "$@" timeout 7200 python3 $H/opt/code/s4_models.py $O s0322p0,s0322p1 > $O/reports/$tag.log 2>&1
python3 -c "
import json; r = json.load(open('$O/reports/$tag.json'))
for b in ('16_adjacent', '32_skip4'): print(' ', '$tag', b, {k: round(v, 3) for k, v in r[b].items()})" || tail -5 $O/reports/$tag.log
echo BENCH_KML_DONE
