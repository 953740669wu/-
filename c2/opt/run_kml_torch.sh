#!/bin/bash
# torch matmul/attention routed to KML SME BLAS by LD_PRELOAD (sgemm_ interposition), one domain, cpu=38.
H=/home/share/songzhenlong/eitfm; K=/opt/HPCKit/kml-lib/sme/kblas/multi
export PYTHONPATH=$H/sw/torch:$H/opt/code OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38
ldd $K/libkblas.so | grep -v -E "linux-vdso|ld-linux"
nm -D $K/libkblas.so | grep -E " T (sgemm_|sgemv_|cblas_sgemm)$"
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
D="python3 $H/opt/code/diag_mm.py"
echo "== baseline (torch OpenBLAS)"; $D openblas
for P in "$K/libkblas.so" "/opt/HPCKit/bisheng-lib/libomp.so:$K/libkblas.so"; do
  echo "== LD_PRELOAD=$P"; LD_PRELOAD=$P timeout 300 $D kml || echo "FAILED preload $P"
done
echo "== s4 pieces with KML (libomp + kblas)"
LD_PRELOAD=/opt/HPCKit/bisheng-lib/libomp.so:$K/libkblas.so timeout 1500 python3 $H/opt/code/diag_s4.py 16 2>&1 | grep -v -i warn | head -40
echo KML_TORCH_DONE
