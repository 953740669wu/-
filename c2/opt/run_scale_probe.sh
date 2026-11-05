#!/bin/bash
# Concurrency scaling, whole node: the 32-belt pretrain step (BATCH=32, strict membind, KML fp32 linear) on N = 1, 4, 8, 16
# domains at once (domains 0..N-1; at N=16 all). Separates per-domain contention (memory bandwidth, reclaim, power
# capping) from a single bad domain. Per level: per-domain frames/s, /proc/vmstat reclaim/compaction/NUMA deltas, CPU
# frequency sampled mid-run on domains 0 and 12, per-node free memory mid-run. Before the runs: busy threads on
# domain 12's cores.
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
tag=${1:-scale_probe}; R=$O/reports/$tag; mkdir -p $R
echo "host $(hostname)"
c12=$(cat /sys/devices/system/node/node12/cpulist); echo "domain 12 cpus $c12; busy threads there (pcpu > 1):"
ps -eLo psr,pcpu,user,comm --no-headers | awk -v l="$c12" 'BEGIN {split(l, a, "-")} $1 >= a[1] && $1 <= a[2] && $2 > 1' | head
grep -m3 -E "HugePages_Total|MemFree" /sys/devices/system/node/node12/meminfo
VM="pgscan_direct|pgsteal_direct|pgscan_kswapd|compact_stall|numa_miss|numa_foreign|pgmigrate_success|thp_fault_fallback"
vm() { grep -E "^($VM) " /proc/vmstat; }
freq() { for c in $(cut -d- -f1 /sys/devices/system/node/node$1/cpulist); do
  f=/sys/devices/system/cpu/cpu$c/cpufreq/scaling_cur_freq; [ -r $f ] && echo "dom$1 cpu$c $(( $(cat $f) / 1000 )) MHz"; done; }
for N in 1 4 8 16; do
  S=$R/sync_n$N; rm -rf $S; mkdir -p $S; vm > $R/vm0_n$N; t0=$(date +%s)
  for d in $(seq 0 $((N - 1))); do
    env BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32 BELTS=32_skip4 PARTS=pre SYNC_DIR=$S SYNC_N=$N \
      TIMING_OUT=$tag/n${N}_d$d.json REPS=3 SAMPLING=0 GN=0 \
      timeout 3600 numactl --cpunodebind=$d --membind=$d python3 $H/opt/code/s4_models.py $O s0322p0,s0322p1 \
      > $R/n${N}_d$d.log 2>&1 &
  done
  sleep 120; echo "N=$N mid-run:"; freq 0; [ $N = 16 ] && freq 12
  numactl -H | awk '/free:/ && $2 < 16 {printf "  node%s free %s MB\n", $2, $4}' | head -16
  wait; vm > $R/vm1_n$N; echo "N=$N wall $(( $(date +%s) - t0 )) s"
  join <(sort $R/vm0_n$N) <(sort $R/vm1_n$N) | awk '{printf "  %s +%d\n", $1, $3 - $2}'
  python3 -c "
import json, glob, re
v = {int(re.search(r'_d(\d+)', f).group(1)): json.load(open(f))['32_skip4']['pretrain_frames_per_s'] for f in glob.glob('$R/n${N}_d*.json')}
print('  N=$N per-domain pretrain frames/s', {d: round(v[d], 2) for d in sorted(v)}, ' sum', round(sum(v.values()), 2))"
done
echo SCALE_PROBE_DONE
