"""Stage 3: complete electrode model (CEM) forward solves, adjoint Jacobian, ventilation/pathology states,
target images and forward-model checks for one anatomy.

Env: eit_petsc (real PETSc with MUMPS/CHOLMOD). Units SI. Currents are 1 A patterns (results are linear in I).
Writes <out>/cases/<case>/frames.npz and forward.json.
"""
import os, sys, json, time
import numpy as np
import scipy.sparse as sp
from scipy import ndimage
from petsc4py import PETSc

SEED = int(os.environ.get('SEED', 0))
N_STATES = int(os.environ.get('N_STATES', 10))
SOLVER = os.environ.get('SOLVER', 'mumps')
R_ELEC = 0.007                    # electrode patch radius (m)
Z_RANGE = (3e-4, 3e-3)            # contact impedance, log-uniform (Ohm m^2) -- demo choice, TBD in Phase 4
POS_ERR = 0.010                   # electrode position error along the belt, +-10 mm
SLAB = 0.02                       # target image slab half-width (m)
IMG = 64
PATHS = ['none', 'atelectasis', 'consolidation', 'effusion', 'pneumothorax', 'overdistension']
PATH_P = [0.4, 0.15, 0.15, 0.1, 0.05, 0.15]
BELTS = {'16_adjacent': (16, 1), '32_skip4': (32, 5)}
# barycentric sample points per tetrahedron: centroid, 4 vertex-leaning, 6 edge-leaning
SAMPLE_BARY = np.array([[0.25] * 4] + [[0.55 if i == v else 0.15 for i in range(4)] for v in range(4)] +
                       [[0.4 if i in (a, b) else 0.1 for i in range(4)] for a in range(4) for b in range(a + 1, 4)])


# ---------------------------------------------------------------- FEM pieces
def p1_geometry(nodes, tets):
    a = nodes[tets]
    D = np.stack([a[:, 1] - a[:, 0], a[:, 2] - a[:, 0], a[:, 3] - a[:, 0]], 1)    # E,3,3
    vol = np.abs(np.linalg.det(D)) / 6
    Dinv = np.linalg.inv(D)                                                        # columns: grads of l1..l3
    G = np.concatenate([-Dinv.sum(2, keepdims=True), Dinv], 2).transpose(0, 2, 1)  # E,4,3
    return G, vol


def stiffness(tets, G, vol, sig, n):
    Ke = np.einsum('eik,ejk->eij', G, G) * (vol * sig)[:, None, None]
    r = np.repeat(tets, 4, axis=1).ravel()
    c = np.tile(tets, (1, 4)).ravel()
    return sp.csr_matrix((Ke.ravel(), (r, c)), shape=(n, n))


def boundary_faces(tets):
    f = np.concatenate([tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]]])
    s = np.sort(f, 1)
    _, idx, cnt = np.unique(s, axis=0, return_index=True, return_counts=True)
    return f[idx[cnt == 1]]


def subtriangle_rule(n=8):
    """Barycentric centroids of the n*n congruent sub-triangles of a triangle (equal weights)."""
    q = []
    for i in range(n):
        for j in range(n - i):
            q.append(((i + 1 / 3) / n, (j + 1 / 3) / n))
            if i + j < n - 1:
                q.append(((i + 2 / 3) / n, (j + 2 / 3) / n))
    q = np.array(q)
    return np.c_[1 - q.sum(1), q], 1.0 / len(q)


QUAD_L, QUAD_W = subtriangle_rule()


def electrode_patches(nodes, bf, centres, shapes=None):
    """Electrode = exact region on the boundary, independent of the triangulation. Each boundary triangle near
    the electrode is integrated with the sub-triangle rule, keeping only quadrature points inside the region.
    Default region: disk of radius R_ELEC around the site snapped onto the surface."""
    cen = nodes[bf].mean(1)
    out = []
    for l, c in enumerate(centres):
        tri = bf[np.linalg.norm(cen - c, axis=1) < R_ELEC + 0.008]
        if len(tri) == 0:
            raise RuntimeError(f'no boundary face near electrode {l} at {c}')
        p = nodes[tri]
        qp = np.einsum('qi,tik->tqk', QUAD_L, p)                                  # T, Q, 3
        ar = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        if shapes is None:
            flat = qp.reshape(-1, 3)
            c0 = flat[np.argmin(np.linalg.norm(flat - c, axis=1))]                  # site snapped to surface
            inside = np.linalg.norm(qp - c0, axis=2) < R_ELEC
        else:
            inside = shapes[l](qp)
        w = ar[:, None] * QUAD_W * inside                                         # T, Q
        keep = w.sum(1) > 0
        out.append((tri[keep], w[keep]))
    return out


def cem_blocks(nodes, patches, z, n):
    """Electrode terms: sum_l M_l/z_l (N x N), C = -b_l/z_l (N x L), diag |e_l|/z_l."""
    rows, cols, vals = [], [], []
    C = np.zeros((n, len(patches)))
    area = np.zeros(len(patches))
    for l, (tri, w) in enumerate(patches):
        area[l] = w.sum()
        mloc = np.einsum('tq,qi,qj->tij', w, QUAD_L, QUAD_L)                      # int phi_i phi_j over patch
        bloc = w @ QUAD_L                                                         # int phi_i
        rows.append(np.repeat(tri, 3, 1).ravel()); cols.append(np.tile(tri, (1, 3)).ravel())
        vals.append((mloc / z[l]).ravel())
        np.add.at(C[:, l], tri.ravel(), -bloc.ravel() / z[l])
    M = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    return M, sp.csr_matrix(C), area / z, area


def cem_system(K, M, C, dg):
    """Full CEM matrix with the last electrode voltage grounded (U_L = 0), so it is SPD."""
    A = sp.bmat([[K + M, C[:, :-1]], [C[:, :-1].T, sp.diags(dg[:-1])]], format='csr')
    return A


class Assembler:
    """CEM matrix values for many conductivities on one mesh and electrode set. The CSR pattern (structural, so it
    never depends on values) and a sparse map from element conductivities to the stiffness values are built once;
    each assembly is then one sparse mat-vec plus the constant electrode terms."""
    def __init__(self, tets, G, vol, Me, C, dg, n, chunk=200000):
        E = len(tets)
        # node pattern from the unique tetrahedron edges (no 16-per-element temporaries)
        t = np.sort(tets, 1).astype(np.int64)
        und = np.unique((t[:, [0, 0, 0, 1, 1, 2]] * n + t[:, [1, 2, 3, 2, 3, 3]]).ravel())
        i, j, d = und // n, und % n, np.arange(n)
        del t, und
        Kp = sp.csr_matrix((np.ones(2 * len(i) + n, np.float32), (np.r_[i, j, d], np.r_[j, i, d])), shape=(n, n))
        del i, j
        one = lambda S: sp.csr_matrix((np.ones(S.nnz), S.nonzero()), shape=S.shape)
        Ap = cem_system(Kp, one(Me), one(sp.csr_matrix(C)), np.ones(len(dg)))
        del Kp
        Ap.sort_indices()
        self.indptr, self.indices, self.shape = Ap.indptr, Ap.indices, Ap.shape
        N = Ap.shape[0]
        key = np.repeat(np.arange(N, dtype=np.int64), np.diff(Ap.indptr)) * N + Ap.indices

        def pos(rr, cc):
            q = rr.astype(np.int64) * N + cc
            p = np.searchsorted(key, q)
            assert np.array_equal(key[np.minimum(p, len(key) - 1)], q), 'entry outside the CEM pattern'
            return p
        # map element conductivities -> matrix values, stored by element (CSC, 16 entries per column); a column's
        # entries are distinct positions, and the mat-vec sums each value in element order
        idx = np.empty(16 * E, np.int32)
        for s in range(0, E, chunk):
            tt = tets[s:s + chunk]
            idx[16 * s:16 * (s + len(tt))] = pos(np.repeat(tt, 4, axis=1).ravel(), np.tile(tt, (1, 4)).ravel())
        Ke0 = (np.einsum('eik,ejk->eij', G, G) * vol[:, None, None]).ravel()     # unit-conductivity element matrices
        self.P = sp.csc_matrix((Ke0, idx, np.arange(0, 16 * E + 1, 16, dtype=np.int32)), shape=(len(key), E))
        A0 = cem_system(sp.csr_matrix((n, n)), Me, C, dg).tocoo()
        self.const = np.bincount(pos(A0.row, A0.col), A0.data, len(key))

    def values(self, sig):
        return self.P @ sig + self.const

    def matrix(self, sig):
        return sp.csr_matrix((self.values(sig), self.indices, self.indptr), shape=self.shape)


class Solver:
    """Cholesky factor of the CEM matrix. refactor() takes new values on the same pattern and keeps the symbolic
    analysis (fill-reducing ordering), so many conductivities on one mesh share it. The PETSc matrix wraps
    self.data without copying."""
    def __init__(self, A):
        A = A.tocsr()
        A.sort_indices()
        self.n = A.shape[0]
        self.indptr, self.indices = A.indptr.astype(PETSc.IntType), A.indices.astype(PETSc.IntType)
        self.data = np.array(A.data, dtype=PETSc.ScalarType)
        self.M = PETSc.Mat().createAIJWithArrays(A.shape, (self.indptr, self.indices, self.data))
        self.M.setOption(PETSc.Mat.Option.SPD, True)
        self.ksp = PETSc.KSP().create()
        self.ksp.setOperators(self.M)
        self.ksp.setType('preonly')
        pc = self.ksp.getPC()
        pc.setType('cholesky')
        pc.setFactorSolverType(SOLVER)
        self.ksp.setUp()                                       # symbolic + numeric factorisation happen here

    def refactor(self, data):
        self.data[:] = data
        self.M.assemble()                                      # new matrix state, same nonzero pattern
        self.ksp.setOperators(self.M)
        self.ksp.setUp()                                       # numeric factorisation only

    def solve(self, rhs):
        """All right-hand sides in one multi-RHS triangular solve."""
        F = self.ksp.getPC().getFactorMatrix()
        B = PETSc.Mat().createDense(rhs.shape, array=np.asfortranarray(rhs, dtype=PETSc.ScalarType))
        X = PETSc.Mat().createDense(rhs.shape)
        X.setUp()
        F.matSolve(B, X)
        out = np.array(X.getDenseArray())
        B.destroy(); X.destroy()
        return out

    def destroy(self):
        self.ksp.destroy(); self.M.destroy()


def protocol(L, skip):
    drives = [(i, (i + skip) % L) for i in range(L)]
    meas = []
    for d, (a, b) in enumerate(drives):
        for m, (c, e) in enumerate(drives):
            if len({a, b} & {c, e}) == 0:
                meas.append((d, m))
    return drives, np.array(meas)


def drive_rhs(n, L, drives):
    R = np.zeros((n + L - 1, len(drives)))
    for k, (a, b) in enumerate(drives):
        for e, s in ((a, 1.0), (b, -1.0)):
            if e < L - 1:
                R[n + e, k] = s
    return R


def voltages(X, n, L):
    U = np.vstack([X[n:], np.zeros((1, X.shape[1]))])          # electrode voltages, U_L = 0
    return X[:n], U


def measure(U, drives, meas):
    d = np.array([U[drives[m][0], k] - U[drives[m][1], k] for k, m in meas])
    return d


# ---------------------------------------------------------------- physiological states on the voxel grid
def state_sigma(lab, sig, rng, kind):
    """Returns (sigma_ref, sigma_cur, description). Pathology is present in both frames; ventilation and
    cardiac change only in the current frame."""
    s = sig[lab].astype(np.float32)
    lung = np.isin(lab, [6, 7])
    vent = lung.astype(np.float32)
    ii, jj, kk = np.nonzero(lung)
    y = jj.astype(np.float32)
    yn = np.zeros(lab.shape, np.float32)
    yn[ii, jj, kk] = (y - y.min()) / max(np.ptp(y), 1)          # 0 dorsal ... 1 ventral (RAS: +y anterior)
    desc = dict(pathology=kind)
    side = int(rng.choice([6, 7]))
    if kind == 'atelectasis':
        f = rng.uniform(0.1, 0.3); m = lung & (yn < f); s[m] = 0.35; vent[m] = 0; desc['dorsal_fraction'] = f
    elif kind == 'consolidation':
        c = np.array([ii, jj, kk])[:, rng.integers(len(ii))]; r = rng.uniform(13, 27)  # voxels (~20-40 mm)
        g = np.ogrid[:lab.shape[0], :lab.shape[1], :lab.shape[2]]
        m = lung & ((g[0] - c[0]) ** 2 + (g[1] - c[1]) ** 2 + (g[2] - c[2]) ** 2 < r * r)
        s[m] = 0.5; vent[m] = 0; desc['radius_vox'] = r
    elif kind == 'effusion':
        f = rng.uniform(0.05, 0.2); m = (lab == side) & (yn < f); s[m] = 1.4; vent[m] = 0; desc['fraction'] = f
    elif kind == 'pneumothorax':
        f = rng.uniform(0.1, 0.2); m = (lab == side) & (yn > 1 - f); s[m] = 1e-3; vent[m] = 0; desc['fraction'] = f
    elif kind == 'overdistension':
        f = rng.uniform(0.2, 0.4); m = lung & (yn > 1 - f); s[m] *= 0.8; vent[m] *= 0.3; desc['fraction'] = f
    ref = s.copy()
    amp = rng.uniform(0.05, 0.25)                                # relative lung sigma drop at end-inspiration
    grav = 0.6 + 0.8 * (1 - yn)                                  # more ventilation in dependent (dorsal) lung
    cur = s * (1 - amp * vent * grav)
    heart = lab == 5
    card = rng.uniform(-0.05, 0.05)
    cur[heart] *= 1 + card
    desc.update(tidal_amp=amp, cardiac_rel=card)
    return ref, cur, desc


def image_frame(lab, dx, zb):
    k0, k1 = int((zb - SLAB) / dx[2]), int((zb + SLAB) / dx[2]) + 1
    body = (lab[:, :, k0:k1] > 0).any(2)
    ii, jj = np.nonzero(body)
    return k0, k1, (ii.min() * dx[0], (ii.max() + 1) * dx[0], jj.min() * dx[1], (jj.max() + 1) * dx[1])


def to_pixels(x, y, box):
    px = np.clip(((x - box[0]) / (box[1] - box[0]) * IMG).astype(int), 0, IMG - 1)
    py = np.clip(((y - box[2]) / (box[3] - box[2]) * IMG).astype(int), 0, IMG - 1)
    return px * IMG + py


def target_image(dsig, k0, k1, dx, box, lab):
    m = dsig[:, :, k0:k1].mean(2)
    inside = (lab[:, :, k0:k1] > 0).any(2)
    ii, jj = np.nonzero(inside)
    p = to_pixels(ii * dx[0], jj * dx[1], box)
    num = np.bincount(p, m[ii, jj], IMG * IMG); den = np.bincount(p, None, IMG * IMG)
    return (num / np.maximum(den, 1)).reshape(IMG, IMG).astype(np.float32)


# ---------------------------------------------------------------- main
def main(case, out):
    d = os.path.join(out, 'cases', case)
    T = {}
    rng = np.random.default_rng(SEED + int(case[1:]))
    P = np.load(os.path.join(d, 'prep.npz'))
    lab, dx, zb, sites_xy, sig = P['lab'], P['dx'], float(P['belt_z']), P['sites_xy'], P['sigma'].copy()
    for kv in filter(None, os.environ.get('SIGOVR', '').split(',')):   # diagnostic overrides "label=sigma,..."
        k, v = kv.split('=')
        sig[int(k)] = float(v)
    mesh_file = os.environ.get('MESH', 'mesh.npz')
    Mz = np.load(os.path.join(d, mesh_file))
    nodes, tets = Mz['nodes'], Mz['tets'].astype(np.int64)
    n = len(nodes)

    t0 = time.perf_counter()
    G, vol = p1_geometry(nodes, tets)
    cen = nodes[tets].mean(1)
    # element sigma = mean of the voxel map over 11 interior points (centroid first), so thin high-contrast
    # layers (subcutaneous fat, ribs) are represented consistently across mesh levels
    pts = np.einsum('kv,evd->ekd', SAMPLE_BARY, nodes[tets])
    vs = np.clip((pts / dx).astype(int), 0, np.array(lab.shape) - 1)
    # the smoothed surface pokes slightly outside the voxel body mask: use the nearest body voxel there
    near = ndimage.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
    vs = np.moveaxis(near[:, vs[..., 0], vs[..., 1], vs[..., 2]], 0, -1)            # E, K, 3
    del near, pts
    vox = vs[:, 0]

    def el_sigma(volmap):
        if os.environ.get('HOMOG'):                     # diagnostic: uniform thorax, isolates geometry/electrodes
            return np.full(len(tets), float(os.environ['HOMOG']))
        return volmap[vs[..., 0], vs[..., 1], vs[..., 2]].mean(1)
    bf = boundary_faces(tets)
    k0, k1, box = image_frame(lab, dx, zb)
    in_slab = np.abs(cen[:, 2] - zb) < SLAB
    pix = to_pixels(cen[in_slab, 0], cen[in_slab, 1], box)
    Pimg = sp.csr_matrix((np.ones(in_slab.sum()), (np.arange(in_slab.sum()), pix)), shape=(in_slab.sum(), IMG * IMG))
    T['geometry_s'] = time.perf_counter() - t0

    # belt sites in 3D with tangents for position error
    s3 = np.c_[sites_xy, np.full(len(sites_xy), zb)]
    tang = np.roll(s3, -1, 0) - np.roll(s3, 1, 0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)

    T['states_s'] = 0.0; T['targets_s'] = 0.0
    states = []
    for k in range(N_STATES):
        t0 = time.perf_counter()
        kind = str(rng.choice(PATHS, p=PATH_P))
        ref, cur, desc = state_sigma(lab, sig, rng, kind)
        T['states_s'] += time.perf_counter() - t0
        t0 = time.perf_counter()
        img = target_image(cur - ref, k0, k1, dx, box, lab)
        T['targets_s'] += time.perf_counter() - t0
        states.append((el_sigma(ref), el_sigma(cur), img, desc))

    res = dict(case=case, nodes=n, tets=len(tets), solver=SOLVER, n_states=N_STATES, belts={}, checks={})
    frames = {}
    for bname, (L, skip) in BELTS.items():
        B = dict(assembly_s=[], factor_s=[], solve_s=[], measure_s=[])
        idx = np.arange(0, 32, 32 // L)
        brng = np.random.default_rng([SEED, int(case[1:]), L])   # belt state independent of N_STATES
        cpos = s3[idx] + tang[idx] * brng.uniform(-POS_ERR, POS_ERR, (L, 1))
        z = np.exp(brng.uniform(np.log(Z_RANGE[0]), np.log(Z_RANGE[1]), L))
        patches = electrode_patches(nodes, bf, cpos)
        Me, C, dg, area = cem_blocks(nodes, patches, z, n)
        drives, meas = protocol(L, skip)
        R = drive_rhs(n, L, drives)
        V = []

        def forward(sig_el, keep=False):
            t0 = time.perf_counter(); A = cem_system(stiffness(tets, G, vol, sig_el, n), Me, C, dg)
            B['assembly_s'].append(time.perf_counter() - t0)
            t0 = time.perf_counter(); S = Solver(A); B['factor_s'].append(time.perf_counter() - t0)
            t0 = time.perf_counter(); X = S.solve(R); B['solve_s'].append(time.perf_counter() - t0)
            S.destroy()
            t0 = time.perf_counter(); u, U = voltages(X, n, L); v = measure(U, drives, meas)
            B['measure_s'].append(time.perf_counter() - t0)
            return (v, u, U, A) if keep else v

        # reference of the first state is used for the Jacobian and the checks
        v0, u0, U0, A0 = forward(states[0][0], keep=True)
        t0 = time.perf_counter()
        gu = np.einsum('eik,eip->ekp', G[in_slab], u0[tets[in_slab]])       # E_slab, 3, patterns
        Js = -np.einsum('ekp,ekq->epq', gu, gu) * vol[in_slab][:, None, None]   # E_slab x drive x drive
        Jm = np.stack([Js[:, a, b] for a, b in meas], 0)                        # M x E_slab
        J_img = (Pimg.T @ Jm.T).T.astype(np.float32)                             # M x 4096
        B['jacobian_s'] = time.perf_counter() - t0

        if bname == '16_adjacent':
            # current conservation: injected current recovered from the solution on every electrode
            cur = dg[:, None] * U0 + np.asarray(C.T @ u0)                          # L x patterns
            inj = np.zeros((L, len(drives)))
            for kk, (a, b) in enumerate(drives):
                inj[a, kk] += 1; inj[b, kk] -= 1
            res['checks']['current_conservation_max_abs_A'] = float(np.abs(cur - inj).max())
            res['checks']['current_sum_max_abs_A'] = float(np.abs(cur.sum(0)).max())
            # reciprocity: transfer impedance between drive pair d and measurement pair m
            Z = np.full((L, L), np.nan)
            for (dd, mm), val in zip(meas, v0):
                Z[dd, mm] = val
            ok = ~np.isnan(Z) & ~np.isnan(Z.T)
            res['checks']['reciprocity_max_rel'] = float(np.abs(Z - Z.T)[ok].max() / np.abs(Z[ok]).max())
            # Jacobian vs finite difference on a random lung blob inside the slab
            lung_slab = np.where(in_slab)[0][np.isin(lab[vox[in_slab, 0], vox[in_slab, 1], vox[in_slab, 2]], [6, 7])]
            c0 = cen[rng.choice(lung_slab)]
            blob = lung_slab[np.linalg.norm(cen[lung_slab] - c0, axis=1) < 0.02]
            dsig = np.zeros(len(tets)); dsig[blob] = 1e-3 * states[0][0][blob]
            v1 = forward(states[0][0] + dsig)
            pos = np.searchsorted(np.where(in_slab)[0], blob)
            lin = Jm[:, pos] @ dsig[blob]
            res['checks']['jacobian_fd_rel'] = float(np.linalg.norm(lin - (v1 - v0)) / np.linalg.norm(v1 - v0))
            res['checks']['jacobian_fd_blob_elements'] = int(len(blob))

        for k, (sref, scur, img, desc) in enumerate(states):
            vr = v0 if k == 0 else forward(sref)
            vc = forward(scur)
            V.append((vr, vc))
        frames[bname] = dict(v_ref=np.array([a for a, _ in V], np.float32), v_cur=np.array([b for _, b in V], np.float32),
                             J_img=J_img, z=z, area=area)
        res['belts'][bname] = dict(L=L, n_meas=len(meas), n_solves=len(B['factor_s']),
                                   electrode_area_mm2=[round(a * 1e6, 1) for a in area],
                                   **{k: (float(np.mean(v)) if isinstance(v, list) else v) for k, v in B.items()},
                                   factor_s_max=float(np.max(B['factor_s'])))
    res['timing'] = T
    res['states'] = [s[3] for s in states]
    if mesh_file == 'mesh.npz':
        np.savez_compressed(os.path.join(d, 'frames.npz'), images=np.stack([s[2] for s in states]),
                            **{f'{b}_{k}': v for b, f in frames.items() for k, v in f.items()})
    json.dump(res, open(os.path.join(d, 'forward' + ('' if mesh_file == 'mesh.npz' else '_' + mesh_file[:-4]) + '.json'), 'w'),
              indent=1, default=float)
    for b in frames:
        np.save(os.path.join(d, f'vref_{b}_{mesh_file[:-4]}.npy'), frames[b]['v_ref'][0])
        np.save(os.path.join(d, f'vcur_{b}_{mesh_file[:-4]}.npy'), frames[b]['v_cur'][0])
    print(json.dumps({k: res[k] for k in ('case', 'nodes', 'checks', 'timing')}, default=float))
    for b, r in res['belts'].items():
        print(b, {k: r[k] for k in r if k.endswith('_s') or k in ('n_solves', 'n_meas', 'factor_s_max')})


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
