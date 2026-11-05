#!/bin/bash
# Invoke inside a separately authorized S00 allocation. This file never submits jobs.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
TASK=$(cd -- "$HERE/.." && pwd -P)
: "${CCS_JOB_ID:?requires an allocated compute job}"
: "${S06_CPUSET:?S00 must choose 36 allocated CPUs in one domain}"
: "${S06_MEMNODE:?S00 must verify the corresponding DDR NUMA node}"
source "$TASK/baseline/cluster_runtime_reference.env"
export OMP_NUM_THREADS=36 OPENBLAS_NUM_THREADS=36 MKL_NUM_THREADS=36
export CXX="${S06_CXX:-/usr/bin/g++}"
test -x "$CXX"
test -x "$C2_PYTHON"
test -r "$LD_PRELOAD"
RUN="$TASK/evidence/c2_${CCS_JOB_ID}_$(date -u +%Y%m%dT%H%M%SZ)"
# Preflight only reads process affinity; no model or HBM allocation.
numactl --physcpubind="$S06_CPUSET" --membind="$S06_MEMNODE" \
  "$C2_PYTHON" -I -S -B -c \
  'import os; n=len(os.sched_getaffinity(0)); print("allocated probe CPUs:", n); assert n == 36, n'
exec numactl --physcpubind="$S06_CPUSET" --membind="$S06_MEMNODE" \
  "$C2_PYTHON" -I -S -B "$HERE/run_probe.py" \
  --python "$C2_PYTHON" --out "$RUN" \
  --package-root /home/share/songzhenlong/eitfm/sw/torch_kml \
  --package-root "$S00_RUNTIME_ROOT/venv/lib64/python3.9/site-packages" \
  --package-root "$S00_RUNTIME_ROOT/venv/lib/python3.9/site-packages"
