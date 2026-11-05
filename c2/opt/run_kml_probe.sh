#!/bin/bash
# Can KML BLAS (SVE/SME per the C2 docs) beat torch's bundled OpenBLAS for fp32 GEMM? One domain, cpu=38.
H=/home/share/songzhenlong/eitfm
cat /proc/sys/abi/sve_default_vector_length /proc/sys/abi/sme_default_vector_length 2>&1
ls /opt/HPCKit; ls -d /opt/HPCKit/kml-lib/* 2>&1 | head -20
find /opt/HPCKit -name "libkblas.so*" 2>/dev/null
find /opt/HPCKit -name "libkml_rt*" -o -name "libkblas*.so" 2>/dev/null | head -3
nm -D $(find /opt/HPCKit -name "libkblas.so" | head -1) 2>/dev/null | grep -i -E " T .*(sbgemm|bfgemm|bgemm|hgemm|sgemm_)" | head
echo "== torch openblas core"
OPENBLAS_VERBOSE=2 PYTHONPATH=$H/sw/torch OMP_NUM_THREADS=1 python3 -c "import torch; torch.ones(4,4)@torch.ones(4,4)" 2>&1 | head -3
export OMP_PLACES=cores OMP_PROC_BIND=close
for L in $(find /opt/HPCKit -name "libkblas.so" 2>/dev/null); do
  for t in 1 38; do OMP_NUM_THREADS=$t LD_LIBRARY_PATH=$(dirname $L):/opt/HPCKit/bisheng-lib:$LD_LIBRARY_PATH timeout 300 python3 $H/opt/code/sgemm_kml.py $L 2048 || echo "FAILED $L t=$t"; done
  OMP_NUM_THREADS=38 LD_LIBRARY_PATH=$(dirname $L):/opt/HPCKit/bisheng-lib:$LD_LIBRARY_PATH timeout 300 python3 $H/opt/code/sgemm_kml.py $L 4096 || true
done
TL=$(ls $H/sw/torch/torch.libs/libopenblasp*.so)
for t in 1 38; do OMP_NUM_THREADS=$t python3 $H/opt/code/sgemm_kml.py $TL 2048; done
echo KML_PROBE_DONE
