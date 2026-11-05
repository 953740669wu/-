#!/bin/bash
# torch CPU kernel throughput under BLAS core-type / thread / mkldnn settings (one NUMA domain, cpu=38)
H=/home/share/songzhenlong/eitfm; export PYTHONPATH=$H/sw/torch
ls $H/sw/torch/torch.libs/ $H/sw/torch/torch/lib | grep -i -E "blas|gomp|acl|arm|dnnl"
python3 -c "import torch; print(torch.__config__.parallel_info())" | head -12
D="python3 $H/opt/code/diag_blas.py"
OMP_NUM_THREADS=1 $D
OMP_NUM_THREADS=38 $D
for c in NEOVERSEV2 NEOVERSEV1 NEOVERSEN2 ARMV8SVE CORTEXA57; do OMP_NUM_THREADS=38 OPENBLAS_CORETYPE=$c $D; done
OMP_NUM_THREADS=38 MKLDNN=0 $D
OMP_NUM_THREADS=38 ONEDNN_DEFAULT_FPMATH_MODE=BF16 $D
echo DIAG_BLAS_DONE
