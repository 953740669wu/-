#!/bin/bash
# NOT submission authorization. NEW S00 marker/resource/cleanup gate + S01 review required.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
fail() { echo "$*" >&2; exit 2; }
[[ -n "${CCS_JOB_ID:-}" && "$CCS_JOB_ID" != 2043445 && "$CCS_JOB_ID" != 2048959 ]] || fail 'new reviewed job required'
[[ -n "${S02_ENGINEERING_DESCRIPTOR:-}" && -n "${S02_ENGINEERING_DESCRIPTOR_SHA256:-}" ]] || fail 'original descriptor/SHA required'
case "$HERE" in /home/share/dengqingtian/opt/stage4_sessions/S00/S02_LINEAR_R10_*/payload) ;; *) fail 'new owned staging path required' ;; esac
[[ "$(hostname)" != login* ]] || fail 'compute allocation required'
OUT="$HERE/outputs/ab_${CCS_JOB_ID}"
if [[ "${1:-}" != --bounded-child ]]; then
  mkdir -p "$HERE/outputs"
  mkdir "$OUT" || fail 'refuse existing run; no retry'
  CODE=0
  /usr/bin/timeout --signal=TERM --kill-after=30s 840 bash "$0" --bounded-child || CODE=$?
  echo "$CODE" >"$OUT/exit_code.txt"
  if [[ "$CODE" != 0 ]]; then printf '{"status":"FAIL_OR_INCOMPLETE_STOP_NO_RETRY","exit":%s}\n' "$CODE" >"$OUT/runner_status.json"; fi
  exit "$CODE"
fi
source "$HERE/interfaces/cluster_runtime.env"
trap 'code=$?; echo "$code" >"$OUT/failure_code.txt"; exit 2' ERR
PLACEMENT=$("$C2_PYTHON" -B "$HERE/cpu36_guard.py" --capture "$OUT/cpu_allocation.json" 2>"$OUT/capture_error.txt")
read -r NODE ALLOCATED SELECTED <<< "$PLACEMENT"
COMMAND=(numactl --physcpubind="$ALLOCATED" --membind="$NODE" "$C2_PYTHON" -B)
COMMON=(--descriptor "$S02_ENGINEERING_DESCRIPTOR" --descriptor-sha256 "$S02_ENGINEERING_DESCRIPTOR_SHA256"
  --expected-cpus "$SELECTED" --cpu-contract "$OUT/cpu_allocation.json")
printf '%q ' "${COMMAND[@]}" >"$OUT/launcher.txt"
"${COMMAND[@]}" "$HERE/screen_linear.py" --expected-cpus "$SELECTED" --cpu-contract "$OUT/cpu_allocation.json" \
  --output-dir "$HERE/outputs/linear_screen_${CCS_JOB_ID}" >"$OUT/linear_screen.log" 2>&1
"${COMMAND[@]}" "$HERE/train_linear_ab.py" --phase strict "${COMMON[@]}" \
  --output-dir "$HERE/outputs/strict_${CCS_JOB_ID}" >"$OUT/strict.log" 2>&1
RECEIPT="$HERE/outputs/strict_${CCS_JOB_ID}/result.json"
RECEIPT_SHA=$("$C2_PYTHON" -B -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$RECEIPT")
for ROLE in baseline candidate; do
  "${COMMAND[@]}" "$HERE/train_linear_ab.py" --phase perf --variant "$ROLE" "${COMMON[@]}" \
    --strict-receipt "$RECEIPT" --strict-receipt-sha256 "$RECEIPT_SHA" \
    --output-dir "$HERE/outputs/perf_${ROLE}_${CCS_JOB_ID}" >"$OUT/perf_${ROLE}.log" 2>&1
done
