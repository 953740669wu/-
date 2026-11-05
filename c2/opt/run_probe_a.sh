#!/bin/bash
# Phase A2/C1/D1 probe: CPU clock under load, KML bf16 GEMM API, DevKit and BiSheng compiler locations.
echo "== cpufreq"; for f in scaling_governor scaling_cur_freq cpuinfo_max_freq scaling_max_freq cpuinfo_min_freq scaling_available_frequencies; do
  echo "$f: $(cat /sys/devices/system/cpu/cpu0/cpufreq/$f 2>&1)"; done
ls /sys/devices/system/cpu/cpu0/cpufreq/ 2>&1 | tr '\n' ' '; echo
( timeout 8 python3 -c "while True: pass" & ); sleep 3; echo "under load cpu0..3: $(cat /sys/devices/system/cpu/cpu{0,1,2,3}/cpufreq/scaling_cur_freq 2>&1 | tr '\n' ' ')"
grep -m1 -i "bogomips\|MHz" /proc/cpuinfo; lscpu | grep -i mhz
echo "== kblas.h bf16"; Hd=$(find /opt/HPCKit -name kblas.h 2>/dev/null | head -3); echo "$Hd"
for h in $Hd; do grep -n -i -E "bgemm|bfloat|bf16|typedef.*16" $h | head -30; done
echo "== compilers / devkit"; ls /opt/HPCKit; find /opt -maxdepth 4 -type f \( -name clang -o -name "clang++" -o -name devkit -o -name "kupl.h" \) 2>/dev/null | head
ls /opt | head -30; which clang devkit 2>&1 | head -3
echo "== modules"; ls /opt/HPCKit/*/ 2>/dev/null | head -40
echo PROBE_A_DONE
