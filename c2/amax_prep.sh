#!/bin/bash
# Corpus inputs on amax for C2: stage 1 (s1_prepare) and the body surface (s2_mesh SURFACE_ONLY=1) for every included
# case, into <out>/cases/<case>/{prep.npz, prep.json, body_base.stl, body_base.json}. Volume meshes are made on C2.
# The code is frozen in <out>/code on the first run: s1_prepare.py and both CSVs as used by the pilot, s2_mesh.py from
# demo/ (uploaded next to this script). Resumable: cases whose files exist are skipped. data/raw is only read.
# Usage: amax_prep.sh <out> [parallel cases, default 8]
set -e -o pipefail
O=$1; NP=${2:-8}; PILOT=/mnt/lvliannas/szl/thorax_eitfm_pilot_20261101; HERE=$(cd $(dirname $0) && pwd)
export PA=/home/szl/software/anaconda3/bin/python O
mkdir -p $O/code $O/logs
if [ ! -f $O/code/MD5SUMS ]; then
  cp $PILOT/code/s1_prepare.py $PILOT/code/Cole_Cole_Fitted_Parameters.csv $PILOT/code/included_cases_20261101.csv $HERE/s2_mesh.py $O/code/
  (cd $O/code && md5sum * > MD5SUMS)
fi
cd $O
$PA -I -c "import csv; print('\n'.join(sorted(r['case'] for r in csv.DictReader(open('code/included_cases_20261101.csv')))))" > cases.txt
echo "$(wc -l < cases.txt) cases, $NP at a time"
one() {
  c=$1; t=$(date +%s)
  [ -f cases/$c/prep.npz ] || $PA -I code/s1_prepare.py $c $O code/Cole_Cole_Fitted_Parameters.csv > logs/${c}_s1.log 2>&1 || { echo "FAILED s1 $c"; return; }
  [ -f cases/$c/body_base.stl ] || SURFACE_ONLY=1 $PA -I code/s2_mesh.py $c $O > logs/${c}_surface.log 2>&1 || { echo "FAILED surface $c"; return; }
  echo "$c $(( $(date +%s) - t )) s"
}
export -f one
xargs -a cases.txt -P $NP -I{} bash -c 'one {}'
echo "inputs present: $(ls cases/*/prep.npz | wc -l) prep, $(ls cases/*/body_base.stl | wc -l) surfaces"
grep -l '"gap_ok": false' cases/*/body_base.json 2>/dev/null | sed 's|cases/||; s|/body_base.json||' | tr '\n' ' ' | sed 's/^/gap_ok false (for review): /'; echo
echo AMAX_PREP_DONE
