#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?native job identity required}"
[[ "${1:-}" =~ ^[a-f0-9]{64}$ ]] || exit 2
exec env -i PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 HBM=0 CCS_JOB_ID="$CCS_JOB_ID" S00_REVIEW_SHA="$1" /usr/bin/python3 -B "$HERE/run_job.py" "$HERE"
