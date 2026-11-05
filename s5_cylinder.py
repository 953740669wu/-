"""Homogeneous cylinder test: 3D CEM FEM (s3_forward) vs a semi-analytic 2D CEM reference.

Electrodes span the full cylinder height and the ends are insulated, so the 3D field does not depend on z and
equals the 2D disk solution with current I/H. The 2D reference represents the boundary current density g as
piecewise constant on fine sub-arcs of each electrode; the disk Neumann-to-Dirichlet map is applied with the
Fourier series in closed form per sub-arc (truncated at N_SERIES terms, error O(1/N)).

Usage:  mesh  (anaconda env, gmsh)      python s5_cylinder.py mesh  <out> <h>
        solve (eit_petsc env)           python s5_cylinder.py solve <out> <h>
"""
import os, sys, json, time
import numpy as np

R, H, SIG, L, Z = 0.15, 0.10, 1.0, 16, 0.01      # m, m, S/m, electrodes, Ohm m^2
W = 0.02                                          # electrode width along the boundary (m)
N_SUB, N_SERIES = 40, 5000


def mesh(out, h):
    import gmsh
    gmsh.initialize(); gmsh.option.setNumber('General.Terminal', 0)
    gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, H, R); gmsh.model.occ.synchronize()
    gmsh.option.setNumber('Mesh.MeshSizeMax', h); gmsh.option.setNumber('Mesh.MeshSizeMin', h)
    gmsh.option.setNumber('Mesh.Algorithm3D', 10)
    gmsh.model.mesh.generate(3)
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    _, en = gmsh.model.mesh.getElementsByType(4)
    gmsh.finalize()
    idx = np.full(int(tags.max()) + 1, -1); idx[tags.astype(int)] = np.arange(len(tags))
    tets = idx[en.astype(int).reshape(-1, 4)]
    used = np.unique(tets); remap = np.full(len(tags), -1); remap[used] = np.arange(len(used))
    np.savez(os.path.join(out, f'cyl_mesh_{h}.npz'), nodes=xyz.reshape(-1, 3)[used], tets=remap[tets])


def reference_2d():
    """Semi-analytic 2D CEM on the disk; returns electrode voltages for each adjacent drive (1 A per H)."""
    half = W / 2 / R
    centres = 2 * np.pi * np.arange(L) / L
    edges = np.stack([np.linspace(c - half, c + half, N_SUB + 1) for c in centres])  # L, N_SUB+1
    a, b = edges[:, :-1].ravel(), edges[:, 1:].ravel()                               # sub-arc ends
    th = (a + b) / 2
    n = np.arange(1, N_SERIES + 1)
    K = np.zeros((len(th), len(th)))
    for k in range(len(th)):                     # u(th_k) = R/(pi sig) sum_n 1/n^2 [sin n(th-a) - sin n(th-b)] g
        K[k] = (np.sin(np.outer(th[k] - a, n)) - np.sin(np.outer(th[k] - b, n))) @ (1 / n ** 2)
    K *= R / (np.pi * SIG)
    ns = len(th)
    A = np.zeros((ns + L + 1, ns + L))
    A[:ns, :ns] = K + Z * np.eye(ns)
    elec = np.repeat(np.arange(L), N_SUB)
    A[np.arange(ns), ns + elec] = -1                                                # u + z g - U_l = 0
    A[ns + elec, np.arange(ns)] = R * (b - a)                                       # sum g ds = I_l
    A[ns + L, ns:] = 1                                                              # sum U = 0
    V = []
    for d in range(L):
        rhs = np.zeros(ns + L + 1)
        rhs[ns + d] = 1 / H; rhs[ns + (d + 1) % L] = -1 / H
        V.append(np.linalg.lstsq(A, rhs, rcond=None)[0][ns:])
    return np.array(V).T                                                            # L x drives


def solve(out, h):
    sys.path.insert(0, os.path.dirname(__file__))
    import s3_forward as F
    m = np.load(os.path.join(out, f'cyl_mesh_{h}.npz'))
    nodes, tets = m['nodes'], m['tets'].astype(np.int64); n = len(nodes)
    G, vol = F.p1_geometry(nodes, tets)
    bf = F.boundary_faces(tets)
    ang = 2 * np.pi * np.arange(L) / L

    def strip(c):
        def f(q):
            rr = np.hypot(q[..., 0], q[..., 1])
            dphi = np.angle(np.exp(1j * (np.arctan2(q[..., 1], q[..., 0]) - c)))
            return (np.abs(dphi) * R < W / 2) & (rr > R - 1e-4)    # lateral surface only
        return f
    # strips span the full height, so integrate over all lateral faces rather than a disk neighbourhood
    cen = nodes[bf].mean(1)
    lat = bf[np.hypot(cen[:, 0], cen[:, 1]) > R - 0.01]
    pw = []
    for l in range(L):
        p = nodes[lat]
        qp = np.einsum('qi,tik->tqk', F.QUAD_L, p)
        ar = 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        w = ar[:, None] * F.QUAD_W * strip(ang[l])(qp)
        k = w.sum(1) > 0
        pw.append((lat[k], w[k]))
    z = np.full(L, Z)
    Me, C, dg, area = F.cem_blocks(nodes, pw, z, n)
    drives, meas = F.protocol(L, 1)
    t0 = time.perf_counter()
    A = F.cem_system(F.stiffness(tets, G, vol, np.full(len(tets), SIG), n), Me, C, dg)
    S = F.Solver(A); X = S.solve(F.drive_rhs(n, L, drives)); S.destroy()
    _, U = F.voltages(X, n, L)
    t_fem = time.perf_counter() - t0
    v_fem = F.measure(U, drives, meas)
    t0 = time.perf_counter()
    Uref = reference_2d()
    v_ref = F.measure(Uref, drives, meas)
    t_ref = time.perf_counter() - t0
    res = dict(h=h, nodes=n, tets=len(tets), electrode_area_mm2_mean=float(area.mean() * 1e6),
               electrode_area_exact_mm2=W * H * 1e6, rel_l2=float(np.linalg.norm(v_fem - v_ref) / np.linalg.norm(v_ref)),
               max_rel=float(np.abs(v_fem - v_ref).max() / np.abs(v_ref).max()), fem_s=t_fem, ref_s=t_ref)
    json.dump(res, open(os.path.join(out, f'cylinder_{h}.json'), 'w'), indent=1)
    print(json.dumps(res))


if __name__ == '__main__':
    {'mesh': mesh, 'solve': solve}[sys.argv[1]](sys.argv[2], float(sys.argv[3]))
