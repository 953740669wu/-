#!/bin/bash
# Prepared only. Execute after S01 R7 review and a fresh bounded compute allocation.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/cluster_runtime.env"
: "${S01_RUN:?set the fresh staged task root}"
: "${CCS_JOB_ID:?run inside the newly allocated Donau job}"
S01_RUN=$(cd -- "$S01_RUN" && pwd -P)
case "$S01_RUN" in
  /home/share/dengqingtian/opt/stage4_sessions/S00/*|/home/share/dengqingtian/opt/stage4_sessions/S01/*) ;;
  *) exit 2 ;;
esac
[[ "$(hostname)" != login* ]] || exit 2
[[ "$(command -v python3)" = "$C2_PYTHON" ]] || exit 2
[[ -z "${RUN_ID:-}" ]] || { echo 'worker RUN_ID must not be inherited' >&2; exit 2; }
( set -o noclobber; printf '%s\n' "$CCS_JOB_ID" > "$S01_RUN/startup36_once.marker" ) || exit 2
export S01_RUN NDOM=1 CORES_PER_DOM=36 ROUNDS=3 REPS=1 BATCH=32
export HBM=0 MEMPOL=membind SKIP_BUSY=0 SAMPLE_FOREIGN=0
export RUN_TIMEOUT=180 SYNC_TIMEOUT=120 DEVICE=cpu AMP=fp32 KML_LINEAR=1 LINEAR_DTYPE=fp32 CKPT=0
CPU36_RUNTIME_REFERENCE=$(bash "$S01_RUN/candidate/run_node16.sh" --preflight)
[[ -f "$CPU36_RUNTIME_REFERENCE" ]] || exit 2
export CPU36_RUNTIME_REFERENCE
timeout --signal=TERM --kill-after=15s 780s \
  bash "$S01_RUN/candidate/run_node16.sh" "s01_cpu36_${CCS_JOB_ID}" \
  BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32 CKPT=0 BELTS=16_adjacent PARTS=pre,dec REPS=1
