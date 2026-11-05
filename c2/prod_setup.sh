#!/bin/bash
# One-time setup of a C2 corpus folder (login node): freezes the code that every shard job runs and splits the case
# list into shards of one whole-node job each. With 25 contacts, 3 cases = 300 units, about 4 h on the 48 slots of a node
# (3 single-thread units per NUMA domain, PILOT_C2_REPORT.md). Refuses to overwrite an existing folder's code.
# Usage: prod_setup.sh <out> <case list file (one case per line)> [cases per shard, default 3]
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$1; CL=$2; PER=${3:-3}
[ -e $O/code ] && { echo "$O/code exists; not overwriting frozen code"; exit 1; }
mkdir -p $O/code $O/cases $O/shards $O/logs
cp $H/opt/code/s2_mesh.py $H/opt/code/s3_forward.py $H/opt/code/s6_corpus.py $H/prod_tasks.sh $H/prod_c2.sh $O/code/
cp $H/env.sh $O/code/env.sh.used
(cd $O/code && md5sum * > MD5SUMS)
grep -v '^#' $CL | awk 'NF {print $1}' | sort -u > $O/cases.txt
split -l $PER -d -a 2 --additional-suffix=.txt $O/cases.txt $O/shards/shard_
(cd $O/code && python3 -c "import s6_corpus as S; print('config_hash', S.CFG_HASH, 'code_hash', S.CODE_HASH)") | tee $O/code/HASHES
echo "$(wc -l < $O/cases.txt) cases in $(ls $O/shards | wc -l) shards of up to $PER"
