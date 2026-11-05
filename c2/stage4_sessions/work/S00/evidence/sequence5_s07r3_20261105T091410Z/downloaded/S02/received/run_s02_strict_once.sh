#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?native scheduler identity required}"
timeout --signal=TERM --kill-after=2s 45s /usr/bin/python3 -B "$HERE/cpp_readonly_identity.py" "$HERE" > "$HERE/cpp_probe.log" 2>&1 || echo "$?" > "$HERE/cpp_probe_nonzero.txt"
exec env S02_CASE_FILE="/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt" bash "$HERE/payload/run_s00_seq5_job.sh" strict
