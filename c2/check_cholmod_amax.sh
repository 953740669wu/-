#!/bin/bash
# Same smoke units as smoke/ (MUMPS), re-solved with CHOLMOD; compares voltages and images.
set -e
P=/mnt/lvliannas/szl/thorax_eitfm_pilot_20261101; S=$P/smoke; C=$P/smoke_cholmod
PP=/data2/szl/conda_envs/eit_petsc/bin/python
mkdir -p $C/cases/s0322
cp $S/cases/s0322/prep.npz $S/cases/s0322/placements.json $S/cases/s0322/mesh_p0.npz $C/cases/s0322/
cd $C; rm -rf code; cp -r $S/code code
export CFG_OVERRIDE='{"contacts": 2, "baselines": 2, "breaths": 2}' OMP_NUM_THREADS=8 SOLVER=cholmod
/usr/bin/time -f "maxrss_kB %M wall %e" $PP -I code/s6_corpus.py solve s0322 0 16_adjacent $C
$PP -c "
import numpy as np
for c in (0, 1):
    a = np.load('$S/parts/s0322_p0_16_adjacent_c%d.npz' % c); b = np.load('$C/parts/s0322_p0_16_adjacent_c%d.npz' % c)
    rel = lambda k: float(np.linalg.norm(a[k].astype(float) - b[k].astype(float)) / np.linalg.norm(a[k].astype(float)))
    dv = (a['v_cur'] - a['v_ref'][a['base_of_pair']]), (b['v_cur'] - b['v_ref'][b['base_of_pair']])
    print('contact', c, 'v_ref', rel('v_ref'), 'v_cur', rel('v_cur'), 'dv', float(np.linalg.norm(dv[0] - dv[1]) / np.linalg.norm(dv[0])), 'images identical', bool((a['images'] == b['images']).all()))
"
