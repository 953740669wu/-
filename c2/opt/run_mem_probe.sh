#!/bin/bash
# Memory residency, one domain: per-node meminfo and zone_reclaim_mode, then the 32-belt steps (pretrain + decoder)
# at B64, B32 and B64 with per-layer activation checkpointing (CKPT=1), each strictly bound (numactl --membind) to the
# allocated domain: frames/s and peak RSS.
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
echo "host $(hostname)  zone_reclaim_mode $(cat /proc/sys/vm/zone_reclaim_mode)  $(numactl --show | grep -E 'nodebind|membind' | tr '\n' ' ')"
meminfo() {
  for d in /sys/devices/system/node/node*; do
    awk -v n=$(basename $d) '/MemTotal|MemFree|FilePages|AnonPages|SUnreclaim|Shmem:|HugePages_Total/ {v[$3]=int($4/1024)}
      END {printf "%-7s total %6d free %6d file %6d anon %6d shmem %6d slab_unrecl %6d MB  hugepages %d\n", n, v["MemTotal:"],
           v["MemFree:"], v["FilePages:"], v["AnonPages:"], v["Shmem:"], v["SUnreclaim:"], v["HugePages_Total:"]}' $d/meminfo
  done | sort -V
}
meminfo
dom=$(numactl --show | awk '/^cpubind/ {print $2}')
mkdir -p $O/reports/mem_probe
for v in "B64:BATCH=64" "B32:BATCH=32" "B64ckpt:BATCH=64 CKPT=1"; do
  tag=${v%%:*}
  env ${v#*:} KML_LINEAR=1 LINEAR_DTYPE=fp32 BELTS=32_skip4 TIMING_OUT=mem_probe/$tag.json REPS=3 SAMPLING=0 GN=0 \
    timeout 3600 numactl --cpunodebind=$dom --membind=$dom python3 $H/opt/code/s4_models.py $O s0322p0,s0322p1 \
    > $O/reports/mem_probe/$tag.log 2>&1
  python3 -c "
import json; r = json.load(open('$O/reports/mem_probe/$tag.json'))['32_skip4']
print('$tag', {k: round(v, 3) for k, v in r.items()})" || tail -5 $O/reports/mem_probe/$tag.log
done
echo "after runs:"; meminfo | grep -E "^node$dom "
echo MEM_PROBE_DONE
