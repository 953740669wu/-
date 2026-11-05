#!/bin/bash
# End-to-end test of run_c2_tasks.sh on s0322 with small units (1 contact x 1 baseline x 2 breaths): placements,
# 2 cluster meshes, 4 units (2 placements x 2 belts), manifest. Then placement 0 / 16-belt results on the cluster
# mesh vs the amax-mesh reference (val/ref c0, same seeds): the mesh-to-mesh difference at level D.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt/worker_test
rm -rf $O; mkdir -p $O/code $O/cases/s0322
cp $H/opt/code/s3_forward.py $H/opt/code/s6_corpus.py $H/opt/code/s2_mesh.py $O/code/
cp $H/val/cases/s0322/prep.npz $O/cases/s0322/; cp $H/val/body_base_s0322.stl $O/cases/s0322/body_base.stl
echo s0322 > $O/cases.txt
xargs --version | head -1
export CFG_OVERRIDE='{"contacts": 1, "baselines": 1, "breaths": 2}'
bash $H/opt/run_c2_tasks.sh $O $O/cases.txt
cat $O/logs/*.log | grep -i -E "error|traceback" | head || true
source $H/env.sh
python3 - <<'PY'
import json, numpy as np
H = '/home/share/songzhenlong/eitfm'; O = H + '/opt/worker_test'
for k in (0, 1):
    m = json.load(open(f'{O}/cases/s0322/mesh_p{k}.json'))
    print('mesh', k, {x: m[x] for x in ('nodes', 'tets', 'mesh_volume_L', 'host', 'gmsh_threads')}, 'gmsh_volume_s', round(m['timing']['gmsh_volume_s']))
p_amax = json.load(open(f'{H}/val/cases/s0322/placements.json'))['placements'][0]
p_c2 = json.load(open(f'{O}/cases/s0322/placements.json'))['placements'][0]
print('placement 0 identical to amax:', p_amax['normal'] == p_c2['normal'] and p_amax['d'] == p_c2['d'])
a = np.load(f'{H}/val/ref/s0322_p0_16_adjacent_c0.npz'); b = np.load(f'{O}/parts/s0322_p0_16_adjacent_c0.npz')
rel = lambda x, y: float(np.linalg.norm(x.astype(float) - y.astype(float)) / np.linalg.norm(x.astype(float)))
da = a['v_cur'][:2] - a['v_ref'][0]; db = b['v_cur'][:2] - b['v_ref'][0]
print('cluster mesh vs amax mesh (p0, 16-belt, baseline 0, 2 breaths): v_ref rel', rel(a['v_ref'][0], b['v_ref'][0]),
      'dv rel', rel(da, db), 'images identical', bool(np.array_equal(a['images'][:2], b['images'][:2])))
PY
echo WORKER_TEST_DONE
