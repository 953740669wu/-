#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?requires real two-domain scheduler identity}"
[[ "${1:-}" =~ ^[a-f0-9]{64}$ ]] || exit 2
exec env -i PATH=/usr/bin:/bin HOME=/home/share/dengqingtian USER=dengqingtian LC_ALL=C PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 CCS_JOB_ID="$CCS_JOB_ID" S00_REVIEW_SHA="$1" HBM=0 S07_PY=/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 PYTHONPATH=/home/share/songzhenlong/eitfm/sw/torch_kml LD_LIBRARY_PATH=/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib /usr/bin/python3 -B "$HERE/run_s07_diag_job.py" "$HERE"
