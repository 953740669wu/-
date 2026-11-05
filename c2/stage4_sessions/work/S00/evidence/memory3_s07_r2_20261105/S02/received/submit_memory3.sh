#!/bin/bash
set -euo pipefail
RUN=$(cd -- "$(dirname -- "$0")" && pwd -P)
STRICT=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T060434Z/payload/evidence/c2_2037034_checkpoint_strict/result.json
source "$RUN/pair1/payload/interfaces/cluster_runtime.env"
for N in 1 2 3; do
  "$C2_PYTHON" -B "$RUN/pair$N/payload/memory_gate.py" "$STRICT" > "$RUN/memory_gate_before_submit_pair$N.json"
done
source /etc/profile.d/donaukit_scheduler.sh
(set -o noclobber; printf '%s\n' 'three original independent CKPT0/1 pairs; no retry' > "$RUN/submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$RUN" -oo "$RUN/job.log" env PATH=/usr/bin:/bin HBM=0 bash "$RUN/run_memory_three_pairs.sh" > "$RUN/submission.json" 2> "$RUN/submission.stderr.txt"
/usr/bin/python3 -B -c 'import json,sys; from pathlib import Path; r=Path(sys.argv[1]); j=json.loads((r/"submission.json").read_text())["data"]["jobId"]; (r/"job_id.txt").write_text(str(j)+"\n"); print("MEMORY3_JOB",j)' "$RUN"
