#!/bin/bash
# Where does `import torch` hang when KML SME kblas is preloaded? Python + native stacks.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export PYTHONPATH=$H/sw/torch OMP_PLACES=cores OMP_PROC_BIND=close
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
which gdb eu-stack pstack 2>&1 | grep -v "no "
for nt in 1 38; do
  echo "== OMP_NUM_THREADS=$nt"
  OMP_NUM_THREADS=$nt LD_PRELOAD=$K/libkblas.so timeout 90 python3 -X faulthandler -c "
import faulthandler, sys; faulthandler.dump_traceback_later(40, exit=True)
import torch; print('imported', torch.__version__); a = torch.randn(512, 512); print((a @ a).sum().item() != 0)" 2>&1 | grep -v -E "^\s*$" | head -30
  echo "exit ${PIPESTATUS[0]}"
done
echo "== LD_DEBUG last libs"
OMP_NUM_THREADS=1 LD_PRELOAD=$K/libkblas.so LD_DEBUG=files timeout 40 python3 -c "import torch" 2>&1 | grep -E "file=" | tail -8
echo KML_TORCH3_DONE
