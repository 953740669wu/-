"""Geometry QC for the thorax corpus: body truncated by the CT field of view, and nearly closed skin folds.

Usage: python qc_geometry.py <audit csv> <out csv> [n_workers]
Reads only the CT, the T5 and lung labels of each usable case; same body mask and +-15 cm crop as s1_prepare.py, same
surface as s2_mesh.py. Also reports the fraction of segmented lung inside the body mask. Flags: fov_cut_belt (body touches a lateral CT edge within +-4 cm of the belt plane) and
gap_lt_3mm (smallest skin-to-skin gap under 3 mm). Rows are written in case order, so reruns are identical.
"""
import os, sys, csv
import numpy as np
from multiprocessing import Pool
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_prepare as S1
import s2_mesh as S2

BELT_BAND_M = 0.04


def qc(case):
    try:
        ct, dx = S1.load(os.path.join(S1.TS, case, 'ct.nii.gz'))
        t5 = S1.load(os.path.join(S1.TS, case, 'segmentations', 'vertebrae_T5.nii.gz'))[0] > 0
        body = S1.body_mask(ct)
        lung = sum(S1.load(os.path.join(S1.TS, case, 'segmentations', f'lung_{k}.nii.gz'))[0] > 0
                   for k in ('upper_lobe_left', 'lower_lobe_left', 'upper_lobe_right', 'middle_lobe_right',
                             'lower_lobe_right')) > 0
        zb = int(round(np.where(t5.any((0, 1)))[0].mean()))
        h = int(round(S1.HALF_SLAB_M / dx[2]))
        z0, z1 = max(zb - h, 0), min(zb + h + 1, ct.shape[2])
        hb = int(round(BELT_BAND_M / dx[2]))
        b0, b1 = max(zb - hb, 0), min(zb + hb + 1, ct.shape[2])
        faces = lambda b: [b[0].mean(), b[-1].mean(), b[:, 0].mean(), b[:, -1].mean()]
        cut_crop, cut_belt = max(faces(body[:, :, z0:z1])), max(faces(body[:, :, b0:b1]))

        bb = np.where(body[:, :, z0:z1].any(2))
        x0, x1 = max(bb[0].min() - 2, 0), bb[0].max() + 3
        y0, y1 = max(bb[1].min() - 2, 0), bb[1].max() + 3
        surf = S2.body_surface(body[x0:x1, y0:y1, z0:z1].astype(np.uint8), dx, 0)
        p = np.asarray(surf.points)
        n = np.asarray(surf.compute_normals(cell_normals=False, point_normals=True)['Normals'])
        dist, i = cKDTree(p).query(p, k=40)
        gap = np.where(np.einsum('ij,ikj->ik', n, n[i]) < -0.5, dist, np.inf).min(1)
        near = np.abs(p[:, 2] - (zb - z0) * dx[2]) < BELT_BAND_M
        frac = lambda b: round(float((lung & b)[:, :, z0:z1].sum() / max(lung[:, :, z0:z1].sum(), 1)), 4)
        l, _ = ndimage.label(ct > -500)                     # body mask used before 2026-11-01, for comparison
        old = ndimage.binary_fill_holes(l == (np.bincount(l.ravel())[1:].argmax() + 1))
        return dict(case=case, lung_in_body_frac=frac(body), lung_in_old_body_frac=frac(old), fov_cut_crop_frac=round(float(cut_crop), 4), fov_cut_belt_frac=round(float(cut_belt), 4),
                    min_gap_mm=round(float(gap.min()) * 1e3, 2),
                    gap_pts_lt_3mm=int((gap < S2.GAP_MIN).sum()), gap_pts_lt_3mm_belt=int((gap[near] < S2.GAP_MIN).sum()),
                    fov_cut_belt=int(cut_belt > 0), gap_lt_3mm=int(gap.min() < S2.GAP_MIN), error='')
    except Exception as e:                                   # keep going; the row records the failure
        return dict(case=case, error=repr(e)[:200])


def main(audit, out, workers=16):
    cases = sorted(r['case'] for r in csv.DictReader(open(audit)) if r['usable'] == '1')
    with Pool(workers) as pool:
        rows = pool.map(qc, cases, chunksize=1)
    keys = ['case', 'lung_in_body_frac', 'lung_in_old_body_frac', 'fov_cut_crop_frac', 'fov_cut_belt_frac', 'min_gap_mm', 'gap_pts_lt_3mm', 'gap_pts_lt_3mm_belt',
            'fov_cut_belt', 'gap_lt_3mm', 'error']
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)
    ok = [r for r in rows if not r['error']]
    print(f'{len(rows)} cases, {len(rows) - len(ok)} errors; fov_cut_belt {sum(r["fov_cut_belt"] for r in ok)}; '
          f'gap_lt_3mm {sum(r["gap_lt_3mm"] for r in ok)}; '
          f'lung < 95% inside body: new mask {sum(r["lung_in_body_frac"] < .95 for r in ok)}, '
          f'old mask {sum(r["lung_in_old_body_frac"] < .95 for r in ok)}; '
          f'clean {sum(1 for r in ok if not r["fov_cut_belt"] and not r["gap_lt_3mm"])}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16)
