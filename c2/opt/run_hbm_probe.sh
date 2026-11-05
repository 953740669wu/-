#!/bin/bash
# HBM feasibility and bandwidth (hbm_probe.py): the job's hugetlb cgroup limit, then triad GB/s from DDR and from the
# domain's HBM node with N = 1, 4 (one die), 16 domains running at once. hbm mode binds the process to DDR d and HBM
# 16+d: hugetlb mmap reserves pages from the task mempolicy's nodes, and DDR nodes hold no hugepages (ENOMEM otherwise).
H=/home/share/songzhenlong/eitfm; R=$H/opt/s4/reports/hbm_probe; mkdir -p $R
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 PYTHONPATH=$H/sw/torch_kml
echo "host $(hostname)"
cg=$(awk -F: '$2 ~ /hugetlb/ {print $3}' /proc/self/cgroup); echo "hugetlb cgroup $cg"
for f in /sys/fs/cgroup/hugetlb$cg/hugetlb.2MB.{limit_in_bytes,usage_in_bytes}; do [ -r $f ] && echo "  $(basename $f) $(cat $f)"; done
for mode in ${MODES:-ddr hbm}; do
  for N in 1 4 16; do
    S=$R/sync_${mode}_$N; rm -rf $S; mkdir -p $S
    for d in $(seq 0 $((N - 1))); do
      SYNC_DIR=$S SYNC_N=$N numactl --cpunodebind=$d --membind=$d$([ $mode = hbm ] && echo ,$((16 + d))) python3 $H/opt/hbm_probe.py $mode $d 20 \
        > $R/${mode}_n${N}_d$d.out 2>&1 &
    done
    wait
    python3 -c "
import json, glob
r = []
for f in sorted(glob.glob('$R/${mode}_n${N}_d*.out')):
    try: r.append(json.loads(open(f).read().strip().splitlines()[-1]))
    except Exception: print('  FAILED', f, open(f).read()[-300:])
if r: print('$mode N=$N per-domain GB/s', [x['GBps'] for x in r], ' sum', round(sum(x['GBps'] for x in r), 1),
            ' hbm free pages after alloc', r[0]['hbm_hugepages_free_after_alloc'])"
  done
done
echo HBM_PROBE_DONE
