#!/bin/bash
set -euo pipefail
RUN=$(cd -- "$(dirname -- "$0")" && pwd -P)
PAYLOAD="$RUN/payload"
CASE=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt
STRICT=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T060434Z/payload/evidence/c2_2037034_checkpoint_strict/result.json
source "$PAYLOAD/interfaces/cluster_runtime.env"
"$C2_PYTHON" -B "$PAYLOAD/memory_gate.py" "$STRICT" > "$RUN/memory_gate_before_submit.json"
source /etc/profile.d/donaukit_scheduler.sh
command -v dsub > "$RUN/scheduler_path.txt"
(set -o noclobber; printf '%s\n' "$STRICT" > "$RUN/memory_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$PAYLOAD" -oo "$RUN/job.log" env S02_CASE_FILE="$CASE" S02_EQUIVALENCE_RESULT="$STRICT" bash "$PAYLOAD/run_s00_job.sh" memory > "$RUN/submission.json" 2> "$RUN/submission.stderr.txt"
/usr/bin/python3 -B -c 'import json,sys; from pathlib import Path; r=Path(sys.argv[1]); j=json.loads((r/"submission.json").read_text())["data"]["jobId"]; (r/"job_id.txt").write_text(str(j)+"\n"); print("MEMORY_JOB",j)' "$RUN"
