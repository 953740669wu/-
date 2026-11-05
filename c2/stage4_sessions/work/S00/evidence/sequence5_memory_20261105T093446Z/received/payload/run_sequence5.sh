#!/bin/bash
# S00 executes only after review; strict and memory are separate job arrangements.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
fail() { echo "$*" >&2; exit 2; }
[[ -n "${C2_PYTHON:-}" && -n "${CCS_JOB_ID:-}" ]] || fail 'verified runtime and real new job required'
[[ "$(hostname)" != login* ]] || fail 'allocated compute node required'
case "$HERE" in /home/share/dengqingtian/*) ;; *) fail 'owned staging path required' ;; esac
MODE=${1:?strict or memory}
case "$MODE" in strict|memory) ;; *) fail 'strict or memory only' ;; esac
export OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 OMP_PLACES=cores OMP_PROC_BIND=close
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LINEAR_DTYPE=fp32 HBM=0
export S02_SEQUENCE_ROOT="$HERE" S02_CASE_FILE="${S02_CASE_FILE:-$HERE/case/fixed_16_pre.pt}"
OUT="$HERE/evidence/sequence5_${CCS_JOB_ID}_${MODE}"
mkdir -p "$HERE/evidence"
mkdir "$OUT" || fail 'refuse existing sequence output'
trap 'code=$?; echo "$code" >"$OUT/wrapper_error_code.txt"; exit 2' ERR
"$C2_PYTHON" -B - >"$OUT/identity_check.json" 2>"$OUT/identity_error.txt" <<'PY'
import hashlib,json,os
from pathlib import Path
root=Path(os.environ['S02_SEQUENCE_ROOT'])
sources=json.loads((root/'SOURCE_SHA256.json').read_text())
for name,expected in sources.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
case=Path(os.environ['S02_CASE_FILE']);frozen=json.loads((root/'CASE_MANIFEST.json').read_text())
h=hashlib.sha256()
with case.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
assert h.hexdigest()==frozen['sha256'] and case.stat().st_size==frozen['bytes']
print(json.dumps(dict(source_sha256=sources,case_file_sha256=h.hexdigest(),case_file_bytes=case.stat().st_size),indent=2))
PY
if [[ "$MODE" == memory ]]; then
  [[ -n "${S02_SEQUENCE5_RESULT:-}" ]] || fail 'new five-step PASS path required; one-step PASS is refused'
  "$C2_PYTHON" -B "$HERE/sequence_gate.py" "$S02_SEQUENCE5_RESULT" >"$OUT/strict_gate.json" 2>"$OUT/strict_gate_error.txt"
fi
PLACEMENT=$("$C2_PYTHON" -B "$HERE/cpu36_guard.py" --capture "$OUT/cpu_allocation.json" 2>"$OUT/allocation_error.txt")
read -r NUMA_NODE ALLOCATED_CPUSET SELECTED_CPUSET <<< "$PLACEMENT"
if [[ -n "${S02_CPUSET:-}" && "$S02_CPUSET" != "$SELECTED_CPUSET" ]]; then fail 'outer CPU set differs'; fi
BASE=(numactl --physcpubind="$ALLOCATED_CPUSET" --membind="$NUMA_NODE" "$C2_PYTHON" -B)
ARGS=(--case-file "$S02_CASE_FILE" --expected-cpus "$SELECTED_CPUSET" --cpu-contract "$OUT/cpu_allocation.json")
run_child() {
  local DIR=$1
  shift
  mkdir "$DIR"
  printf '%q ' "$@" >"$DIR/command.txt"
  printf '\n' >>"$DIR/command.txt"
  local CODE=0
  "$@" >"$DIR/stdout_stderr.txt" 2>&1 || CODE=$?
  echo "$CODE" >"$DIR/exit_code.txt"
  [[ "$CODE" == 0 ]] || exit "$CODE"
}
if [[ "$MODE" == strict ]]; then
  run_child "$OUT/checker" timeout --signal=TERM --kill-after=15s 780 "${BASE[@]}" \
    "$HERE/check_sequence5.py" "${ARGS[@]}" --output "$OUT/checker/result.json"
else
  for CKPT in 0 1; do
    run_child "$OUT/ckpt$CKPT" timeout --signal=TERM --kill-after=15s 360 "${BASE[@]}" \
      "$HERE/train_sequence5.py" "${ARGS[@]}" --checkpoint "$CKPT" \
      --strict-result "$S02_SEQUENCE5_RESULT" --output "$OUT/ckpt$CKPT/result.json"
  done
fi
echo "SEQUENCE5_DONE MODE=$MODE OUT=$OUT"
