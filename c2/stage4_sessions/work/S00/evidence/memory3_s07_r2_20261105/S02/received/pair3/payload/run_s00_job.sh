#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/interfaces/cluster_runtime.env"
case "${1:-equivalence}" in
  equivalence) exec bash "$HERE/run_c2_diagnostic.sh" checkpoint_strict ;;
  memory) exec bash "$HERE/run_c2_memory.sh" ;;
  *) echo 'choose equivalence or separately authorized memory' >&2; exit 2 ;;
esac
