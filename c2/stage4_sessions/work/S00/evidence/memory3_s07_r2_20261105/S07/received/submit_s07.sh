#!/bin/bash
set -euo pipefail
RUN=$(cd -- "$(dirname -- "$0")" && pwd -P)
MEM=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_R6_MEMORY3_20261105T072600Z
source /etc/profile.d/donaukit_scheduler.sh
JOB=$(cat "$MEM/job_id.txt")
djob -J -l "$JOB" > "$RUN/memory_dependency_terminal.json"
/usr/bin/python3 -B - "$RUN" "$MEM" <<'PY'
import hashlib,json,sys
from pathlib import Path
r,m=map(Path,sys.argv[1:])
j=json.loads((r/'memory_dependency_terminal.json').read_text())['data']['successData'][0]
s=json.loads((m/'job_evidence/SUMMARY.json').read_text())
assert j['state']=='SUCCEEDED' and j['jobExitCode']==0
assert all(u['pids']=='-' for g in j['resGroups'] for u in g['nodeResUsages'])
assert s['status']=='PASS_THREE_NEW_PAIRS_DDR_FIRST_STEP_DIAGNOSTIC_ONLY'
assert len(s['pairs'])==3 and len(set(s['distinct_model_pids']))==6
(r/'memory_dependency.json').write_text(json.dumps(dict(job_id=str(j['jobId']),summary_path=str(m/'job_evidence/SUMMARY.json'),summary_sha256=hashlib.sha256((m/'job_evidence/SUMMARY.json').read_bytes()).hexdigest(),terminal_sha256=hashlib.sha256((r/'memory_dependency_terminal.json').read_bytes()).hexdigest(),three_pairs_valid=True),indent=2)+'\n')
PY
(set -o noclobber; printf '%s\n' 'one R2 two-domain job after three valid memory pairs' > "$RUN/submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=76,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=2,distribution=pack]' -T 300 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_s07_r2_job.sh" > "$RUN/submission.json" 2> "$RUN/submission.stderr.txt"
/usr/bin/python3 -B -c 'import json,sys; from pathlib import Path; r=Path(sys.argv[1]); j=json.loads((r/"submission.json").read_text())["data"]["jobId"]; (r/"job_id.txt").write_text(str(j)+"\n"); print("S07_R2_JOB",j)' "$RUN"
