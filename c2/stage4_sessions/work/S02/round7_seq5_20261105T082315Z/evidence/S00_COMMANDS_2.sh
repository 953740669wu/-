set -euo pipefail
STRICT_JOB=$("$C2_PYTHON" -B -c 'import json,sys;print(json.load(sys.stdin)["data"]["jobId"])' <"$RUN/strict_submission.json")
STRICT_RESULT="$PAYLOAD/evidence/sequence5_${STRICT_JOB}_strict/checker/result.json"
"$C2_PYTHON" -B "$PAYLOAD/sequence_gate.py" "$STRICT_RESULT" >"$RUN/five_step_gate_before_submit.json"
source /etc/profile.d/donaukit_scheduler.sh
(set -o noclobber; printf '%s\n' "$STRICT_RESULT" >"$RUN/memory_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/memory_job.log" \
  env S02_CASE_FILE="$CASE" S02_SEQUENCE5_RESULT="$STRICT_RESULT" \
    bash "$PAYLOAD/run_s00_seq5_job.sh" memory \
  >"$RUN/memory_submission.json" 2>"$RUN/memory_submission.stderr.txt"
