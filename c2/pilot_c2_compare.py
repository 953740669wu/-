"""Compare the C2 pilot rerun (pilot_c2/parts) with the amax pilot (pilot_c2/amax_parts): output arrays, checks and timing.
Usage: python3 pilot_c2_compare.py <pilot_c2 dir> <node log> ...   (node logs give each job's wall time)"""
import glob, json, os, re, sys
import numpy as np

W, logs = sys.argv[1], sys.argv[2:]
ARR = ('v_ref', 'v_cur', 'images', 'J_img')
units = sorted(os.path.basename(f)[:-5] for f in glob.glob(f'{W}/amax_parts/*.json'))
done = [u for u in units if os.path.exists(f'{W}/parts/{u}.json')]
print(f'units: {len(done)} of {len(units)} on C2')

same, worst, nojac = 0, {k: 0.0 for k in ARR}, []
for u in done:
    a, c = np.load(f'{W}/amax_parts/{u}.npz'), np.load(f'{W}/parts/{u}.npz')
    if set(a.files) != set(c.files): print(u, 'stored arrays differ:', sorted(set(a.files) ^ set(c.files)))
    ks = [k for k in ARR if k in a.files and k in c.files]   # the Jacobian is stored once per task, not per contact
    if 'J_img' not in ks: nojac.append(u)
    eq = all(np.array_equal(a[k], c[k]) for k in ks)
    same += eq
    for k in ks:
        d = float(np.abs(a[k].astype(float) - c[k].astype(float)).max() / max(float(np.abs(a[k]).max()), 1e-300))
        worst[k] = max(worst[k], d)
print(f'float32-identical to amax: {same} of {len(done)}; max relative difference', {k: f'{v:.1e}' for k, v in worst.items()},
      f'; {len(nojac)} units store no J_img in either')

J = {s: {u: json.load(open(f'{W}/{s}/{u}.json')) for u in done} for s in ('amax_parts', 'parts')}
c2 = J['parts'].values()
print('C2 config hashes', sorted({r['config_hash'] for r in c2}), 'code hashes', sorted({r['code_hash'] for r in c2}))
print('C2 checks: max conservation %.1e A, max reciprocity %.1e, all finite %s, peak RSS max %.2f GB' % (
    max(r['checks']['current_conservation_max_abs_A'] for r in c2), max(r['checks']['reciprocity_max_rel'] for r in c2),
    all(r['finite'] for r in c2), max(r['peak_rss_gb'] for r in c2)))
for belt in ('16_adjacent', '32_skip4'):
    for s in ('amax_parts', 'parts'):
        t = [r['timing'] for u, r in J[s].items() if belt in u]
        ks = sorted(set().union(*t))
        med = {k: round(float(np.median([x[k] for x in t if k in x])), 1) for k in ks}
        print(f'{belt} {"amax" if s == "amax_parts" else "C2  "} n={len(t)} median', med,
              'unit_wall min-max %.0f-%.0f s' % (min(x['unit_wall_s'] for x in t), max(x['unit_wall_s'] for x in t)))
for f in logs:
    m = re.search(r'wall (\d+) s', open(f).read())
    print(f'{os.path.basename(f)}: wall {m.group(1) if m else "?"} s')
