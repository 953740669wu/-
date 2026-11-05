#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?requires the independent allocated job}"
exec env -i PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 CCS_JOB_ID="$CCS_JOB_ID" OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 /usr/bin/python3 -B "$HERE/run_s03_r2_ubsan_recovery.py" "$HERE/payload"
