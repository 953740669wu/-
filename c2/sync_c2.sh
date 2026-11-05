#!/bin/bash
# Transfers between amax and the C2 corpus folder, run on the PC (the only host that reaches both). Each side's file
# list is compared and only missing files cross, streamed as tar through the PC; nothing is stored here.
#   push <amax dir> <c2 dir> <case list>   stage-1 inputs per case: prep.npz/.json, body_base.stl/.json
#   pull <c2 dir> <amax dir>               results: parts/*, placements and mesh sidecars, logs, manifest.csv
#                                          (the manifest is rebuilt on C2 first; meshes stay on C2, ~25 MB each)
set -e -o pipefail; export LC_ALL=C   # byte order on every host, so comm sees both lists sorted alike
A=szl@10.16.109.128; C=songzhenlong@10.44.9.4
q() { grep -v '^\*\*\|Authorized\|post-quantum\|store now\|upgraded' || true; }   # grep exits 1 when nothing is left
lst() { ssh -o BatchMode=yes $1 "cd $2 2>/dev/null && find $3 -type f -printf '%P\n' 2>/dev/null | LC_ALL=C sort" 2>&1 | q | awk NF || true; }   # awk: drop the blank line left by the login banner
case $1 in
push) AD=$2; CD=$3; CL=$4
  want=$(grep -v '^#' $CL | awk 'NF {print $1}' | while read c; do for f in prep.npz prep.json body_base.stl body_base.json; do echo "cases/$c/$f"; done; done | sort)
  have=$(lst $C $CD cases | sed 's|^|cases/|')
  new=$(comm -23 <(echo "$want") <(echo "$have"))
  [ -n "$new" ] || { echo "push: nothing new"; exit 0; }
  echo "push: $(echo "$new" | wc -l) files"
  echo "$new" | ssh -o BatchMode=yes $A "cd $AD && tar czf - -T -" 2> >(q >&2) | ssh -o BatchMode=yes $C "mkdir -p $CD && cd $CD && tar xzmf -" 2>&1 | q
  ;;
pull) CD=$2; AD=$3
  ssh -o BatchMode=yes $C "cd $CD && python3 code/s6_corpus.py manifest $CD > /dev/null" 2>&1 | q
  sel() { grep -E '^(parts/|logs/|manifest\.csv$|cases/[^/]+/(placements\.json|mesh_p[0-9]+\.json)$)'; }
  have=$(lst $A $AD .)
  new=$(comm -23 <(lst $C $CD . | sel) <(echo "$have"))
  new=$( (echo "$new"; echo manifest.csv; lst $C $CD logs | sed 's|^|logs/|') | awk 'NF' | sort -u)   # manifest and logs grow: always refresh
  echo "pull: $(echo "$new" | grep -c '^parts/.*\.json$' || true) new units, $(echo "$new" | wc -l) files"
  echo "$new" | ssh -o BatchMode=yes $C "cd $CD && tar cf - -T -" 2> >(q >&2) | ssh -o BatchMode=yes $A "mkdir -p $AD && cd $AD && tar xmf -" 2>&1 | q
  ;;
*) echo "usage: sync_c2.sh push <amax dir> <c2 dir> <case list> | pull <c2 dir> <amax dir>"; exit 1;;
esac
