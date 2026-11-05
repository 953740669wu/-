#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/interfaces/cluster_runtime.env"
# No login-only scheduler profile is sourced on the compute node.
exec bash "$HERE/run_sequence5.sh" "${1:?strict or memory}"
