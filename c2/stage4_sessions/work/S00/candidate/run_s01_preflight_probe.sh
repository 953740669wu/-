#!/bin/bash
set -euo pipefail
TASK_ROOT=$(cd -- "$(dirname -- "$0")" && pwd -P)
case "$TASK_ROOT" in
  /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_*_R4) ;;
  *) exit 2 ;;
esac
export S00_PYTHON="$TASK_ROOT/venv/bin/python3" S00_RUNTIME_LIMIT_S=120
unset S00_NUMPY_PATH
bash "$TASK_ROOT/run_env_probe.sh"
export PATH="$TASK_ROOT/venv/bin:/usr/bin:/bin"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export S01_RUN="$TASK_ROOT/S01_payload"
export S01_JOB_ID=${CCS_JOB_ID:?scheduler job ID required}
export S01_COMPUTE_HOST=$(hostname)
exec bash "$S01_RUN/runtime_preflight.sh"
