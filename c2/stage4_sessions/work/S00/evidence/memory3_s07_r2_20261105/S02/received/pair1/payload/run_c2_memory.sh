#!/bin/bash
# Preparation only: S00 needs a separately approved finite memory run and strict PASS.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
fail() { echo "$*" >&2; exit 2; }
[[ -n "${C2_PYTHON:-}" && -n "${CCS_JOB_ID:-}" && -n "${S02_EQUIVALENCE_RESULT:-}" ]] || fail 'new job/runtime and checkpoint PASS result required'
[[ "$(hostname)" != login* ]] || fail 'compute job required'
case "$HERE" in /home/share/dengqingtian/*) ;; *) fail 'owned staging path required' ;; esac
export OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 OMP_PLACES=cores OMP_PROC_BIND=close
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LINEAR_DTYPE=fp32 HBM=0
export S02_CASE_FILE="${S02_CASE_FILE:-$HERE/case/fixed_16_pre.pt}"
OUT="$HERE/evidence/memory_${CCS_JOB_ID}_ckpt64"
mkdir -p "$HERE/evidence"
mkdir "$OUT" || fail 'refuse existing memory output'
trap 'code=$?; echo "$code" >"$OUT/wrapper_error_code.txt"; exit 2' ERR
"$C2_PYTHON" -B "$HERE/memory_gate.py" "$S02_EQUIVALENCE_RESULT" >"$OUT/strict_gate.json" 2>"$OUT/strict_gate_error.txt"
# Verify the memory entry and every payload file, too; the strict result alone
# freezes only its own code. This performs no framework or model operation.
export S02_MEMORY_ROOT="$HERE"
"$C2_PYTHON" -B - >"$OUT/identity_check.json" <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ['S02_MEMORY_ROOT'])
sources = json.loads((root / 'SOURCE_SHA256.json').read_text())
for name, expected in sources.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
print(json.dumps(sources, indent=2))
PY
PLACEMENT=$("$C2_PYTHON" -B "$HERE/cpu36_guard.py" --capture "$OUT/cpu_allocation.json" 2>"$OUT/allocation_error.txt")
read -r NUMA_NODE ALLOCATED_CPUSET SELECTED_CPUSET <<< "$PLACEMENT"
if [[ -n "${S02_CPUSET:-}" && "$S02_CPUSET" != "$SELECTED_CPUSET" ]]; then fail 'outer CPU set differs'; fi
for CKPT in 0 1; do
  trap 'code=$?; echo "$code" >"$OUT/wrapper_error_code.txt"; exit 2' ERR
  DIR="$OUT/ckpt$CKPT"
  mkdir "$DIR"
  COMMAND=(timeout --signal=TERM --kill-after=15s 360
    numactl --physcpubind="$ALLOCATED_CPUSET" --membind="$NUMA_NODE"
    "$C2_PYTHON" -B "$HERE/train_memory.py" --checkpoint "$CKPT"
    --case-file "$S02_CASE_FILE" --expected-cpus "$SELECTED_CPUSET"
    --cpu-contract "$OUT/cpu_allocation.json" --output "$DIR/result.json")
  printf '%q ' "${COMMAND[@]}" >"$DIR/command.txt"
  printf '\n' >>"$DIR/command.txt"
  trap - ERR
  set +e
  "${COMMAND[@]}" >"$DIR/stdout_stderr.txt" 2>&1
  CODE=$?
  set -e
  echo "$CODE" >"$DIR/exit_code.txt"
  [[ "$CODE" == 0 ]] || exit "$CODE"
done
echo "TWO_INDEPENDENT_ONE_STEP_PROCESSES_ONLY OUT=$OUT"
