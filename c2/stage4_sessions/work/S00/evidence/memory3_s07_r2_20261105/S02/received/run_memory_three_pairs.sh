#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
: "${CCS_JOB_ID:?requires actual allocated job}"
export S02_CASE_FILE=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt
export S02_EQUIVALENCE_RESULT=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T060434Z/payload/evidence/c2_2037034_checkpoint_strict/result.json
exec /usr/bin/python3 -B "$HERE/run_memory_three_pairs.py" "$HERE"
