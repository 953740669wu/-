#!/bin/bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$ROOT/payload/interfaces/cluster_runtime.env"
export HBM=0 CKPT=0 COMPILE=0
CPUS=$1 NODE=$2
shift 2
inherited=$(sed -n 's/^Cpus_allowed_list:[[:space:]]*//p' "/proc/$$/status")
printf 'pid=%s\njob=%s\nnode=%s\ninherited=%s\nallocated_domain=%s\n' "$$" "$CCS_JOB_ID" "$NODE" "$inherited" "$CPUS" > "${M1_INHERIT_RECEIPT:?}"
if [[ "$inherited" != "${M1_PARENT_CPU_LIST:?}" ]]; then
    printf 'worker shell did not inherit the exact native allocation\n' >&2
    exit 2
fi
if [[ -n "${M23_HBM_LIBRARY:-}" ]]; then
    exec /usr/bin/numactl --physcpubind="$CPUS" --membind="$NODE" /usr/bin/env \
      HBM=1 LD_PRELOAD="$M23_HBM_LIBRARY:$LD_PRELOAD" "$C2_PYTHON" -B "$ROOT/payload/worker.py" "$@"
fi
exec /usr/bin/numactl --physcpubind="$CPUS" --membind="$NODE" "$C2_PYTHON" -B "$ROOT/payload/worker.py" "$@"
