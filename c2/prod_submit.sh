#!/bin/bash
# Submit one whole-node job per shard that is not complete yet (login node). Rerunning it resubmits only unfinished
# shards; the worker skips what is done. Usage: prod_submit.sh <out> [shard file ...]   (default: all shards)
set -e -o pipefail
O=$1; shift
source /etc/profile.d/donaukit_scheduler.sh
for SH in ${@:-$O/shards/shard_*.txt}; do s=$(basename $SH .txt)
  left=$(python3 -c "
import sys; sys.path.insert(0, '$O/code'); import s6_corpus as S, os
cs = open('$SH').read().split()
print(sum(not os.path.exists(f'$O/parts/{c}_p{k}_{b}_c{j}.json') for c in cs for k in range(S.CFG['placements'])
          for b in S.CFG['belts'] for j in range(S.CFG['contacts'])))")
  [ "$left" = 0 ] && { echo "$s complete"; continue; }
  echo -n "$s ($left units left): "
  dsub -q q_hpcai -n eitfm_$s -R cpu=608,mem=480000MB -a "numa[count=16,distribution=pack]" -T ${WALL_S:-21600} \
    -oo $O/logs/$s.log bash -c "cp $O/code/prod_c2.sh /tmp/eitfm_${s}_\$\$.sh && bash /tmp/eitfm_${s}_\$\$.sh $O $SH"
done
