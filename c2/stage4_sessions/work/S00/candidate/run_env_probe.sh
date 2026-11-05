#!/bin/bash
set -euo pipefail
TASK_ROOT=$(cd -- "$(dirname -- "$0")" && pwd -P)
case "$TASK_ROOT" in
  /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_*) ;;
  *) exit 2 ;;
esac
export PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
unset LD_PRELOAD PYTHONPATH KML_BLAS_LIB
hostname
date -u '+%Y-%m-%dT%H:%M:%SZ'
cat /proc/self/cgroup
/usr/bin/python3 -B "$TASK_ROOT/probe_compute_env.py" "$TASK_ROOT"
