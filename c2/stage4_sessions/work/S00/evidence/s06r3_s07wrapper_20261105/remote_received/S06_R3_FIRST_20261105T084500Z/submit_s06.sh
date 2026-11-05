#!/bin/bash
set -euo pipefail
RUN=$(cd -- "$(dirname -- "$0")" && pwd -P)
test -f /etc/profile.d/donaukit_scheduler.sh
source /etc/profile.d/donaukit_scheduler.sh
dsub -h > "$RUN/login_dsub_help.txt"
(set -o noclobber; printf '%s\n' 'one S06 R3 original probe only; no S07 job' > "$RUN/submit_once.marker")
dsub -J -q q_hpcai -x job -R 'cpu=38,mem=8192MB' -RL 'mem=8192MB' -a 'numa[count=1,distribution=pack]' -T 660 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_s06_r3_job.sh" > "$RUN/submission.json" 2> "$RUN/submission.stderr.txt"
JOB=$(/usr/bin/python3 -B -c 'import json,sys; from pathlib import Path; r=Path(sys.argv[1]); j=json.loads((r/"submission.json").read_text())["data"]["jobId"]; (r/"job_id.txt").write_text(str(j)+"\n"); print(j)' "$RUN")
printf 'S06_JOB %s\n' "$JOB"
/usr/bin/python3 -B "$RUN/scheduler_handoff.py" publish --root "$RUN" --job-id "$JOB" > "$RUN/login_publish.log" 2>&1
