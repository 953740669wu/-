#!/bin/bash
# Called only for the unique approved real pilot; no login profile on compute.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
fail() { echo "$*" >&2; exit 2; }
[[ -n "${CCS_JOB_ID:-}" && -n "${S02_REAL_DESCRIPTOR:-}" && -n "${S02_REAL_DESCRIPTOR_SHA256:-}" ]] || fail 'new job and authoritative ready descriptor/SHA required'
[[ "$(hostname)" != login* ]] || fail 'compute allocation required'
case "$HERE" in /home/share/dengqingtian/*) ;; *) fail 'owned staging path required' ;; esac
export OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 OMP_PLACES=cores OMP_PROC_BIND=close
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LINEAR_DTYPE=fp32 HBM=0
OUT="$HERE/outputs/real_${CCS_JOB_ID}"
if [[ "${1:-}" != --bounded-child ]]; then
  mkdir -p "$HERE/outputs"
  mkdir "$OUT" || fail 'refuse existing pilot output; no automatic retry'
  printf '%q ' /usr/bin/timeout --signal=TERM --kill-after=30s 840 bash "$0" --bounded-child >"$OUT/bounded_command.txt"
  printf '\n' >>"$OUT/bounded_command.txt"
  CODE=0
  /usr/bin/timeout --signal=TERM --kill-after=30s 840 bash "$0" --bounded-child || CODE=$?
  echo "$CODE" >"$OUT/exit_code.txt"
  if [[ "$CODE" == 124 || "$CODE" == 137 ]]; then
    printf '{"status":"INCOMPLETE","reason":"whole-entry timeout or termination","exit":%s}\n' "$CODE" >"$OUT/runner_status.json"
  fi
  exit "$CODE"
fi
source "$HERE/interfaces/cluster_runtime.env"
trap 'code=$?; echo "$code" >"$OUT/wrapper_error_code.txt"; exit 2' ERR
# Gate official metadata before allocation/framework imports; a fixture or old
# DATA_NOT_READY audit cannot launch training.
"$C2_PYTHON" -B "$HERE/inspect_descriptor.py" --descriptor "$S02_REAL_DESCRIPTOR" \
  --descriptor-sha256 "$S02_REAL_DESCRIPTOR_SHA256" --output "$OUT/data_gate.json" >"$OUT/data_gate.log" 2>&1
PLACEMENT=$("$C2_PYTHON" -B "$HERE/cpu36_guard.py" --capture "$OUT/cpu_allocation.json" 2>"$OUT/allocation_error.txt")
read -r NUMA_NODE ALLOCATED_CPUSET SELECTED_CPUSET <<< "$PLACEMENT"
[[ -z "${S02_CPUSET:-}" || "$S02_CPUSET" == "$SELECTED_CPUSET" ]] || fail 'CPU set differs'
COMMAND=(numactl --physcpubind="$ALLOCATED_CPUSET" --membind="$NUMA_NODE"
  "$C2_PYTHON" -B "$HERE/train_real.py" --descriptor "$S02_REAL_DESCRIPTOR"
  --descriptor-sha256 "$S02_REAL_DESCRIPTOR_SHA256" --expected-cpus "$SELECTED_CPUSET"
  --cpu-contract "$OUT/cpu_allocation.json" --batch-size 64 --output-dir "$OUT")
printf '%q ' "${COMMAND[@]}" >"$OUT/command.txt"
printf '\n' >>"$OUT/command.txt"
trap - ERR
CODE=0
"${COMMAND[@]}" >"$OUT/stdout_stderr.txt" 2>&1 || CODE=$?
echo "$CODE" >"$OUT/exit_code.txt"
exit "$CODE"
