#!/bin/bash
# Stage 4 CPU benchmark on one NUMA domain (cpu=38, numa-packed): s4_models.py training steps and guided sampling
# under different threads / precision / memory layout / torch.compile. Input frames come from the worker_test
# parts of s0322 (timing only: the step cost does not depend on the values). Writes only under eitfm/opt/s4.
set -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt/s4
mkdir -p $O/cases $O/reports
# torch runtime only: no env.sh (its LD_PRELOAD of BiSheng libomp would clash with torch's bundled libgomp)
export PYTHONPATH=$H/sw/torch:$H/opt/code
hostname; awk '/Cpus_allowed_list/' /proc/self/status; grep -m1 Features /proc/cpuinfo; lscpu | grep -E "Model name|L3|NUMA node0"
CPUS=($(python3 -c "import os; print(' '.join(map(str, sorted(os.sched_getaffinity(0)))))"))
python3 - <<'PY'
import numpy as np, glob, os
H = '/home/share/songzhenlong/eitfm'; O = H + '/opt/s4'
for p in (0, 1):
    out = {}
    for belt in ('16_adjacent', '32_skip4'):
        z = np.load(f'{H}/opt/worker_test/parts/s0322_p{p}_{belt}_c0.npz')
        out['images'] = z['images']
        out[f'{belt}_v_cur'] = z['v_cur']; out[f'{belt}_v_ref'] = z['v_ref'][z['base_of_pair']]; out[f'{belt}_J_img'] = z['J_img']
    os.makedirs(f'{O}/cases/s0322p{p}', exist_ok=True); np.savez(f'{O}/cases/s0322p{p}/frames.npz', **out)
    print('frames', p, {k: v.shape for k, v in out.items()})
PY
python3 -c "import torch; print(torch.__version__, torch.backends.mkldnn.is_available(), torch.backends.cpu.get_cpu_capability())"
# OpenMP threads must be bound: unbound, 38 threads run a 2048^3 matmul at 10 GFLOP/s vs 95 on one core;
# bound (close, cores) they reach 440-510 fp32 / ~1000 bf16 (opt_diag_threads.log)
export OMP_PROC_BIND=close OMP_PLACES=cores
run() {   # run <tag> <threads> <first core> [ENV=..]: one process on cores first..first+threads-1 of the domain
  tag=$1; t=$2; c0=$3; shift 3
  echo "== $tag threads=$t cores ${CPUS[$c0]}+ $*"
  env OMP_NUM_THREADS=$t TIMING_OUT=$tag.json REPS=${REPS:-5} SAMPLING=0 GN=0 "$@"     timeout ${TO:-3600} taskset -c $(echo "${CPUS[@]:$c0:$t}" | tr ' ' ',') python3 $H/opt/code/s4_models.py $O s0322p0,s0322p1 > $O/reports/$tag.log 2>&1     && python3 -c "
import json; r = json.load(open('$O/reports/$tag.json'))
for b in ('16_adjacent', '32_skip4'):
    x = r[b]; print(' ', '$tag', b, {k: round(v, 3) for k, v in x.items()})
if 'gn_noser' in r: print('  gn', r['gn_noser'])" || { echo "  FAILED $tag"; tail -5 $O/reports/$tag.log; }
}
conc() {  # conc <tag> <procs> <threads> [ENV=..]: <procs> concurrent processes side by side in the domain
  tag=$1; np=$2; t=$3; shift 3
  for g in $(seq 0 $((np - 1))); do run ${tag}_g$g $t $((g * t)) "$@" & done; wait
}
# bf16 autocast is not used: one 16-belt enc+dec fwd+bwd takes 415 s in bf16 vs 9.4 s in fp32 (opt_diag_s4b.log).
# GN is not timed here: numpy's own OpenBLAS (pthreads) ignores OMP binding and is slow multithreaded.
run fp32_t38 38 0
run fp32_cl_t38 38 0 CHANNELS_LAST=1
conc fp32_4x9 4 9
conc fp32_2x19 2 19
run fp32_b128_t38 38 0 BATCH=128 REPS=3
PATH=$H/sw/gxx/usr/bin:$PATH CXX=g++ TO=2400 run fp32_compile_t38 38 0 COMPILE=1
run fp32_t38_sampling 38 0 SAMPLING=1 REPS=2
echo BENCH_S4_DONE
