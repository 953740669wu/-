#!/bin/bash
set -euo pipefail
RUN=$(cd -- "$(dirname -- "$0")" && pwd -P)
source /etc/profile.d/donaukit_scheduler.sh
command -v dsub > "$RUN/scheduler_path.txt"
(set -o noclobber; printf '%s\n' 'UBSan controls then conditional original new50' > "$RUN/c_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=1,distribution=pack]' -T 300 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_s03_r2_ubsan_recovery.sh" > "$RUN/submission.json" 2> "$RUN/submission.stderr.txt"
/usr/bin/python3 -B -c 'import json,sys; from pathlib import Path; r=Path(sys.argv[1]); j=json.loads((r/"submission.json").read_text())["data"]["jobId"]; (r/"job_id.txt").write_text(str(j)+"\n"); print("UBSAN_C_JOB",j)' "$RUN"
