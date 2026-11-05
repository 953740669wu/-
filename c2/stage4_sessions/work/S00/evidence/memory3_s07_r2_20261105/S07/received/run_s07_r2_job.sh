#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?requires real two-domain scheduler identity}"
source /etc/profile.d/donaukit_scheduler.sh
command -v djob > "$HERE/djob_cli_path.txt"
printf '%q ' timeout --signal=TERM --kill-after=1s 10 djob -J -l "$CCS_JOB_ID" > "$HERE/scheduler_query_command.txt"
printf '\n' >> "$HERE/scheduler_query_command.txt"
set +e
timeout --signal=TERM --kill-after=1s 10 djob -J -l "$CCS_JOB_ID" > "$HERE/scheduler_allocation.json" 2> "$HERE/scheduler_query_error.txt"
CODE=$?
set -e
echo "$CODE" > "$HERE/scheduler_query_exit.txt"
[[ "$CODE" == 0 ]] || exit "$CODE"
exec env -i PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 CCS_JOB_ID="$CCS_JOB_ID" HBM=0 S07_PY=/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 PYTHONPATH=/home/share/songzhenlong/eitfm/sw/torch_kml LD_LIBRARY_PATH=/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib /usr/bin/python3 -B "$HERE/run_s07_r2_job.py" "$HERE"
