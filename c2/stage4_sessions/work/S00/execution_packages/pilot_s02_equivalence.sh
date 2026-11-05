#!/bin/bash
# Prepared only: one original strict configuration; no threshold or model changes.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/cluster_runtime.env"
: "${S02_RUN:?set a fresh staged S02 task root}"
: "${CCS_JOB_ID:?run inside the allocated Donau job}"
case "$S02_RUN" in /home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S02_*/payload) ;; *) exit 2 ;; esac
[[ "$(hostname)" != login* ]] || exit 2
export S02_RUN OMP_NUM_THREADS=4 OMP_PROC_BIND=false
PLACEMENT=$("$C2_PYTHON" -B - <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ['S02_RUN'])
for name, expected in json.loads((root / 'SOURCE_MANIFEST_S00.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
allowed = set(os.sched_getaffinity(0))
assert len(allowed) == 4, 'expected exactly four allocated CPUs'
nodes = []
for node in Path('/sys/devices/system/node').glob('node[0-9]*'):
    text = (node / 'cpulist').read_text().strip()
    if not text:
        continue
    cpus = set()
    for part in text.split(','):
        bounds = part.split('-')
        cpus.update(range(int(bounds[0]), int(bounds[-1]) + 1))
    if allowed <= cpus:
        nodes.append(int(node.name[4:]))
assert len(nodes) == 1, 'allocated CPUs must belong to one NUMA domain'
print(str(nodes[0]) + ' ' + ','.join(map(str, sorted(allowed))))
PY
)
read -r NUMA_NODE S02_CPUSET <<< "$PLACEMENT"
export S02_CPUSET
OUT="$S02_RUN/evidence/c2_${CCS_JOB_ID}"
mkdir -p "$S02_RUN/evidence"
mkdir "$OUT"
export S02_AFFINITY_REPORT="$OUT/checker_affinity.json"
timeout --signal=TERM --kill-after=15s 780 \
  numactl --physcpubind="$S02_CPUSET" --membind="$NUMA_NODE" \
  "$C2_PYTHON" -B "$S02_RUN/run_s02_checker_bound.py" \
  --belt 16_adjacent --part pre --microbatch 32 --history fresh --threads 4 \
  --kml --output "$OUT/equivalence.json"
