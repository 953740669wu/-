# EIT-FM pipeline on the C2 cluster: optimized code for stages 2–4 (handover, 2026-11-03)

This package holds the code that runs the thoracic-EIT pipeline on the C2 Kunpeng cluster:
- **Stage 2:** meshing.
- **Stage 3:** forward solves and corpus generation.
- **Stage 4:** reconstruction-model training.

It covers what was optimized, how well it works, how to run and check it, and what is still open. The detailed measurements, each with its log, are in the reports under `c2/` (§7).

## 1. Ground rules (keep these)

- **Never invent results.** Every number in the reports comes from a logged run. Mark projections as projections.
- **`data/raw` is read-only.** Respect the subject split.
- **Fixed seeds:** 2026 for splits and corpus, 0/1/2 for training.
- **The corpus is finished and frozen:**
  - Folder: `corpus_shape_20261102`, with 11,900 units and 1,190,000 pairs.
  - Code hash `d8b2be8d1f`, config hash `b1049eac1a`.
  - Any change to `s1_prepare.py`, `s2_mesh.py`, `s3_forward.py` or `s6_corpus.py` changes those hashes. Results made with changed code are a new corpus, not a continuation. To optimize stages 2–3 further, keep the outputs bit-identical, or float32-identical as defined in §3.2, against the frozen code, and test with the smoke scripts in §3.4.
- **Pilot before scale.** Measure every change on one domain, then on one die (4 domains), then on the whole node. A full node behaves differently from one domain (§5.2).
- **Determinism.** Mesh with one thread (multi-threaded HXT is not reproducible). Outputs are resumable; workers skip finished meshes and units.

## 2. Machines and environment

| Host | Role | Notes |
|---|---|---|
| amax (GPU server) | stage 1 inputs, GPU training, analysis | `/mnt/lvliannas/szl/...` |
| C2 (Kunpeng, ssh `hpc-vpn`) | stages 2–3 corpus production, stage 4 CPU work | `/home/share/songzhenlong/eitfm`; Donau scheduler, queue `q_hpcai` |
| the PC | the only host that reaches both | `c2/sync_c2.sh` moves data |

The host names, user names and paths in the scripts are the current owner's. Adjust them for your own account.

**A C2 compute node:**
- **CPU and memory:** 608 cores in 16 NUMA domains of 38 cores, each with about 31–32 GB of DDR. Each group of four domains is one die and shares about 105 GB/s of DDR bandwidth.
- **HBM:** 16 HBM nodes of 4 GB (nodes 16–31), reserved as a free 2 MB hugetlb pool.
- **Clock:** 2.0 GHz is the maximum.
- **ISA:** SVE2, bf16, i8mm, SME.
- **Tools:** no perf, DevKit or headers. gcc works inside jobs.

**Software in `eitfm/sw/`, built by the scripts here:**
- `gmsh` (`c2/build_gmsh.sh`).
- PETSc 3.25.3 with SuiteSparse/CHOLMOD on KML BLAS (`c2/build_petsc.sh`, environment `c2/env.sh`). OpenBLAS (`c2/build_openblas.sh`) is an alternative stack.
- PyTorch 2.7.1+cpu (`sw/torch`), plus `sw/torch_kml`.
- `sw/kml_shim` and `sw/hbm_alloc`, built in jobs from `c2/opt/kml_sgemm_shim.c` (`run_kml_shim.sh`) and `c2/opt/hbm_alloc.c` (`run_hbm_ab.sh`).

**Submitting jobs:**
- Whole node: `-R cpu=608,mem=480000MB -a "numa[count=16,distribution=pack]"`.
- One domain: `-R cpu=38 -a "numa[count=1,distribution=pack]"`.
- Without the `numa` option, a job gets one core per NUMA domain.
- Bash reads scripts while they run, so copy a launcher to `/tmp` before running it (as `prod_submit.sh` does). Never edit a script that a running job is using.

## 3. Stages 2–3: meshing, forward solves, corpus production (done; in production)

### 3.1 Stage 2: meshing (`s2_mesh.py`, `c2/build_gmsh.sh`; details in `c2/GMSH_C2_REPORT.md`)

- **gmsh 4.15.1 is built for C2.** It runs in `VOLUME_ONLY=1` mode on `body_base.stl`, which amax writes with `SURFACE_ONLY=1` in `c2/amax_prep.sh`. Only `prep.npz` and the STL (about 4.5 MB gzipped) cross the slow link.
- **The surface subdivision was rewritten in numpy.** It reproduces amax's pyvista surface exactly and needs no pyvista, scikit-image or scipy on C2.
- **One-thread meshing is deterministic** (byte-identical `mesh.npz` on C2). One mesh takes about 950 s; 16 run at once in one allocation, for an effective 62 s per mesh.
- **Threads don't help:** `tOptimize` takes 97% of the time and doesn't scale in this build.
- **Open:**
  - `tOptimize` is the only real cost. Changing its settings changes the mesh, and with it the corpus.
  - The C2 and amax meshes differ by 0.5% in v_ref, so all corpus meshes are made on C2 with one thread.

### 3.2 Stage 3: forward solver (`s3_forward.py`, used by `s6_corpus.py`, `s5_cylinder.py`)

**What changed:**
1. **Assembly map:**
   - The CEM sparsity pattern is built once per unit from the unique tet edges.
   - A CSC map from element conductivities to matrix values is built once (16 int32 entries per element).
   - Each later assembly is one sparse mat-vec plus the constant electrode terms.
2. **One symbolic factorization per unit:** `Solver.refactor()` writes new values into the same PETSc AIJ arrays (`SAME_NONZERO_PATTERN`). CHOLMOD then repeats only the numeric factorization for the 105 matrices of a unit.
3. **Multi-RHS solve:** all 16 or 32 drive patterns go through one `MatMatSolve`.
4. **Lower peak memory:** the Jacobian is formed in chunks of 16 measurements, so peak RSS is 5.2–5.75 GB per unit.

**Effect:**
- Per solve on one thread: 32.3 s before, 14.5 s after (2.2× faster).
- Per 16-belt unit: about 57 min before, about 29 min after.
- The old `Solver(A)` / `solve(rhs)` interface is unchanged.

**Correctness:**
- Against the amax MUMPS reference, v_ref, v_cur, images and J_img are float32-identical; z differs by ≤ 1.1e-16.
- Conservation is ≤ 6e-13 A and reciprocity ≤ 6e-14.

**Ruled out by measurement:**
- Other orderings: CHOLMOD's NESDIS is already the best; AMD and METIS are 5× slower.
- CHOLMOD threads: 1 thread takes 12.5 s per refactorization, 16 threads 92 s.
- PCG with the baseline factor: an estimate only; it would cost more than a refactorization.

### 3.3 Corpus generation (`s6_corpus.py`) and production scripts (`c2/PRODUCTION_C2.md`, `c2/PILOT_C2_REPORT.md`)

**Content added to `s6_corpus.py`** (each change was smoke-tested):
- Slab-aware pathology placement, and raised minimum pathology sizes.
- A body-shape perturbation: 8 Fourier terms, `max_rel` 0.05, applied to the deformed mesh and electrode loop.
- 25 contacts per case.
- Earlier versions are kept as `c2/opt/s6_corpus_pre_{slab,size,shape}.py` for diffing.

**Production:**

| Script | Where it runs | Job |
|---|---|---|
| `c2/amax_prep.sh` | amax | stage 1 and the body surface |
| `c2/sync_c2.sh push` | PC | push the inputs |
| `c2/prod_setup.sh` | C2 login | freeze the code, write the shards |
| `c2/prod_submit.sh` | C2 login | one whole-node job per unfinished shard |
| `c2/prod_c2.sh`, `c2/prod_tasks.sh` | C2 jobs | the worker: one single-thread task per core, three slots per NUMA domain, one unit per task, resumable |
| `c2/sync_c2.sh pull` | PC | pull the results to amax |

- **Measured throughput:** about 86 units/h per node, 0.56 core-hours per unit.
- **Lessons:**
  - Always pass absolute shard paths.
  - Shards at the 6 h limit lose their last units; resubmit them.
  - `sync_c2.sh` sets `LC_ALL=C`, because the two hosts sort differently.
- **The older single-allocation worker** is `c2/run_c2_tasks.sh`.
- **Validation and pilots:** `c2/val.sh`, `c2/pilot_c2.sh`, `c2/pilot_c2_compare.py`.

**Packing:** one unit per NUMA domain is best. Several in one domain slow down about 2× because they share memory bandwidth. The worker uses three per domain as a compromise.

### 3.4 Tests for stages 2–3 (`c2/opt/`)

- `run_smoke_opt.sh`: the drop-in check against the amax reference.
- `bench_s3.py` / `run_bench_s3.sh`: old against new path, orderings, threads.
- `run_conc_opt.sh`, `run_conc2_opt.sh`: packing.
- `run_worker_test.sh`: end-to-end worker test.
- `run_size_smoke.sh`, `run_slab_smoke.sh`, `run_shape_smoke.sh`: the corpus changes. The shape smoke test checks that A = 0 is bit-identical to the pre-shape code.

**Possible further work on stages 2–3** (all optional now that the corpus is done):
- Threaded CHOLMOD. 1 thread already reaches about 51 GFLOP/s, and more threads were slower.
- A faster `tOptimize`, at the cost of new meshes.
- Fewer refactorizations per unit, for example low-rank updates for local pathology changes. This must keep outputs identical within the tolerances in §3.2.

## 4. Stage 4 on CPU: where it stands

`s4_models.py` holds two models:
- The EIT-FM measurement-token encoder: 12 layers, width 512, 8 heads, masked modelling.
- The conditional diffusion U-Net decoder.

It is device-agnostic, and its defaults reproduce the amax GPU run (the original is `c2/opt/s4_models_gpu_orig.py`). Training was planned for RTX 4090s. amax is no longer available, so the target is **one C2 node = one 4090**.

**Best measured throughput per node** (frames/s):

| | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder |
|---|---|---|---|---|
| RTX 4090 | 1,188 | 284 | 219 | 134 |
| C2 node, best configuration | 290–318 (HBM, B32) | 72–75 (HBM, B32) | 31–33 (DDR, B64) | 20–21 (DDR, B64) |
| fraction of a 4090 | 1/3.7–1/4.1 | 1/3.8 | 1/7 | 1/6.4 |

**What was done, in order of impact:**
1. **Thread binding** (`OMP_PROC_BIND=close OMP_PLACES=cores`). Without it, threads scale negatively.
2. **KML SME BLAS for torch's GEMMs** through an LD_PRELOAD shim (`c2/opt/kml_sgemm_shim.c`). The shim loads KML lazily; loading it before torch hangs.
3. **`kml_ops.py`:**
   - `KLinear`: fp32 is exact.
   - The bf16 paths `cblas_bgemm` and `cblas_sbgemm`. Their conventions are documented in the file; `sbgemm` needs a zeroed C.
   - bf16 GEMM is 2.0–3.5× faster than fp32 on forward and dX. Per-op casts make it slower overall unless activations stay bf16 between layers.
4. **One process per NUMA domain** (`c2/opt/run_node16.sh`), strictly memory-bound (`--membind`), with a phase barrier.
   - `SKIP_BUSY=1` leaves out cores already used by foreign processes.
   - `NDOM=4` runs one die.
5. **HBM placement:** the `c2/opt/hbm_alloc.c` LD_PRELOAD puts torch's large buffers in the domain's HBM node (62 GB/s regardless of load).
   - It roughly doubles 16-belt on the whole node, and gives 3.5× on one die.
   - 32-belt is unchanged, because its 12–17 GB working set is too large for 4 GB of HBM.

**The main finding:** the node is limited by memory bandwidth. Four domains share about 105 GB/s of DDR, so one domain measured alone overstates the full node by about 3×. Only changes that reduce DDR traffic help: HBM, smaller working sets, bf16 activations, fused attention.

**Everything about stage 4 is in `c2/STAGE4_HANDOVER.md`:** run recipe, knobs, open issues and next steps with day estimates. The phase plan and its gates are in `c2/STAGE4_C2_PLAN.md`.

**Short version of the next steps:**
- **M1:** fix the remaining straggler domains. Rerun checkpointing + HBM on the whole node; the bus-error fix is tested on one domain only.
- **M2:** fit each rank's working set in about 4 GB.
- **M3:** place buffers in HBM by how heavily they are used.
- **Then:** bf16 activations between layers, fused SME attention, and 16 ranks as one data-parallel device.

**Estimate:**
- 16-belt: about 1–1.5 weeks to about 1/2.5–1/3 of a 4090.
- 32-belt: about 3–4 weeks to about 1/4–1/6.
- One node is not expected to match a 4090. Plan on several nodes per training run.

## 5. Package layout

The layout mirrors the project folder `demo/`.

| Path | Contents |
|---|---|
| `s1_prepare.py` | Stage 1 (case preparation). Included because `amax_prep.sh` and `qc_geometry.py` depend on it |
| `s2_mesh.py` | Stage 2 mesher (`SURFACE_ONLY`, `VOLUME_ONLY`, `GMSH_THREADS`, `GMSH_VERBOSE`) |
| `s3_forward.py` | Stage 3 CEM forward solver: assembler, refactorizing solver, multi-RHS |
| `s5_cylinder.py` | Cylinder validation; uses the `s3_forward` interface |
| `s6_corpus.py` | Corpus units: pathologies, breaths, shape perturbation, Jacobian |
| `qc_geometry.py` | Geometry QC for stages 1–2 |
| `s4_models.py`, `kml_ops.py` | Stage 4 models, step timing and env knobs; KML GEMM / `KLinear` |
| `c2/*.sh`, `c2/pilot_c2_compare.py` | Builds, environment, production, sync, validation, pilots |
| `c2/opt/` | Optimization tests, benchmarks, probes, preload sources, previous `s6_corpus` versions, the original GPU `s4_models` |
| `c2/*.md` | Reports, runbook, plan, stage 4 handover (§7) |

## 6. Where results live

- **C2:** `eitfm/logs/opt_*.log` (every log cited in the reports) and `eitfm/opt/s4/reports/<tag>/`. Corpus: `eitfm/corpus_shape_20261102`.
- **amax:** the corpus copy is `/mnt/lvliannas/szl/thorax_eitfm_corpus_20261102/c2`; the reports are in `reports/P4_corpus.md`.

## 7. Documents, in reading order

1. This file.
2. `c2/C2_OPTIMIZATION_REPORT.md`: all stage 2–4 measurements, with logs.
3. `c2/GMSH_C2_REPORT.md`: the gmsh build, determinism and throughput.
4. `c2/PILOT_C2_REPORT.md` and `c2/PRODUCTION_C2.md`: pilot against amax, and the production runbook with its history.
5. `c2/STAGE4_HANDOVER.md`: stage 4 status and next steps.
6. `c2/STAGE4_C2_PLAN.md`: stage 4 phase plan and gates.
