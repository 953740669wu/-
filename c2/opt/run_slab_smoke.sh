#!/bin/bash
# Smoke test of slab-aware pathology placement (s6_corpus.py): s0322 p0 16-belt, 1 contact x 6 baselines x 2 breaths,
# on the C2 worker_test mesh; per state: pathology, slab fields, and the defect's share of the target image.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt/slab_smoke
rm -rf $O; mkdir -p $O/code $O/cases/s0322
cp $H/opt/code/s3_forward.py $H/opt/code/s6_corpus.py $O/code/
for f in prep.npz placements.json mesh_p0.npz mesh_p0.json; do ln -s $H/opt/worker_test/cases/s0322/$f $O/cases/s0322/$f; done
source $H/env.sh
export CFG_OVERRIDE='{"contacts": 1, "baselines": 6, "breaths": 2}' OMP_NUM_THREADS=1
python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $O
python3 - <<'PY'
import json, numpy as np
O = '/home/share/songzhenlong/eitfm/opt/slab_smoke'
r = json.load(open(f'{O}/parts/s0322_p0_16_adjacent_c0.json')); z = np.load(f'{O}/parts/s0322_p0_16_adjacent_c0.npz')
print('code_hash', r['code_hash'], 'config_hash', r['config_hash'])
for st in r['states'][::2]:
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items() if k in
           ('baseline', 'pathology', 'side', 'slab_empty', 'threshold_yn_s', 'threshold_jj', 'centre_plane_dist_m', 'radius_vox', 'fraction', 'dorsal_fraction')})
print('images', z['images'].shape, 'finite', bool(np.isfinite(z['images']).all()), 'v_cur finite', bool(np.isfinite(z['v_cur']).all()))
PY
echo SLAB_SMOKE_DONE
