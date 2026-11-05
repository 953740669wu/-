#!/bin/bash
# Smoke test of the body-shape perturbation (s6_corpus.py): s0322 p0 16-belt, 1 contact x 6 baselines x 2 breaths, on
# the C2 worker_test mesh, as run_size_smoke.sh. (i) max_rel = 0: arrays bit-identical to the code-899ceae590 smoke
# (opt/size_smoke); (ii) A forced to 0.05: displacement, tet volume ratio, reference-frame change vs nominal.
set -e -o pipefail
H=/home/share/songzhenlong/eitfm
source $H/env.sh
export OMP_NUM_THREADS=1
run() {   # name, CFG_OVERRIDE
  O=$H/opt/shape_smoke_$1; rm -rf $O; mkdir -p $O/code $O/cases/s0322
  cp $H/opt/code/s3_forward.py $H/opt/code/s6_corpus.py $O/code/
  for f in prep.npz placements.json mesh_p0.npz mesh_p0.json; do ln -s $H/opt/worker_test/cases/s0322/$f $O/cases/s0322/$f; done
  CFG_OVERRIDE="$2" python3 $O/code/s6_corpus.py solve s0322 0 16_adjacent $O > $O/solve.log 2>&1
}
run a0 '{"contacts": 1, "baselines": 6, "breaths": 2, "shape": {"fourier_terms": 8, "max_rel": 0.0}}' &
run a5 '{"contacts": 1, "baselines": 6, "breaths": 2, "shape": {"fourier_terms": 8, "max_rel": 0.05, "amp": 0.05}}' &
wait
python3 - <<'PY'
import json, numpy as np
H = '/home/share/songzhenlong/eitfm/opt'; u = 'parts/s0322_p0_16_adjacent_c0'
for n in ('a0', 'a5'):
    print(n, open(f'{H}/shape_smoke_{n}/solve.log').read().strip()[-600:])
old, new = np.load(f'{H}/size_smoke/{u}.npz'), np.load(f'{H}/shape_smoke_a0/{u}.npz')
ro, rn = json.load(open(f'{H}/size_smoke/{u}.json')), json.load(open(f'{H}/shape_smoke_a0/{u}.json'))
print('(i) A=0 vs code', ro['code_hash'], '-> arrays:', sorted(old.files) == sorted(new.files),
      {f: bool(np.array_equal(old[f], new[f])) for f in old.files})
print('    checks equal', ro['checks'] == rn['checks'], ' states equal', ro['states'] == rn['states'],
      ' perimeter equal', ro['belt_perimeter_m'] == rn['belt_perimeter_m'], ' shape', rn['shape'])
r5 = json.load(open(f'{H}/shape_smoke_a5/{u}.json')); z5 = np.load(f'{H}/shape_smoke_a5/{u}.npz')
print('(ii) A=0.05 code', r5['code_hash'], 'config', r5['config_hash'], 'checks', r5['checks'], 'finite', r5['finite'])
print('     shape', {k: (round(v, 5) if isinstance(v, float) else v) for k, v in r5['shape'].items() if k not in ('a', 'b')})
print('     perimeter deformed', round(r5['belt_perimeter_m'], 4), 'timing', {k: round(v, 1) for k, v in r5['timing'].items()})
print('     J_img vs A=0 J_img equal:', bool(np.array_equal(z5['J_img'], new['J_img'])), ' images equal:', bool(np.array_equal(z5['images'], new['images'])),
      ' v_ref rel change vs A=0 (all baselines):', float(np.linalg.norm(z5['v_ref'] - new['v_ref']) / np.linalg.norm(new['v_ref'])))
PY
echo SHAPE_SMOKE_DONE
