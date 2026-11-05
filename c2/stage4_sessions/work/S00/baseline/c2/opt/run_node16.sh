#!/bin/bash
# Phase A1: whole-node throughput. One s4_models.py process per compute NUMA domain (16 x 38 cores), all at once,
# each bound with numactl (cores + local memory: MEMPOL=membind (strict, default) or preferred); ROUNDS repetitions. Each phase (belt x pretrain/decoder)
# starts on all domains together (s4_models SYNC_DIR barrier). Per round: the sum of per-domain frames/s, the
# conservative node rate 16 B / slowest step, and the spread across domains; gate A1 = round-to-round spread <= 5%.
# SKIP_BUSY=1: before each round, cores already running a thread at > 5% CPU (foreign processes) are left out of
# that domain (numactl --physcpubind, OMP_NUM_THREADS reduced to match).
# HBM=1: memory policy d,16+d and LD_PRELOAD hbm_alloc (large torch buffers in the domain's HBM node 16+d).
# NDOM=n: only the first n domains (n = 4 is one die, which already shows the full bandwidth contention).
# argv: tag, then extra env assignments (e.g. KML_LINEAR=1 LINEAR_DTYPE=bf16).
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4; K=/opt/HPCKit/kml-lib/sme/kblas/multi; B=/opt/HPCKit/bisheng-lib
export OMP_PLACES=cores OMP_PROC_BIND=close OMP_NUM_THREADS=38 KML_BLAS_LIB=$K/libkblas.so
export LD_LIBRARY_PATH=$K:/opt/HPCKit/kml-lib:$B${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export PYTHONPATH=$H/sw/torch_kml:$H/opt/code LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so
tag=${1:-node16}; shift; ROUNDS=${ROUNDS:-3}; MEMPOL=${MEMPOL:-membind}
nodes=$(for d in /sys/devices/system/node/node*; do [ -n "$(cat $d/cpulist)" ] && basename $d | tr -d node; done | sort -n |
       head -n ${NDOM:-99})
echo "host $(hostname)  compute domains: $(echo $nodes | wc -w)  ($(echo $nodes))"; numactl -H | grep -E "size|free" | head -40
mkdir -p $O/reports/$tag
for r in $(seq 1 $ROUNDS); do
  t0=$(date +%s); S=$O/reports/$tag/sync_r$r; rm -rf $S; mkdir -p $S
  busy=$([ "${SKIP_BUSY:-0}" = 1 ] && ps -eLo psr,pcpu --no-headers | awk '$2 > 5 {print $1}' | sort -un | tr '\n' ' ')
  [ -n "$busy" ] && echo "round $r busy cores skipped: $busy"
  for d in $nodes; do
    cpus=$(numactl -H | awk -v d=$d '$1 == "node" && $2 == d && $3 == "cpus:" {for (i = 4; i <= NF; i++) print $i}' |
           grep -vxF -f <(echo $busy | tr ' ' '\n' | grep .) | paste -sd,)
    [ -z "$busy" ] && cpus=$(cat /sys/devices/system/node/node$d/cpulist)
    mem=$d; hbm=()
    [ "${HBM:-0}" = 1 ] && { mem=$d,$((16 + d)); hbm=(HBM_NODE=$((16 + d)) HBM_STATS=1 LD_PRELOAD=$H/sw/hbm_alloc/libhbm_alloc.so:$LD_PRELOAD); }
    env SYNC_DIR=$S SYNC_N=$(echo $nodes | wc -w) TIMING_OUT=$tag/r${r}_d$d.json REPS=${REPS:-5} SAMPLING=0 GN=0 "$@" "${hbm[@]}" \
      OMP_NUM_THREADS=$(echo $cpus | tr ',' '\n' | awk -F- '{n += NF == 2 ? $2 - $1 + 1 : 1} END {print n}') \
      timeout 5400 numactl --physcpubind=$cpus --$MEMPOL=$mem python3 $H/opt/code/s4_models.py $O s0322p0,s0322p1 \
      > $O/reports/$tag/r${r}_d$d.log 2>&1 &
  done
  wait; echo "round $r wall $(( $(date +%s) - t0 )) s"; grep -l -E 'Killed|MemoryError|Traceback' $O/reports/$tag/r${r}_d*.log 2>/dev/null | sed 's/^/  failed: /'
done
python3 - "$O/reports/$tag" "$ROUNDS" <<'PY'
import json, sys, glob, os, statistics as st
D, R = sys.argv[1], int(sys.argv[2]); keys = ('pretrain_frames_per_s', 'decoder_frames_per_s'); sums = {}; cons = {}
for r in range(1, R + 1):
    fs = sorted(glob.glob(f'{D}/r{r}_d*.json')); rs = [json.load(open(f)) for f in fs]
    for b in ('16_adjacent', '32_skip4'):
        for k in keys:
            v = [x[b][k] for x in rs if k in x.get(b, {})]
            if not v: continue
            sums.setdefault((b, k), []).append(sum(v)); cons.setdefault((b, k), []).append(len(v) * min(v))
            print(f'round {r} {b:12s} {k:22s} domains {len(v):2d}  node sum {sum(v):8.2f}  per-domain min {min(v):.2f}'
                  f' median {st.median(v):.2f} max {max(v):.2f}  conservative {len(v) * min(v):8.2f}  peak mem max {max(x[b]["peak_mem_GB"] for x in rs):.1f} GB')
print('gate A1 (round-to-round spread of node sum, (max-min)/mean <= 5%):')
for (b, k), v in sums.items():
    sp = (max(v) - min(v)) / st.mean(v); print(f'  {b:12s} {k:22s} sum {[round(x, 2) for x in v]}  spread {sp:.1%}  {"PASS" if sp <= .05 else "FAIL"}'
          f'   conservative {[round(x, 2) for x in cons[(b, k)]]}')
PY
echo NODE16_DONE
