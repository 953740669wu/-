#!/bin/bash
# Run inside an allocated C2 compute job only; never writes sw/ or opt/code.
set -euo pipefail
: "${S00_RUN:?set an absolute unique S00 run directory}"
case "$S00_RUN" in
  /home/share/dengqingtian/opt/stage4_sessions/S00/*) ;;
  *) echo 'S00_RUN must be below the S00 remote root' >&2; exit 2 ;;
esac
mkdir "$S00_RUN/lib"
gcc -O2 -shared -fPIC -o "$S00_RUN/lib/libhbm_alloc.so" \
  "$S00_RUN/baseline/c2/opt/hbm_alloc.c" -lpthread
gcc -O2 -shared -fPIC -o "$S00_RUN/lib/libkml_sgemm_shim.so" \
  "$S00_RUN/baseline/c2/opt/kml_sgemm_shim.c" -ldl -lpthread
sha256sum "$S00_RUN"/lib/*.so > "$S00_RUN/lib/SHA256SUMS"
