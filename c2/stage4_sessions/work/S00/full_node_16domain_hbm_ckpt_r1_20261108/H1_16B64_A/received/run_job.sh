#!/bin/bash
set -euo pipefail
ulimit -c 0
ROOT=$(cd -- "$(dirname -- "$0")" && pwd -P)
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{64}$ ]]
: "${CCS_JOB_ID:?native job ID required}"
job_env=(PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1)
job_env+=(PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 CCS_JOB_ID="$CCS_JOB_ID")
exec env -i "${job_env[@]}" /usr/bin/python3 -B "$ROOT/launch.py" "$1"
