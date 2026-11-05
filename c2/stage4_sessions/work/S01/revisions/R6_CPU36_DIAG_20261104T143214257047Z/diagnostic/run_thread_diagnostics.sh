#!/bin/bash
# Prepared for S00: small operators only, never a model restart.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/cluster_runtime.env"
: "${CCS_JOB_ID:?S00 must allocate a new compute job}"
[[ "$(hostname)" != login* ]] || exit 2
export PYTHONDONTWRITEBYTECODE=1
exec "$C2_PYTHON" -B "$HERE/run_diagnostics.py"
