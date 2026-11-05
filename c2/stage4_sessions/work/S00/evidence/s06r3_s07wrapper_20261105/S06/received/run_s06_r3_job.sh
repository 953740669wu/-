#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?requires current allocated scheduler identity}"
exec env -i PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 CCS_JOB_ID="$CCS_JOB_ID" HBM=0 /usr/bin/python3 -B "$HERE/run_s06_r3_job.py" "$HERE"
