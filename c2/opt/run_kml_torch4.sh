#!/bin/bash
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export PYTHONPATH=$H/sw/torch OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
echo "== native stack of the preload hang"
LD_PRELOAD=$K/libkblas.so python3 -c "import torch" & P=$!; sleep 25
gdb -p $P -batch -ex "thread apply all bt 14" 2>&1 | grep -E "^#|^Thread" | head -60; kill -9 $P 2>/dev/null; wait $P 2>/dev/null
echo "== KML loaded after torch (ctypes, no preload)"
timeout 600 python3 $H/opt/code/kml_after_torch.py 1024 2048 4096 2>&1 | tail -15; echo "exit ${PIPESTATUS[0]}"
echo KML_TORCH4_DONE
