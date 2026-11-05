"""Stage 1: CT + TotalSegmentator labels -> cropped thoracic tissue map, sigma table, 32 electrode sites.

Reads raw data read-only. Writes <out>/cases/<case>/prep.npz and timing json.
Coordinates: canonical RAS voxel grid of the crop, in metres (x = i * dx).
"""
import os, sys, json, time, glob, csv
import numpy as np, nibabel as nib
from scipy import ndimage
from skimage import measure

TS = '/mnt/lvliannas/szl/raw_datasets/TotalSegmentator_data/TS_Extracted'
FREQ = 100e3
HALF_SLAB_M = 0.15          # crop +-15 cm around the belt plane
N_SITES = 32                # 32 sites; the 16-electrode belt uses every second one

# tissue ids -> Cole-Cole class in the project table (code/阶段二/.../Cole_Cole_Fitted_Parameters.csv)
TISSUES = {1: ('muscle', 'Muscle'), 2: ('fat', 'SAT (Subcutaneous Fat)'), 3: ('bone_cancellous', 'Bone (Cancellous)'),
           4: ('bone_cortical', 'Vertebrae'), 5: ('blood', 'Blood'), 6: ('lung_left', 'Lung'), 7: ('lung_right', 'Lung'),
           8: ('liver', 'Liver'), 9: ('spleen', 'Spleen'), 10: ('stomach', 'Stomach'), 11: ('kidney', 'Kidney'),
           12: ('air', None)}
AIR_SIGMA = 1e-4


def cole_cole(f, p):
    jw = (1j * 2 * np.pi * f * p['tau']) ** p['alpha']
    return p['s0'] + (p['sinf'] - p['s0']) * jw / (1 + jw)


def sigma_table(csv_path):
    params = {}
    for r in csv.DictReader(open(csv_path, encoding='utf-8-sig')):
        params[r['IT_IS分类'].strip()] = {k: float(r[k]) for k in ('s0', 'sinf', 'tau', 'alpha')}
    sig = np.zeros(13)
    src = {}
    for tid, (name, cls) in TISSUES.items():
        sig[tid] = AIR_SIGMA if cls is None else cole_cole(FREQ, params[cls]).real
        src[name] = cls or 'air (fixed 1e-4 S/m)'
    return sig, src


def load(p):
    im = nib.as_closest_canonical(nib.load(p))
    return np.asarray(im.dataobj), np.array(im.header.get_zooms()[:3], float) / 1000.0


def body_mask(ct):
    """Patient body: CT > -500 HU, with thin attachments (table shell, sheets) cut by an in-plane opening, largest
    component, holes filled slice by slice. A 3D fill misses the lungs whenever the airway leaves the scan."""
    disk = np.add.outer(np.arange(-2, 3) ** 2, np.arange(-2, 3) ** 2) <= 4
    body = ndimage.binary_opening(ct > -500, structure=disk[:, :, None])
    l, n = ndimage.label(body)
    body = l == (np.bincount(l.ravel())[1:].argmax() + 1)
    for z in range(body.shape[2]):
        body[:, :, z] = ndimage.binary_fill_holes(body[:, :, z])
    return body


def label_map(case, ct):
    seg = os.path.join(TS, case, 'segmentations')
    lab = np.zeros(ct.shape, np.uint8)
    body = body_mask(ct)
    lab[body] = 1
    lab[body & (ct >= -190) & (ct <= -30)] = 2
    lab[body & (ct < -900)] = 12                       # bowel gas / airway
    groups = [(3, ['rib_', 'sternum', 'scapula_', 'clavicula_', 'humerus_', 'costal_cartilages']),
              (4, ['vertebrae_']), (5, ['heart', 'aorta', 'pulmonary_vein', 'superior_vena_cava', 'inferior_vena_cava',
                                        'atrial_appendage', 'brachiocephalic', 'subclavian_artery', 'common_carotid']),
              (8, ['liver']), (9, ['spleen']), (10, ['stomach', 'esophagus']), (11, ['kidney_left', 'kidney_right']),
              (12, ['trachea']), (6, ['lung_upper_lobe_left', 'lung_lower_lobe_left']),
              (7, ['lung_upper_lobe_right', 'lung_middle_lobe_right', 'lung_lower_lobe_right'])]
    for tid, prefixes in groups:
        for f in sorted(glob.glob(os.path.join(seg, '*.nii.gz'))):
            n = os.path.basename(f)[:-7]
            if any(n.startswith(p) for p in prefixes):
                lab[(load(f)[0] > 0) & body] = tid
    return lab, body


def electrode_sites(body_slice, dx):
    """32 points at equal arc length on the outer body contour of one axial slice (metres, in-plane)."""
    c = max(measure.find_contours(body_slice.astype(float), 0.5), key=len)
    # start at the most anterior point (max y) so electrode 0 is sternal, ordering counter-clockwise from above
    c = np.roll(c, -int(np.argmax(c[:, 1])), axis=0)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
    t = np.linspace(0, seg[-1], N_SITES, endpoint=False)
    pts = np.c_[np.interp(t, seg, c[:, 0]), np.interp(t, seg, c[:, 1])] * dx[:2]
    return pts, float(seg[-1] * dx[0])


def main(case, out, csv_path):
    T = {}
    t0 = time.perf_counter()
    ct, dx = load(os.path.join(TS, case, 'ct.nii.gz'))
    t5 = load(os.path.join(TS, case, 'segmentations', 'vertebrae_T5.nii.gz'))[0] > 0
    T['load_ct_s'] = time.perf_counter() - t0

    t0 = time.perf_counter()
    lab, body = label_map(case, ct)
    T['tissue_map_s'] = time.perf_counter() - t0

    t0 = time.perf_counter()
    zb = int(round(np.where(t5.any((0, 1)))[0].mean()))      # belt plane at mid-T5
    h = int(round(HALF_SLAB_M / dx[2]))
    z0, z1 = max(zb - h, 0), min(zb + h + 1, ct.shape[2])
    bb = np.where(body[:, :, z0:z1].any(2))
    x0, x1, y0, y1 = bb[0].min() - 2, bb[0].max() + 3, bb[1].min() - 2, bb[1].max() + 3
    x0, y0 = max(x0, 0), max(y0, 0)
    lab = lab[x0:x1, y0:y1, z0:z1]
    pts, circ = electrode_sites(lab[:, :, zb - z0] > 0, dx)
    sig, src = sigma_table(csv_path)
    T['crop_electrodes_s'] = time.perf_counter() - t0

    os.makedirs(os.path.join(out, 'cases', case), exist_ok=True)
    np.savez_compressed(os.path.join(out, 'cases', case, 'prep.npz'), lab=lab, dx=dx, belt_z=(zb - z0) * dx[2],
                        sites_xy=pts, sigma=sig)
    info = dict(case=case, shape=list(lab.shape), voxel_m=dx.tolist(), belt_slice=zb, circumference_m=circ,
                lung_L=float(np.isin(lab, [6, 7]).sum() * dx.prod() * 1e3), sigma_100kHz=dict(
                    (TISSUES[k][0], round(float(sig[k]), 5)) for k in TISSUES), sigma_source=src, timing=T)
    json.dump(info, open(os.path.join(out, 'cases', case, 'prep.json'), 'w'), indent=1)
    print(json.dumps(dict(case=case, **T, circ_m=round(circ, 3))))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
