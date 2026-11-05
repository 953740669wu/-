"""Stage 3 cost on one C2 node, s0322 placement 0, 16-electrode belt (one unit's matrix, three conductivities).

  compare    old path (COO assembly + bmat, new factorisation and column-by-column solves per state) against the
             new one (assembly map, one symbolic analysis, numeric refactorisation, multi-RHS solve); max differences
  orderings  symbolic + numeric factorisation time and fill for CHOLMOD ordering choices
  refactor   numeric refactorisation and multi-RHS solve time only (run at several OMP_NUM_THREADS)

Usage: python3 bench_s3.py <code dir> <case dir> <mode>
"""
import os, sys, json, time
import numpy as np, scipy.sparse as sp

code, case_dir, mode = sys.argv[1:4]
sys.path.insert(0, code)
import s3_forward as F, s6_corpus as S6
from petsc4py import PETSc

F.R_ELEC = S6.CFG['r_elec_m']
P = np.load(os.path.join(case_dir, 'prep.npz'))
lab, dx, sig = P['lab'], P['dx'], P['sigma']
pl = json.load(open(os.path.join(case_dir, 'placements.json')))['placements'][0]
Mz = np.load(os.path.join(case_dir, pl['mesh'] + '.npz'))
nodes, tets = Mz['nodes'], Mz['tets'].astype(np.int64)
nn = len(nodes)
G, vol = F.p1_geometry(nodes, tets)
vox = np.clip((nodes[tets].mean(1) / dx).astype(int), 0, np.array(lab.shape) - 1)
le = lab[vox[:, 0], vox[:, 1], vox[:, 2]]
lung = np.isin(le, [6, 7])
s0 = np.maximum(sig[le], 0.03)                                     # tissue table at each element centroid
states = [s0, s0 * np.where(lung, 0.85, 1.0), s0 * np.where(lung, 0.92, 1.0)]

L, skip = S6.CFG['belts']['16_adjacent']
bf = F.boundary_faces(tets)
loop = S6.belt_loop(nodes, bf, np.array(pl['normal']), pl['d'])
per = S6.loop_points(loop, np.zeros(1))[1]
centres, _ = S6.loop_points(loop, np.arange(L) / L * per)
Me, C, dg, area = F.cem_blocks(nodes, F.electrode_patches(nodes, bf, centres), np.full(L, 1e-3), nn)
drives, meas = F.protocol(L, skip)
R = F.drive_rhs(nn, L, drives)
thr = os.environ.get('OMP_NUM_THREADS', '?')
out = lambda **kw: print(json.dumps(dict(mode=mode, threads=thr, **kw)), flush=True)
out(nodes=nn, tets=len(tets), unknowns=nn + L - 1)


class OldSolver:                                     # the previous s3_forward.Solver, kept here as the reference
    def __init__(self, A):
        A = A.tocsr()
        self.M = PETSc.Mat().createAIJ(size=A.shape, csr=(A.indptr.astype(PETSc.IntType),
                                                          A.indices.astype(PETSc.IntType), A.data))
        self.M.setOption(PETSc.Mat.Option.SPD, True)
        self.ksp = PETSc.KSP().create(); self.ksp.setOperators(self.M); self.ksp.setType('preonly')
        pc = self.ksp.getPC(); pc.setType('cholesky'); pc.setFactorSolverType(F.SOLVER)
        self.ksp.setUp()
        self.x, self.b = self.M.createVecs()

    def solve(self, rhs):
        o = np.empty_like(rhs)
        for k in range(rhs.shape[1]):
            self.b.setArray(rhs[:, k]); self.ksp.solve(self.b, self.x); o[:, k] = self.x.getArray()
        return o

    def destroy(self):
        self.ksp.destroy(); self.M.destroy(); self.x.destroy(); self.b.destroy()


def factor_stats(S):
    """lnz and flop count of the factor, from CHOLMOD's info view."""
    f = '/tmp/eitfm_cholview_%d.txt' % os.getpid()
    vw = PETSc.Viewer().createASCII(f); vw.pushFormat(PETSc.Viewer.Format.ASCII_INFO)
    S.ksp.getPC().getFactorMatrix().view(vw); vw.destroy()
    txt = open(f).read(); os.remove(f)
    keep = [l.strip() for l in txt.splitlines() if any(k in l for k in ('lnz', ' fl', 'selected', 'nmethods', 'current'))]
    return keep


tick = time.perf_counter
if mode == 'compare':
    t0 = tick(); asm = F.Assembler(tets, G, vol, Me, C, dg, nn); tmap = tick() - t0
    Xn, Tn, S = [], [], None
    for s in states:
        t0 = tick(); data = asm.values(s); t1 = tick()
        if S is None:
            S = F.Solver(sp.csr_matrix((data, asm.indices, asm.indptr), shape=asm.shape))
        else:
            S.refactor(data)
        t2 = tick(); X = S.solve(R); t3 = tick()
        Xn.append(X); Tn.append(dict(assembly_s=t1 - t0, factor_s=t2 - t1, solve_s=t3 - t2))
    out(path='new', assembly_map_s=tmap, per_state=Tn, stats=factor_stats(S))
    S.destroy()
    Xo, To = [], []
    for s in states:
        t0 = tick(); A = F.cem_system(F.stiffness(tets, G, vol, s, nn), Me, C, dg); t1 = tick()
        S = OldSolver(A); t2 = tick(); X = S.solve(R); t3 = tick(); S.destroy()
        Xo.append(X); To.append(dict(assembly_s=t1 - t0, factor_s=t2 - t1, solve_s=t3 - t2))
    out(path='old', per_state=To)
    A_old = F.cem_system(F.stiffness(tets, G, vol, states[1], nn), Me, C, dg)
    dA = abs(A_old - asm.matrix(states[1]))
    rel = lambda a, b: float(np.abs(a - b).max() / np.abs(a).max())
    out(matrix_max_abs_diff_rel=float(dA.max() / abs(A_old).max()),
        X_rel=[rel(a, b) for a, b in zip(Xo, Xn)],
        U_rel=[rel(a[nn:], b[nn:]) for a, b in zip(Xo, Xn)],
        v_rel=[rel(F.measure(F.voltages(a, nn, L)[1], drives, meas), F.measure(F.voltages(b, nn, L)[1], drives, meas))
               for a, b in zip(Xo, Xn)],
        dv_rel=rel(F.measure(F.voltages(Xo[1] - Xo[0], nn, L)[1], drives, meas),
                   F.measure(F.voltages(Xn[1] - Xn[0], nn, L)[1], drives, meas)))

elif mode == 'orderings':
    asm = F.Assembler(tets, G, vol, Me, C, dg, nn)
    A0 = asm.matrix(states[0])
    ref = None
    for name, opts in (('default', {}), ('nmethods1_amd', {'mat_cholmod_nmethods': 1}),
                       ('nmethods2_amd_metis', {'mat_cholmod_nmethods': 2}),
                       ('nmethods3_amd_metis_nesdis', {'mat_cholmod_nmethods': 3}),
                       ('petsc_nd', {'pc_factor_mat_ordering_type': 'nd'}),
                       ('default_nopack', {'mat_cholmod_pack': 0})):
        o = PETSc.Options()
        for k, v in opts.items():
            o[k] = v
        t0 = tick(); S = F.Solver(A0); t1 = tick()
        S.refactor(asm.values(states[1])); t2 = tick(); X = S.solve(R); t3 = tick()
        U = X[nn:]
        ref = U if ref is None else ref
        out(ordering=name, analyze_plus_factor_s=t1 - t0, refactor_s=t2 - t1, solve_s=t3 - t2,
            U_rel_vs_default=float(np.abs(U - ref).max() / np.abs(ref).max()), stats=factor_stats(S))
        S.destroy()
        for k in opts:
            del o[k]

elif mode == 'refactor':
    asm = F.Assembler(tets, G, vol, Me, C, dg, nn)
    t0 = tick(); S = F.Solver(asm.matrix(states[0])); t1 = tick()
    rf, sv = [], []
    for s in states[1:] * 2:
        t = tick(); S.refactor(asm.values(s)); rf.append(tick() - t)
        t = tick(); S.solve(R); sv.append(tick() - t)
    out(first_s=t1 - t0, refactor_s=rf, solve_s=sv)
    S.destroy()
