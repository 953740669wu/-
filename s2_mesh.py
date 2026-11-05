"""Stage 2: body mask of the crop -> closed surface -> gmsh tetrahedral mesh refined along the belt band.

Writes <out>/cases/<case>/mesh.npz (nodes in metres, tets) and mesh.json (timing, size, quality).
With VOLUME_ONLY=1 the surface step is skipped and <MESH_OUT>_body.stl, written by an earlier run, is meshed as is;
that step needs only numpy and gmsh, so it runs on hosts without the surface tools (the C2 cluster).
With SURFACE_ONLY=1 the run stops after body_base.stl/.json (kept if already present; surface_s and host are
added to body_base.json when it is created), for making surfaces on a host with the surface tools.
"""
import os, sys, json, time, platform
import numpy as np
import gmsh

VOLUME_ONLY = os.environ.get('VOLUME_ONLY', '0') == '1'
SURFACE_ONLY = os.environ.get('SURFACE_ONLY', '0') == '1'   # stop after body_base.stl/.json (no volume mesh)
assert not (VOLUME_ONLY and SURFACE_ONLY), 'VOLUME_ONLY and SURFACE_ONLY are exclusive'
try:
    from scipy import ndimage
    from skimage import measure
    import pyvista as pv, pymeshfix
except ImportError:
    if not VOLUME_ONLY:
        raise
GMSH_THREADS = int(os.environ.get('GMSH_THREADS', 4))
GMSH_VERBOSE = os.environ.get('GMSH_VERBOSE', '0') == '1'

H_BELT = float(os.environ.get('H_BELT', 0.0013))   # element size at the belt plane (m); defaults are level D
H_FAR = float(os.environ.get('H_FAR', 0.004))      # element size far from the belt (m)
GRADE = 0.25                                       # size growth per metre away from the belt plane
SURF_VOX = float(os.environ.get('SURF_VOX', 0.0025))  # surface triangle scale of the base surface (m)
SUBDIV = int(os.environ.get('SUBDIV', 1))              # linear subdivisions of the base surface for this level
# belt plane n.x = d as "nx,ny,nz,d" (unit normal, metres); default: the axial plane at the prepared belt height
PLANE = os.environ.get('PLANE', '')
MESH_OUT = os.environ.get('MESH_OUT', 'mesh')          # writes <MESH_OUT>.npz / .json in the case folder
# skin refinement in the belt band (off when BAND = 0): surface and near-skin elements of size H_SKIN within
# |z - zb| < BAND, growing by SKIN_GRADE per metre inward from the skin and by Z_GRADE per metre beyond the band
BAND = float(os.environ.get('BAND', 0))
H_SKIN = float(os.environ.get('H_SKIN', 0.0018))
SKIN_GRADE = float(os.environ.get('SKIN_GRADE', 0.2))
Z_GRADE = float(os.environ.get('Z_GRADE', 0.25))


def skin_size(z, zb):
    return H_SKIN + Z_GRADE * np.maximum(0, np.abs(z - zb) - BAND)


def refine_band(p, f, zb):
    """Conforming longest-edge bisection of the surface triangles until every edge is shorter than skin_size().
    New points are edge midpoints of flat triangles, so the surface, and the domain, are unchanged."""
    while True:
        e = np.sort(np.stack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], 1), axis=2)
        ue, inv = np.unique(e.reshape(-1, 2), axis=0, return_inverse=True)
        inv = inv.reshape(-1, 3)
        L = np.linalg.norm(p[ue[:, 0]] - p[ue[:, 1]], axis=1)
        mark = L > skin_size((p[ue[:, 0], 2] + p[ue[:, 1], 2]) / 2, zb)
        if not mark.any():
            return p, f
        k = np.argmax(L[inv], 1)                                  # local index of each triangle's longest edge
        longest = inv[np.arange(len(f)), k]
        while True:                                               # closure: a split triangle splits its longest edge
            need = mark[inv].any(1) & ~mark[longest]
            if not need.any():
                break
            mark[longest[need]] = True
        mid = np.full(len(ue), -1, np.int64)
        mid[mark] = len(p) + np.arange(mark.sum())
        p = np.vstack([p, (p[ue[mark, 0]] + p[ue[mark, 1]]) / 2])
        r = (k[:, None] + np.arange(3)) % 3                       # rotate so the longest edge is a-b
        a, b, c = (np.take_along_axis(f, r, 1)[:, i] for i in range(3))
        m0, m1, m2 = (mid[np.take_along_axis(inv, r, 1)[:, i]] for i in range(3))   # midpoints of ab, bc, ca
        s = m0 >= 0
        new = [f[~s]]
        for sel, tri in (((m2 < 0), (a, m0, c)), ((m2 >= 0), (a, m0, m2)), ((m2 >= 0), (m0, c, m2)),
                         ((m1 < 0), (m0, b, c)), ((m1 >= 0), (m0, b, m1)), ((m1 >= 0), (m0, m1, c))):
            sel = s & sel
            new.append(np.stack([t[sel] for t in tri], 1))
        f = np.vstack(new)


def read_stl(path):
    """Binary STL -> points, triangles (vertices shared by exact coordinates)."""
    rec = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    with open(path, 'rb') as fh:
        fh.seek(80)
        n = int(np.frombuffer(fh.read(4), '<u4')[0])
        v = np.frombuffer(fh.read(n * rec.itemsize), rec)['v'].reshape(-1, 3)
    p, inv = np.unique(v, axis=0, return_inverse=True)
    return p.astype(float), inv.ravel().reshape(-1, 3).astype(np.int64)


def write_stl(path, p, f):
    rec = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
    t = p[f]
    r = np.zeros(len(f), rec)
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    r['n'] = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-30)
    r['v'] = t
    with open(path, 'wb') as fh:
        fh.write(b'\0' * 80)
        fh.write(np.uint32(len(f)).tobytes())
        fh.write(r.tobytes())


def subdivide_linear(p, f, n):
    """Each triangle -> 4 at its edge midpoints, n times (the same surface as VTK's linear subdivision)."""
    for _ in range(n):
        e = np.sort(np.stack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], 1), axis=2)
        ue, inv = np.unique(e.reshape(-1, 2), axis=0, return_inverse=True)
        m = len(p) + inv.reshape(-1, 3)                          # midpoints of ab, bc, ca
        p = np.vstack([p, (p[ue[:, 0]] + p[ue[:, 1]]) / 2])
        a, b, c = f.T
        f = np.vstack([np.c_[a, m[:, 0], m[:, 2]], np.c_[m[:, 0], b, m[:, 1]], np.c_[m[:, 2], m[:, 1], c],
                       np.c_[m[:, 0], m[:, 1], m[:, 2]]])
    return p, f


GAP_MIN = 0.003           # smallest allowed gap between facing parts of the skin (m)
# closing radii tried in turn until the gap is open, in voxels (0: two iterations of the default cross). Default: no
# extra closing, the case is only flagged (gap_ok false in body_base.json) for review, because closing fuses arms
# to the torso (s0946: +12% volume at 4 voxels)
CLOSE_R = tuple(int(r) for r in os.environ.get('CLOSE_R', '0').split(','))


def body_surface(lab, dx, r):
    if r:
        z, y, x = np.ogrid[-r:r + 1, -r:r + 1, -r:r + 1]
        body = ndimage.binary_closing(lab > 0, structure=x * x + y * y + z * z <= r * r)
    else:
        body = ndimage.binary_closing(lab > 0, iterations=2)
    f = dx / SURF_VOX
    small = ndimage.zoom(body.astype(np.float32), f, order=1) > 0.5
    small = np.pad(small, 1)                               # pad so the crop ends are capped
    sp = dx / f
    v, fc, _, _ = measure.marching_cubes(small.astype(np.float32), 0.5, spacing=tuple(sp))
    v -= sp                                                # undo the pad offset
    surf = pv.PolyData(v, np.c_[np.full(len(fc), 3), fc].ravel()).smooth_taubin(n_iter=30, pass_band=0.1)
    fix = pymeshfix.MeshFix(surf.points, surf.faces.reshape(-1, 4)[:, 1:])
    fix.repair()
    return pv.PolyData(fix.points, np.c_[np.full(len(fix.faces), 3), fix.faces].ravel())


def min_gap(surf):
    """Smallest distance from a surface point to a nearby point whose normal faces it (a nearly closed fold)."""
    from scipy.spatial import cKDTree
    p = np.asarray(surf.points)
    n = np.asarray(surf.compute_normals(cell_normals=False, point_normals=True)['Normals'])
    dist, i = cKDTree(p).query(p, k=40)
    facing = np.einsum('ij,ikj->ik', n, n[i]) < -0.5
    return float(np.where(facing, dist, np.inf).min())


def main(case, out):
    d = os.path.join(out, 'cases', case)
    P = np.load(os.path.join(d, 'prep.npz'))
    lab, dx, zb = P['lab'], P['dx'], float(P['belt_z'])
    T = {}

    stl = os.path.join(d, MESH_OUT + '_body.stl')        # per output, so meshes of one case can run in parallel
    # one body surface per case; finer mesh levels only split its triangles (linear subdivision keeps the
    # geometry identical), so a convergence study compares discretisations of the same domain
    base = os.path.join(d, 'body_base.stl')
    t0 = time.perf_counter()
    if VOLUME_ONLY:                                       # body_base.stl comes from a host with the surface tools
        p, f = subdivide_linear(*read_stl(base), SUBDIV)
        if BAND:
            p, f = refine_band(p, f, zb)
        write_stl(stl, p, f)
        T['surface_s'] = time.perf_counter() - t0
    else:
        if not os.path.exists(base):
            # skin folds that nearly close (gap < GAP_MIN) fill with sliver tetrahedra
            for r in CLOSE_R:
                surf = body_surface(lab, dx, r)
                gap = min_gap(surf)
                if gap >= GAP_MIN:
                    break
            surf.save(base)
            info = dict(close_radius_vox=r, min_gap_mm=gap * 1e3, gap_ok=bool(gap >= GAP_MIN))
            if SURFACE_ONLY:
                info.update(surface_s=time.perf_counter() - t0, host=platform.node())
            json.dump(info, open(os.path.join(d, 'body_base.json'), 'w'))
        if SURFACE_ONLY:                                  # the volume mesh is made elsewhere (VOLUME_ONLY)
            print(open(os.path.join(d, 'body_base.json')).read())
            return
        surf = pv.read(base)
        if SUBDIV:
            surf = surf.subdivide(SUBDIV, 'linear')
        if BAND:
            p, f = refine_band(np.asarray(surf.points, float), surf.faces.reshape(-1, 4)[:, 1:].astype(np.int64), zb)
            surf = pv.PolyData(p, np.c_[np.full(len(f), 3), f].ravel())
        surf.save(stl)
        T['surface_s'] = time.perf_counter() - t0

    t0 = time.perf_counter()
    gmsh.initialize()
    gmsh.option.setNumber('General.Terminal', int(GMSH_VERBOSE))   # GMSH_VERBOSE=1: per-stage wall/CPU times
    gmsh.option.setNumber('General.Verbosity', 5 if GMSH_VERBOSE else 0)
    gmsh.option.setNumber('General.NumThreads', GMSH_THREADS)
    # the boundary triangulation is kept as is (reparametrizing the capped torso surface fails in gmsh)
    gmsh.merge(stl)
    n_surf = len(gmsh.model.mesh.getElementsByType(2)[0])
    sl = gmsh.model.geo.addSurfaceLoop([s[1] for s in gmsh.model.getEntities(2)])
    gmsh.model.geo.addVolume([sl])
    gmsh.model.geo.synchronize()
    nx, ny, nz, pd = [float(v) for v in PLANE.split(',')] if PLANE else (0.0, 0.0, 1.0, zb)
    # gmsh's expression parser rejects "+ -c", so every term carries its own sign after a leading 0
    plane = '0' + ''.join(f"{'-' if c < 0 else '+'}{abs(c):.9f}{v}" for c, v in ((nx, '*x'), (ny, '*y'), (nz, '*z'), (-pd, '')))
    size = f'Min({H_FAR}, {H_BELT} + {GRADE}*Fabs({plane}))'
    if BAND:
        # distance to the skin (the discrete surface's nodes), capped by the belt-plane field
        dist = gmsh.model.mesh.field.add('Distance')
        gmsh.model.mesh.field.setNumbers(dist, 'SurfacesList', [s[1] for s in gmsh.model.getEntities(2)])
        size = (f'Min({size}, {H_SKIN} + {SKIN_GRADE}*F{dist} + {Z_GRADE}*Max(0, Fabs(z - {zb}) - {BAND}))')
    fld = gmsh.model.mesh.field.add('MathEval')
    gmsh.model.mesh.field.setString(fld, 'F', size)
    gmsh.model.mesh.field.setAsBackgroundMesh(fld)
    for k in ('MeshSizeExtendFromBoundary', 'MeshSizeFromPoints', 'MeshSizeFromCurvature'):
        gmsh.option.setNumber('Mesh.' + k, 0)
    gmsh.option.setNumber('Mesh.Algorithm3D', 10)               # HXT, multithreaded
    gmsh.model.mesh.generate(3)
    T['gmsh_volume_s'] = time.perf_counter() - t0

    t0 = time.perf_counter()
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    nodes = xyz.reshape(-1, 3)
    et, en = gmsh.model.mesh.getElementsByType(4)
    gmsh.finalize()
    idx = np.full(int(tags.max()) + 1, -1, np.int64)
    idx[tags.astype(np.int64)] = np.arange(len(tags))
    tets = idx[en.astype(np.int64).reshape(-1, 4)]
    used = np.unique(tets)
    remap = np.full(len(nodes), -1, np.int64)
    remap[used] = np.arange(len(used))
    nodes, tets = nodes[used], remap[tets].astype(np.int32)
    a = nodes[tets]
    vol = np.einsum('ij,ij->i', np.cross(a[:, 1] - a[:, 0], a[:, 2] - a[:, 0]), a[:, 3] - a[:, 0]) / 6
    flip = vol < 0
    tets[flip, 0], tets[flip, 1] = tets[flip, 1], tets[flip, 0].copy()
    vol = np.abs(vol)
    np.savez_compressed(os.path.join(d, MESH_OUT + '.npz'), nodes=nodes, tets=tets)
    T['mesh_export_s'] = time.perf_counter() - t0
    info = dict(case=case, nodes=int(len(nodes)), tets=int(len(tets)), h_belt=H_BELT, h_far=H_FAR, subdiv=SUBDIV,
                plane=[nx, ny, nz, pd], band=BAND, h_skin=H_SKIN, skin_grade=SKIN_GRADE, z_grade=Z_GRADE, surface_triangles=n_surf,
                min_vol_m3=float(vol.min()), mesh_volume_L=float(vol.sum() * 1e3), timing=T,
                host=platform.node(), gmsh=gmsh.__version__, gmsh_threads=GMSH_THREADS)
    json.dump(info, open(os.path.join(d, MESH_OUT + '.json'), 'w'), indent=1)
    print(json.dumps(info))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
