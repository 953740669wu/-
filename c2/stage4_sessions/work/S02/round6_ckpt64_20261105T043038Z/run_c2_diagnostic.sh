#!/bin/bash
# One strict CPU36 comparison. S00 alone supplies the new allocation and runtime.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
fail() { echo "$*" >&2; exit 2; }
[[ -n "${C2_PYTHON:-}" && -n "${CCS_JOB_ID:-}" ]] || fail 'source verified runtime inside a new Donau job'
[[ "$(hostname)" != login* ]] || fail 'compute allocation required'
case "$HERE" in /home/share/dengqingtian/*) ;; *) fail 'not an owned staging path' ;; esac
[[ "${1:-checkpoint_strict}" == checkpoint_strict && $# -le 1 ]] || fail 'one B64 checkpoint strict configuration only'
export OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1
export OMP_PLACES=cores OMP_PROC_BIND=close
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 LINEAR_DTYPE=fp32
export S02_DIAGNOSTIC_ROOT="$HERE"
export S02_CASE_FILE="${S02_CASE_FILE:-$HERE/case/fixed_16_pre.pt}"
OUT="$HERE/evidence/c2_${CCS_JOB_ID}_checkpoint_strict"
mkdir -p "$HERE/evidence"
mkdir "$OUT" || fail 'refuse existing output; do not repeat this comparison'
trap 'code=$?; echo "$code" >"$OUT/wrapper_error_code.txt"; echo 2 >"$OUT/checker_exit_code.txt"; exit 2' ERR
"$C2_PYTHON" -B - >"$OUT/identity_check.json" 2>"$OUT/identity_error.txt" <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ['S02_DIAGNOSTIC_ROOT'])
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()
source = json.loads((root/'SOURCE_SHA256.json').read_text())
for name, expected in source.items():
    assert sha(root/name) == expected, name
case = json.loads((root/'CASE_MANIFEST.json').read_text())
path = Path(os.environ['S02_CASE_FILE']).resolve()
assert path.stat().st_size == case['bytes'] and sha(path) == case['sha256'], 'wrong frozen case'
print(json.dumps(dict(source_sha256=source, case_path=str(path), case_sha256=case['sha256'],
                     case_bytes=case['bytes'], python=os.sys.executable), indent=2))
PY
PLACEMENT=$("$C2_PYTHON" -B "$HERE/cpu36_guard.py" --capture "$OUT/cpu_allocation.json" 2>"$OUT/allocation_error.txt")
read -r NUMA_NODE ALLOCATED_CPUSET SELECTED_CPUSET <<< "$PLACEMENT"
if [[ -n "${S02_CPUSET:-}" && "$S02_CPUSET" != "$SELECTED_CPUSET" ]]; then
  echo 2 >"$OUT/checker_exit_code.txt"
  fail 'outer S02_CPUSET differs from selected36; remove obsolete four-core setting'
fi
export S02_CPUSET="$SELECTED_CPUSET"
printf '%s\n' "node=$NUMA_NODE allocated=$ALLOCATED_CPUSET selected=$S02_CPUSET" >"$OUT/placement.txt"
# Preserve authorization until the checker captures it; that same PID binds selected36
# before importing numpy/torch. No computation executes on the two reserved cores.
COMMAND=(timeout --signal=TERM --kill-after=15s 780
  numactl --physcpubind="$ALLOCATED_CPUSET" --membind="$NUMA_NODE"
  "$C2_PYTHON" -B "$HERE/diagnose_update.py" --backend kml --mode checkpoint_strict
  --expected-cpus "$S02_CPUSET" --cpu-contract "$OUT/cpu_allocation.json"
  --case-file "$S02_CASE_FILE" --output "$OUT/result.json")
printf '%q ' "${COMMAND[@]}" >"$OUT/command.txt"
printf '\n' >>"$OUT/command.txt"
trap - ERR
set +e
"${COMMAND[@]}" >"$OUT/stdout_stderr.txt" 2>&1
CODE=$?
set -e
echo "$CODE" >"$OUT/checker_exit_code.txt"
echo "S02_DIAGNOSTIC_EXIT=$CODE OUT=$OUT"
exit "$CODE"
