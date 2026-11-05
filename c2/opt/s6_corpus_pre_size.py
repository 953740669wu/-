"""Stage 6: corpus of time-difference frame pairs (Phase 4 pilot and production).

Unit of work = (case, placement k, belt, contact state j): CFG['baselines'] baseline states (pathology drawn, shared
reference frame) x CFG['breaths'] current frames each (ventilation + cardiac change) = 100 pairs from 105 forward
solves. A unit is written atomically to parts/<unit>.npz + .json and skipped when present, so a crashed job resumes
without duplicating or skipping pairs. Every random draw is seeded by the unit's coordinates, never by run order.

Each belt placement (height and tilt) has its own level-D mesh, refined around the tilted belt plane:
  python s6_corpus.py placements <case> <out>     -> cases/<case>/placements.json, and the mesh commands to run
  python s6_corpus.py solve <case> <k> <belt> <out>
  python s6_corpus.py manifest <out>               -> manifest.csv from the part sidecars
Env: eit_petsc for solve; anaconda (gmsh) for the meshes.
"""
import os, sys, json, time, hashlib, resource
import numpy as np

CFG = dict(
    seed=2026,
    placements=2, contacts=5, baselines=5, breaths=20,       # per anatomy: 2 x 2 belts x 5 x 5 x 20 = 2,000 pairs
    belts={'16_adjacent': [16, 1], '32_skip4': [32, 5]},
    dz_m=[-0.02, 0.02],                  # belt height around mid-T5 (about one intercostal space each way)
    tilt_deg=[-10, 10],                  # rotation about the left-right axis
    pos_err_m=0.010,                     # electrode position error along the belt
    r_elec_m=0.007,
    z_range=[3e-4, 3e-3],                # contact impedance, log-uniform (Ohm m^2); design choice to confirm
    p_failed=0.05, failed_z_factor=1000.0,
    paths=['none', 'atelectasis', 'consolidation', 'effusion', 'pneumothorax', 'overdistension'],
    path_p=[0.4, 0.15, 0.15, 0.1, 0.05, 0.15],
    tidal=[0.05, 0.25], cardiac=[-0.05, 0.05],                # design choices to confirm
    slab_m=0.02, img=64,
    mesh=dict(H_BELT=0.0013, H_FAR=0.004, SUBDIV=1),
)
CFG.update(json.loads(os.environ.get('CFG_OVERRIDE', '{}')))    # e.g. a small smoke test; changes the hash
CFG_HASH = hashlib.sha1(json.dumps(CFG, sort_keys=True).encode()).hexdigest()[:10]
CODE_HASH = hashlib.sha1(open(__file__, 'rb').read()).hexdigest()[:10]


def case_id(case):
    return int(case[1:])


# ---------------------------------------------------------------- placements
def placement_planes(case, out):
    d = os.path.join(out, 'cases', case)
    P = np.load(os.path.join(d, 'prep.npz'))
    zb, cxy = float(P['belt_z']), P['sites_xy'].mean(0)
    rows = []
    for k in range(CFG['placements']):
        rng = np.random.default_rng([CFG['seed'], case_id(case), 101, k])
        dz = float(rng.uniform(*CFG['dz_m']))
        t = np.radians(rng.uniform(*CFG['tilt_deg']))
        n = np.array([0.0, -np.sin(t), np.cos(t)])            # axial plane rotated about the x (left-right) axis
        p0 = np.array([cxy[0], cxy[1], zb + dz])
        rows.append(dict(k=k, dz_m=dz, tilt_deg=float(np.degrees(t)), normal=n.tolist(), point=p0.tolist(),
                         d=float(n @ p0), mesh=f'mesh_p{k}'))
    json.dump(dict(case=case, config_hash=CFG_HASH, placements=rows), open(os.path.join(d, 'placements.json'), 'w'), indent=1)
    for r in rows:
        env = ' '.join(f'{a}={b}' for a, b in CFG['mesh'].items())
        print(f"{env} PLANE={','.join(f'{v:.9f}' for v in r['normal'] + [r['d']])} MESH_OUT={r['mesh']}")


def belt_loop(nodes, bf, n, d):
    """Closed polyline where the belt plane cuts the skin: chain the plane crossings of the boundary triangles and
    keep the longest loop. Ordered counter-clockwise seen from above, starting at the most anterior point."""
    sd = nodes @ n - d
    sd[sd == 0] = 1e-12
    e = np.sort(np.concatenate([bf[:, [0, 1]], bf[:, [1, 2]], bf[:, [2, 0]]]), 1)
    ue, inv = np.unique(e, axis=0, return_inverse=True)
    inv = inv.ravel().reshape(3, -1).T                                # face -> its 3 edge ids
    cross = np.sign(sd[ue[:, 0]]) != np.sign(sd[ue[:, 1]])
    a, b = sd[ue[:, 0]], sd[ue[:, 1]]
    w = np.where(cross, a / np.where(cross, a - b, 1), 0)
    pt = nodes[ue[:, 0]] + w[:, None] * (nodes[ue[:, 1]] - nodes[ue[:, 0]])
    fc = cross[inv]
    seg = np.array([inv[f][fc[f]] for f in np.where(fc.sum(1) == 2)[0]])    # each cut face joins two crossed edges
    nbr = {}
    for s0, s1 in seg:
        nbr.setdefault(s0, []).append(s1); nbr.setdefault(s1, []).append(s0)
    seen, loops = set(), []
    for start in nbr:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [x for x in nbr[cur] if x != prev]
            if not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            if cur in seen:
                break
            loop.append(cur); seen.add(cur)
        loops.append(loop)
    q = pt[max(loops, key=len)]
    e1 = np.array([1.0, 0, 0]); e2 = np.cross(n, e1); e2 /= np.linalg.norm(e2)
    xy = np.c_[q @ e1, q @ e2]
    if np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1]) < 0:
        q = q[::-1]
    return np.roll(q, -int(np.argmax(q[:, 1])), 0)


def loop_points(q, t):
    """Points at arc lengths t (wrapped) along the closed polyline q."""
    qq = np.vstack([q, q[:1]])
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(qq, axis=0), axis=1))]
    t = np.mod(t, s[-1])
    return np.stack([np.interp(t, s, qq[:, i]) for i in range(3)], 1), float(s[-1])


# ---------------------------------------------------------------- physiology on the voxel grid
def lung_coords(lab):
    lung = np.isin(lab, [6, 7])
    ii, jj, kk = np.nonzero(lung)
    yn = np.zeros(lab.shape, np.float32)
    yn[ii, jj, kk] = (jj - jj.min()) / max(np.ptp(jj), 1)        # 0 dorsal ... 1 ventral (RAS: +y anterior)
    return lung, (ii, jj, kk), yn


def baseline(lab, sig, rng, kind, lung, lidx, yn, lslab, plane_dist):
    """Pathology (present in reference and current frames). Returns sigma map, ventilation weight map, description.
    lslab: lung voxels (in lidx order) inside the target-image slab; plane_dist: their signed distance to the plane.
    Every pathology intersects the slab: the consolidation centre is a slab lung voxel, and the layer thresholds are
    fractions of the slab's dorsal-ventral (jj) extent (yn_s), applied to the whole lung as a continuous layer."""
    s = sig[lab].astype(np.float32)
    vent = lung.astype(np.float32)
    ii, jj, kk = lidx
    J = np.arange(lab.shape[1])[None, :, None]                   # jj index grid (dorsal -> ventral)
    desc = dict(pathology=kind)
    side = int(rng.choice([6, 7]))

    def slab_range(sel):                                          # jj extent of the slab's lung voxels in sel
        js = jj[lslab & sel] if (lslab & sel).any() else jj[sel]
        desc['slab_empty'] = not (lslab & sel).any()
        return float(js.min()), float(max(np.ptp(js), 1))

    def layer(sel, f, below):                                      # slab-normalized threshold yn_s -> jj index
        j0, w = slab_range(sel)
        yt = f if below else 1 - f
        jt = j0 + yt * w
        desc['threshold_yn_s'] = float(yt); desc['threshold_jj'] = float(jt)
        return (J < jt) if below else (J > jt)
    alls = np.ones(len(ii), bool)
    sides = lab[ii, jj, kk] == side
    if kind == 'atelectasis':
        f = rng.uniform(0.1, 0.3); m = lung & layer(alls, f, True); s[m] = 0.35; vent[m] = 0
        desc['dorsal_fraction'] = f
    elif kind == 'consolidation':
        cand = np.nonzero(lslab)[0] if lslab.any() else np.arange(len(ii))
        q = cand[rng.integers(len(cand))]
        c = np.array([ii[q], jj[q], kk[q]]); r = rng.uniform(13, 27)   # voxels (~20-40 mm)
        g = np.ogrid[:lab.shape[0], :lab.shape[1], :lab.shape[2]]
        m = lung & ((g[0] - c[0]) ** 2 + (g[1] - c[1]) ** 2 + (g[2] - c[2]) ** 2 < r * r)
        s[m] = 0.5; vent[m] = 0; desc['radius_vox'] = r
        desc['centre_plane_dist_m'] = float(plane_dist[q]); desc['slab_empty'] = not lslab.any()
    elif kind == 'effusion':
        f = rng.uniform(0.05, 0.2); m = (lab == side) & layer(sides, f, True); s[m] = 1.4; vent[m] = 0
        desc['fraction'] = f
    elif kind == 'pneumothorax':
        f = rng.uniform(0.1, 0.2); m = (lab == side) & layer(sides, f, False); s[m] = 1e-3; vent[m] = 0
        desc['fraction'] = f
    elif kind == 'overdistension':
        f = rng.uniform(0.2, 0.4); m = lung & layer(alls, f, False); s[m] *= 0.8; vent[m] *= 0.3
        desc['fraction'] = f
    if kind in ('effusion', 'pneumothorax'):
        desc['side'] = 'left' if side == 6 else 'right'
    return s, vent * (0.6 + 0.8 * (1 - yn)), desc                  # ventilation weight keeps the global yn


def breath(s, ventw, heart, rng):
    amp = float(rng.uniform(*CFG['tidal'])); card = float(rng.uniform(*CFG['cardiac']))
    cur = s * (1 - amp * ventw)
    cur[heart] *= 1 + card
    return cur, dict(tidal_amp=amp, cardiac_rel=card)


# ---------------------------------------------------------------- one (case, placement, belt) job
def solve(case, k, belt, out):
    import scipy.sparse as sp
    from scipy import ndimage
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import s3_forward as F
    F.R_ELEC = CFG['r_elec_m']
    d = os.path.join(out, 'cases', case)
    parts = os.path.join(out, 'parts'); os.makedirs(parts, exist_ok=True)
    L, skip = CFG['belts'][belt]
    pl = json.load(open(os.path.join(d, 'placements.json')))['placements'][k]
    n_pl, d_pl = np.array(pl['normal']), pl['d']
    todo = [j for j in range(CFG['contacts'])
            if not os.path.exists(os.path.join(parts, f'{case}_p{k}_{belt}_c{j}.json'))]
    if not todo:
        print('nothing to do'); return

    t0 = time.perf_counter()
    P = np.load(os.path.join(d, 'prep.npz'))
    lab, dx, sig = P['lab'], P['dx'], P['sigma']
    Mz = np.load(os.path.join(d, pl['mesh'] + '.npz'))
    nodes, tets = Mz['nodes'], Mz['tets'].astype(np.int64)
    nn = len(nodes)
    G, vol = F.p1_geometry(nodes, tets)
    cen = nodes[tets].mean(1)
    pts = np.einsum('kv,evd->ekd', F.SAMPLE_BARY, nodes[tets])
    vs = np.clip((pts / dx).astype(int), 0, np.array(lab.shape) - 1)
    near = ndimage.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
    vs = np.moveaxis(near[:, vs[..., 0], vs[..., 1], vs[..., 2]], 0, -1).astype(np.int16)   # E, 11, 3
    del near, pts
    el_sigma = lambda volmap: volmap[vs[..., 0], vs[..., 1], vs[..., 2]].mean(1)
    bf = F.boundary_faces(tets)
    loop = belt_loop(nodes, bf, n_pl, d_pl)

    # target image: body voxels within +-slab of the belt plane, binned by (x, y) into a body-normalized 64x64 box
    IMG = CFG['img']
    ijk = np.nonzero(lab > 0)
    xyz = (np.stack(ijk, 1) + 0.5) * dx
    sl = np.abs(xyz @ n_pl - d_pl) < CFG['slab_m']
    vflat = np.ravel_multi_index(tuple(a[sl] for a in ijk), lab.shape)
    box = (xyz[sl, 0].min(), xyz[sl, 0].max(), xyz[sl, 1].min(), xyz[sl, 1].max())

    def to_pixels(x, y):
        px = np.clip(((x - box[0]) / (box[1] - box[0]) * IMG).astype(int), 0, IMG - 1)
        py = np.clip(((y - box[2]) / (box[3] - box[2]) * IMG).astype(int), 0, IMG - 1)
        return px * IMG + py
    vpix = to_pixels(xyz[sl, 0], xyz[sl, 1])
    vden = np.bincount(vpix, None, IMG * IMG)
    img_mask = (vden > 0).reshape(IMG, IMG)
    del xyz, ijk
    target = lambda dsig: (np.bincount(vpix, dsig.ravel()[vflat], IMG * IMG) / np.maximum(vden, 1)).reshape(IMG, IMG)
    eslab = np.where(np.abs(cen @ n_pl - d_pl) < CFG['slab_m'])[0]
    Pimg = sp.csr_matrix((np.ones(len(eslab)), (np.arange(len(eslab)), to_pixels(cen[eslab, 0], cen[eslab, 1]))),
                         shape=(len(eslab), IMG * IMG))
    lung, lidx, yn = lung_coords(lab)
    plane_dist = (np.stack(lidx, 1) + 0.5) * dx @ n_pl - d_pl      # lung voxels' signed distance to the plane
    lslab = np.abs(plane_dist) < CFG['slab_m']                     # same slab as the target image
    heart = lab == 5
    setup_s = time.perf_counter() - t0
    peak_gb = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    rss = dict(after_setup=peak_gb())

    drives, meas = F.protocol(L, skip)
    R = F.drive_rhs(nn, L, drives)
    for j in todo:
        uid = f'{case}_p{k}_{belt}_c{j}'
        T = dict(setup_s=setup_s, assembly_s=0.0, factor_s=0.0, solve_s=0.0, states_s=0.0, targets_s=0.0)
        tu = time.perf_counter()
        rng = np.random.default_rng([CFG['seed'], case_id(case), 202, k, L, j])
        z = np.exp(rng.uniform(np.log(CFG['z_range'][0]), np.log(CFG['z_range'][1]), L))
        failed = int(rng.integers(L)) if rng.random() < CFG['p_failed'] else -1
        if failed >= 0:
            z[failed] *= CFG['failed_z_factor']
        per = loop_points(loop, np.zeros(1))[1]
        tpos = np.arange(L) / L * per + rng.uniform(-CFG['pos_err_m'], CFG['pos_err_m'], L)
        centres, _ = loop_points(loop, tpos)
        patches = F.electrode_patches(nodes, bf, centres)
        Me, C, dg, area = F.cem_blocks(nodes, patches, z, nn)
        # the unit's 105 matrices share one pattern: assembly map and symbolic factorisation are built once
        t = time.perf_counter(); asm = F.Assembler(tets, G, vol, Me, C, dg, nn); T['assembly_map_s'] = time.perf_counter() - t
        rss.setdefault('after_assembly_map', peak_gb())
        S = None

        def forward(sig_el, keep=False):
            nonlocal S
            t = time.perf_counter(); data = asm.values(sig_el); T['assembly_s'] += time.perf_counter() - t
            t = time.perf_counter()
            if S is None:
                S = F.Solver(sp.csr_matrix((data, asm.indices, asm.indptr), shape=asm.shape))
                T['factor_first_s'] = time.perf_counter() - t
                rss.setdefault('after_first_factor', peak_gb())
            else:
                S.refactor(data)
            T['factor_s'] += time.perf_counter() - t
            t = time.perf_counter(); X = S.solve(R); T['solve_s'] += time.perf_counter() - t
            u, U = F.voltages(X, nn, L)
            v = F.measure(U, drives, meas)
            return (v, u, U) if keep else v

        nb, nt = CFG['baselines'], CFG['breaths']
        v_ref = np.zeros((nb, len(meas)), np.float32); v_cur = np.zeros((nb * nt, len(meas)), np.float32)
        images = np.zeros((nb * nt, IMG, IMG), np.float32)
        states, checks = [], {}
        for b in range(nb):
            rb = np.random.default_rng([CFG['seed'], case_id(case), 303, k, L, j, b])
            t = time.perf_counter()
            kind = str(rb.choice(CFG['paths'], p=CFG['path_p']))
            s, ventw, desc = baseline(lab, sig, rb, kind, lung, lidx, yn, lslab, plane_dist)
            sref = el_sigma(s)
            T['states_s'] += time.perf_counter() - t
            if b == 0:
                v0, u0, U0 = forward(sref, keep=True)
                v_ref[b] = v0
                cur = dg[:, None] * U0 + np.asarray(C.T @ u0)
                inj = np.zeros((L, len(drives)))
                for kk, (a, c) in enumerate(drives):
                    inj[a, kk] += 1; inj[c, kk] -= 1
                checks['current_conservation_max_abs_A'] = float(np.abs(cur - inj).max())
                Z = np.full((L, L), np.nan)
                for (dd, mm), val in zip(meas, v0):
                    Z[dd, mm] = val
                ok = ~np.isnan(Z) & ~np.isnan(Z.T)
                checks['reciprocity_max_rel'] = float(np.abs(Z - Z.T)[ok].max() / np.abs(Z[ok]).max())
                # Jacobian of the baseline-0 reference, projected to image pixels, in chunks of measurements; stored
                # once per (case, placement, belt), in the contact-0 unit, to keep the corpus small for transfer
                J = None
            if b == 0 and j == 0:
                t = time.perf_counter()
                gu = np.einsum('eik,eip->ekp', G[eslab], u0[tets[eslab]])
                J = np.zeros((len(meas), IMG * IMG), np.float32)
                for c0 in range(0, len(meas), 16):                  # 16 measurements per chunk bounds peak memory
                    mm = meas[c0:c0 + 16]
                    Je = -(gu[:, :, mm[:, 0]] * gu[:, :, mm[:, 1]]).sum(1) * vol[eslab][:, None]
                    J[c0:c0 + 16] = np.asarray(Pimg.T @ Je).T
                del gu
                T['jacobian_s'] = time.perf_counter() - t
                rss.setdefault('after_jacobian', peak_gb())
            if b > 0:
                v_ref[b] = forward(sref)
            for i in range(nt):
                t = time.perf_counter()
                c, bd = breath(s, ventw, heart, rb)
                scur = el_sigma(c)
                T['states_s'] += time.perf_counter() - t
                t = time.perf_counter()
                images[b * nt + i] = target(c - s)
                T['targets_s'] += time.perf_counter() - t
                v_cur[b * nt + i] = forward(scur)
                states.append(dict(baseline=b, **desc, **bd))
        rss.setdefault('after_states', peak_gb())
        S.destroy(); del asm
        finite = bool(np.isfinite(v_ref).all() and np.isfinite(v_cur).all() and np.isfinite(images).all()
                      and (J is None or np.isfinite(J).all()))
        T['unit_wall_s'] = time.perf_counter() - tu
        info = dict(unit=uid, case=case, placement=k, dz_m=pl['dz_m'], tilt_deg=pl['tilt_deg'], belt=belt, L=L,
                    contact=j, n_pairs=nb * nt, n_solves=nb * (nt + 1), failed_electrode=failed,
                    z_ohm_m2=z.tolist(), electrode_area_mm2=[round(a * 1e6, 1) for a in area],
                    belt_perimeter_m=per, nodes=nn, tets=len(tets), checks=checks, finite=finite, timing=T,
                    peak_rss_gb=peak_gb(), peak_rss_checkpoints_gb=rss,
                    config_hash=CFG_HASH, code_hash=CODE_HASH, states=states)
        tmp = os.path.join(parts, uid + '.tmp.npz')
        jac = {} if J is None else dict(J_img=(J / np.abs(J).max()).astype(np.float16), J_scale=np.float32(np.abs(J).max()))
        np.savez_compressed(tmp, v_ref=v_ref, v_cur=v_cur, base_of_pair=np.repeat(np.arange(nb), nt).astype(np.int8),
                            images=images.astype(np.float16), img_mask=img_mask, box=np.array(box), z=z, failed=failed,
                            centres=centres, area=area, drives=np.array(drives, np.int16), meas=meas.astype(np.int16), **jac)
        os.replace(tmp, os.path.join(parts, uid + '.npz'))
        json.dump(info, open(os.path.join(parts, uid + '.tmp.json'), 'w'), indent=1, default=float)
        os.replace(os.path.join(parts, uid + '.tmp.json'), os.path.join(parts, uid + '.json'))   # json last = done
        print(json.dumps({x: info[x] for x in ('unit', 'checks', 'finite', 'nodes')}),
              {x: round(v, 1) for x, v in T.items()}, flush=True)


def manifest(out):
    import glob, csv
    rows = []
    for f in sorted(glob.glob(os.path.join(out, 'parts', '*.json'))):
        if f.endswith('.tmp.json'):
            continue
        r = json.load(open(f))
        kinds = [s['pathology'] for s in r['states'][::CFG['breaths']]]
        rows.append(dict(unit=r['unit'], case=r['case'], placement=r['placement'], belt=r['belt'], contact=r['contact'],
                         n_pairs=r['n_pairs'], dz_m=round(r['dz_m'], 4), tilt_deg=round(r['tilt_deg'], 2),
                         failed_electrode=r['failed_electrode'], baselines=';'.join(kinds), nodes=r['nodes'],
                         conservation=r['checks']['current_conservation_max_abs_A'],
                         reciprocity=r['checks']['reciprocity_max_rel'], finite=r['finite'],
                         unit_wall_s=round(r['timing']['unit_wall_s'], 1), peak_rss_gb=round(r['peak_rss_gb'], 2),
                         config_hash=r['config_hash'], code_hash=r['code_hash'], status='done',
                         file=os.path.basename(f)[:-5] + '.npz'))
    with open(os.path.join(out, 'manifest.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(len(rows), 'units,', sum(r['n_pairs'] for r in rows), 'pairs')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'placements':
        placement_planes(sys.argv[2], sys.argv[3])
    elif cmd == 'solve':
        solve(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5])
    elif cmd == 'manifest':
        manifest(sys.argv[2])
