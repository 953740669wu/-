#!/bin/bash
# Which libraries provide the runtime symbols KML's libklapack_full.so leaves undefined (BiSheng flang + C++ runtime).
K=/opt/HPCKit
echo "== ldd libklapack_full"; ldd $K/kml-lib/sve512/libklapack_full.so
echo "== NEEDED"; readelf -d $K/kml-lib/sve512/libklapack_full.so | grep -E "NEEDED|RUNPATH|RPATH"
echo "== bisheng-lib"; ls $K/bisheng-lib
for s in __mth_i_cdiv bs_f90_str_cpy1 __pd_powi_1 __gxx_personality_v0 _ZSt9terminatev; do
  echo "== $s"
  for f in $(find $K /usr/lib64 -maxdepth 4 -name "*.so*" -type f 2>/dev/null); do
    nm -D --defined-only $f 2>/dev/null | grep -q " $s$" && echo "  $f"
  done | head -5
done
