#!/bin/bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
source "$HERE/interfaces/cluster_runtime.env"
exec bash "$HERE/run_c2_diagnostic.sh" strict
