#!/bin/bash
# Drop-in check of the optimized s3_forward/s6_corpus: the val.sh smoke units (s0322, placement 0, 16-belt,
# 2 contacts x 2 baselines x 2 breaths, 1 thread) against the amax MUMPS reference parts in val/ref.
# Acceptance: v_ref, v_cur, images identical at float32 storage or rel < 1e-6; z within 1e-15; J rel < 1e-6.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm; O=$H/opt
source $H/env.sh
hostname; awk '/Cpus_allowed_list/' /proc/self/status
W=$O/smoke; rm -rf $W; mkdir -p $W/cases/s0322
cp $H/val/cases/s0322/prep.npz $H/val/cases/s0322/placements.json $H/val/cases/s0322/mesh_p0.npz $W/cases/s0322/
CFG_OVERRIDE='{"contacts": 2, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=1 \
  python3 -c "
import resource, subprocess, sys, time
t = time.perf_counter(); subprocess.run(sys.argv[1:], check=True)
print('maxrss_kB', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, 'wall_s', round(time.perf_counter() - t, 1))
" python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $W
python3 - <<'PY'
import json, numpy as np
H = '/home/share/songzhenlong/eitfm'
rel = lambda x, y: float(np.abs(x.astype(float) - y.astype(float)).max() / np.abs(x.astype(float)).max())
for c in (0, 1):
    a = np.load(f'{H}/val/ref/s0322_p0_16_adjacent_c{c}.npz'); b = np.load(f'{H}/opt/smoke/parts/s0322_p0_16_adjacent_c{c}.npz')
    da = a['v_cur'] - a['v_ref'][a['base_of_pair']]; db = b['v_cur'] - b['v_ref'][b['base_of_pair']]
    r = dict(contact=c, v_ref=rel(a['v_ref'], b['v_ref']), v_cur=rel(a['v_cur'], b['v_cur']), dv=rel(da, db),
             images=rel(a['images'], b['images']), z=rel(a['z'], b['z']),
             f32_identical=all(np.array_equal(a[k], b[k]) for k in ('v_ref', 'v_cur', 'images')))
    if 'J_img' in a.files:
        r['J'] = rel(a['J_img'], b['J_img'])
    r['pass'] = (r['f32_identical'] or max(r['v_ref'], r['v_cur'], r['images']) < 1e-6) and r['z'] < 1e-15 and r.get('J', 0) < 1e-6
    print(json.dumps(r))
    t = json.load(open(f'{H}/opt/smoke/parts/s0322_p0_16_adjacent_c{c}.json'))
    print('timing', {k: round(v, 2) for k, v in t['timing'].items()}, 'checks', t['checks'], 'rss_gb', round(t['peak_rss_gb'], 2))
PY
echo SMOKE_OPT_DONE
