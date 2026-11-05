#!/bin/bash
# hbm_alloc after the SIGBUS fix: rebuild, then on the allocated domain a 3800 MB arena and a 9000 MB request (must be
# capped to the node's free hugepages, not crash); 60 x 64 MB tensors (3.75 GB, so the 9000 case also spills to DDR).
H=/home/share/songzhenlong/eitfm
gcc -O2 -shared -fPIC -o $H/sw/hbm_alloc/libhbm_alloc.so $H/opt/hbm_alloc.c -lpthread || exit 1
d=$(numactl --show | awk '/^cpubind/ {print $2}'); n=$((16 + d))
echo "host $(hostname) domain $d hbm node $n free $(cat /sys/devices/system/node/node$n/hugepages/hugepages-2048kB/free_hugepages)"
for mb in 3800 9000; do
  HBM_MB=$mb HBM_NODE=$n HBM_STATS=1 LD_PRELOAD=$H/sw/hbm_alloc/libhbm_alloc.so PYTHONPATH=$H/sw/torch_kml OMP_NUM_THREADS=38 \
    numactl --cpunodebind=$d --membind=$d,$n python3 -c "
import torch
xs = [torch.ones(1 << 24) * i for i in range(60)]
print('HBM_MB=$mb ok', all(float(x[-1]) == i for i, x in enumerate(xs)),
      'node $n free hugepages while held', open('/sys/devices/system/node/node$n/meminfo').read().split('HugePages_Free:')[1].split()[0])"
done
echo HBM_FIX_DONE
