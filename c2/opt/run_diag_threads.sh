#!/bin/bash
# Why OpenMP threads scale negatively on C2: cgroup limits, OpenMP bind/wait policy, threads vs processes.
H=/home/share/songzhenlong/eitfm; export PYTHONPATH=$H/sw/torch; D="python3 $H/opt/code/diag_mm.py"
awk '/Cpus_allowed_list|Mems_allowed_list/' /proc/self/status; nproc
cat /proc/self/cgroup; for f in cpu.max cpu.cfs_quota_us cpu.cfs_period_us cpuset.cpus cpuset.cpus.effective; do
  for d in /sys/fs/cgroup /sys/fs/cgroup/cpu,cpuacct /sys/fs/cgroup/cpu /sys/fs/cgroup/cpuset; do
    g=$(grep -E ":(cpu|cpuset|cpu,cpuacct)?:|^0::" /proc/self/cgroup | head -1 | cut -d: -f3)
    [ -f $d$g/$f ] && echo "$d$g/$f: $(cat $d$g/$f)"; [ -f $d/$f ] && echo "$d/$f: $(cat $d/$f)"; done; done 2>/dev/null | sort -u
lscpu | grep -E "Thread|Core|Socket|NUMA node\(s\)|MHz"
for t in 1 2 4 8 16 38; do OMP_NUM_THREADS=$t $D default; done
for t in 8 38; do
  OMP_NUM_THREADS=$t OMP_PROC_BIND=close OMP_PLACES=cores $D bind_close
  OMP_NUM_THREADS=$t OMP_WAIT_POLICY=PASSIVE $D wait_passive
  OMP_NUM_THREADS=$t GOMP_SPINCOUNT=0 OMP_PROC_BIND=close OMP_PLACES=cores $D spin0_bind
done
echo "== 38 single-thread processes at once, one per core"
for c in $(seq 0 37); do OMP_NUM_THREADS=1 taskset -c $c $D proc_core$c & done; wait
echo "== 4 processes x 9 threads (bound)"
for g in 0 1 2 3; do OMP_NUM_THREADS=9 OMP_PROC_BIND=close OMP_PLACES=cores taskset -c $((g*9))-$((g*9+8)) $D proc4x9_g$g & done; wait
echo DIAG_THREADS_DONE
