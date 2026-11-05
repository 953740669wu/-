#!/bin/bash
# HBM allocator: build sw/hbm_alloc/libhbm_alloc.so, a correctness/placement check on domain 0, then one die
# (NDOM=4, domains 0-3 at once) A/B: the s4 steps (both belts, pretrain + decoder, B32, fp32 KLinear) with and
# without HBM=1. Whole-node job (the other 12 domains idle).
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4
mkdir -p $H/sw/hbm_alloc && gcc -O2 -shared -fPIC -o $H/sw/hbm_alloc/libhbm_alloc.so $H/opt/hbm_alloc.c -lpthread || exit 1
echo "host $(hostname); HBM node 16 free hugepages before: $(awk '/HugePages_Free/ {print $4}' /sys/devices/system/node/node16/meminfo)"
HBM_NODE=16 HBM_STATS=1 LD_PRELOAD=$H/sw/hbm_alloc/libhbm_alloc.so PYTHONPATH=$H/sw/torch_kml OMP_NUM_THREADS=38 \
  numactl --cpunodebind=0 --membind=0,16 python3 -c "
import torch
torch.manual_seed(0)
a, b = torch.randn(4096, 4096), torch.randn(4096, 4096)
c = a @ b; ref = (a.double() @ b.double()).float()
print('matmul max rel err', ((c - ref).abs().max() / ref.abs().max()).item())
xs = [torch.ones(1 << 20) * i for i in range(200)]; del xs[::2]; ys = [torch.ones(1 << 20) * i for i in range(100)]
print('reuse check', all(float(y[0]) == i for i, y in enumerate(ys)), all(float(x[-1]) == 2 * i + 1 for i, x in enumerate(xs)))
print('node16 free hugepages while held', open('/sys/devices/system/node/node16/meminfo').read().split('HugePages_Free:')[1].split()[0])
" || exit 1
cp $H/opt/run_node16_new.sh /tmp/run_node16_$$.sh
common="NDOM=4 ROUNDS=1 REPS=3"
env $common bash /tmp/run_node16_$$.sh die4_b32_ddr BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32 | grep -E "^round|failed"
env $common HBM=1 bash /tmp/run_node16_$$.sh die4_b32_hbm BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32 | grep -E "^round|failed"
grep -h "hbm_alloc:" $O/reports/die4_b32_hbm/r1_d*.log | sort | uniq -c | head -12
echo HBM_AB_DONE
