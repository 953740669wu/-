# Stages 2–4 on the C2 cluster: optimization (2026-11-01)

The reference case throughout is s0322, belt placement 0 (level D): 599k nodes, 2.43 M tets, 598,946 unknowns. Timings are single-threaded on C2 Kunpeng nodes. The PETSc/CHOLMOD/KML environment is `env.sh`, owned by the main session; threading is its work item.

## Stage 3: forward solves (`s3_forward.py`, `s6_corpus.py`)

### What changed
1. **Assembly map** (`s3_forward.Assembler`):
   - The CEM sparsity pattern is built once per unit, structurally, from the unique tet edges.
   - A CSC map from element conductivities to matrix values is also built once, holding 16 entries per element in int32.
   - Each later assembly is one sparse mat-vec plus the constant electrode terms, replacing a per-state COO→CSR plus `bmat`.
2. **One symbolic factorization per unit:**
   - `s3_forward.Solver` wraps the value array (`createAIJWithArrays`), and `refactor()` writes new values into it.
   - PETSc sees `SAME_NONZERO_PATTERN`, so CHOLMOD redoes only the numeric factorization.
   - The unit's 105 matrices share one pattern because only the conductivity changes.
3. **Multi-RHS solve:** all 16 or 32 drive patterns go through one `MatMatSolve`, replacing one KSP solve per column.
4. **Lower peak memory:** the Jacobian is formed 16 measurements at a time instead of 64. Peak RSS checkpoints are written to each unit's sidecar.

The old `Solver(A)` / `solve(rhs)` interface still works, so `s3_forward.main` and `s5_cylinder` are unchanged.

### Correctness
- **Drop-in check:** the smoke units (2 contacts × 2 baselines × 2 breaths) give v_ref, v_cur, images and J_img that are **float32-identical** to the amax MUMPS reference (`val/ref`). z differs by ≤ 1.1e-16. Logs: `logs/opt_smoke.log`, `logs/opt_conc2.log`.
- **Same matrix in float64:** the new matrix equals the old one to 1.3e-16 relative. Electrode voltages agree to 1e-13, measurements to 1e-12, and Δv to 1.5e-11. Log: `logs/opt_bench_s3.log`.
- **Checks still pass:** conservation ≤ 6e-13 A and reciprocity ≤ 6e-14.

### Per-solve cost, 1 thread (16-electrode belt)

| step | before | after |
|---|---|---|
| assembly | 4.0 s | 0.2–0.28 s, plus a 17–19 s map once per unit |
| factorization | 24.0 s (symbolic + numeric) | 12.3–13.3 s numeric; the first one per unit is 24–25 s |
| solve | 4.24 s (16 columns) | 1.74–1.84 s (16-belt); 3.64 s (32-belt) |
| **per solve** | **32.3 s** | **14.5 s (2.2× faster)** |

**One full unit (105 solves)** takes about 57 min before and **about 29 min after** for the 16-electrode belt; for the 32-electrode belt it is about 32 min. These figures are projected from the measured per-solve times.

Peak RSS is **5.2–5.75 GB per unit**: about 2.4 GB after setup, 4.2 GB after the first factorization and 5.4 GB after the Jacobian. An intermediate version peaked at 8.1 GB; the Jacobian chunk change fixed that.

### Ruled out by measurement
- **Fill-reducing ordering.** CHOLMOD's default already picks nested dissection (NESDIS): lnz 2.29e8, 0.64 TFLOP. PETSc `nd` is identical. AMD and METIS give lnz 6.3e8 and 5.1 TFLOP, and refactorization takes 65 s, 5× slower.
- **Threads, for now:**

  | threads | 1 | 2 | 4 | 8 | 16 |
  |---|---|---|---|---|---|
  | refactor (s) | 12.5 | 28.7 | 55.5 | 75.0 | 92.2 |

  None of the main session's OpenMP runtime settings helped. At 1 thread the refactorization already runs at about 51 GFLOP/s.
- **PCG on the breath states, preconditioned with the baseline factor** (estimate only, not run). The conductivity ratio sits within about 0.65–1.05, so roughly 12 iterations would be needed. Each iteration costs a multi-RHS solve of 1.8–3.6 s, which is more than one refactorization.

### Packing (1-thread units, 6-solve smoke units)

| layout | refactor per solve | wall for the batch |
|---|---|---|
| 1 unit alone | 12.5–13.1 s | 179 s |
| 16 units, **one per NUMA domain** | 13.5–15.2 s | 229 s |
| 7 units in one domain | 13.8–23.2 s (Jacobian 98–205 s) | 500 s |
| 14 units in one domain | 14.7–31.7 s | 541 s |

The main session's test agrees: 8 units in one domain run up to about 2× slower. Each domain's memory bandwidth is the limit, so units should be spread across all 16 domains with only a few per domain.

## Stage 2: meshing on C2
Details are in `GMSH_C2_REPORT.md`:
- gmsh 4.15.1 runs on C2 in `VOLUME_ONLY=1` mode. Only `prep.npz` and `body_base.stl` (about 4.5 MB gzipped) cross the slow link per case.
- **Single-thread meshing is deterministic:** the same nodes, tets and bytes in every job.
- One mesh takes about 950–970 s. Sixteen at once in one allocation give an effective 62 s per mesh.
- **The mesh realization matters at the 0.5% level.** On placement 0, the C2 1-thread mesh against the amax 4-thread mesh differs by 0.55% in v_ref and 0.51% in Δv. That is within the level-D gate, but it means every corpus mesh should be made the same way, on C2 with 1 thread.

## Production worker: `run_c2_tasks.sh`
One allocation runs placements, then all meshes, then all units, then the manifest:
- **One single-thread task per allowed core**, fed from a shared queue (GNU xargs slots). 32-electrode belts go first.
- **Resumable:** finished meshes and units are skipped.
- **Tested end to end** on s0322 (job 2003010): 2 meshes, 4 units, manifest; placements are identical to amax.

Submit command, from the cluster:
```
dsub -q q_hpcai -R cpu=16,mem=131072MB -T 86400 -oo <log> bash run_c2_tasks.sh <out> <case list>
```
A request without the `numa` option gets one core per NUMA domain.

**Corpus estimate:** 119 cases × 2 placements × 2 belts = 476 tasks of 5 units each. That is about 2.5–2.7 h per task, about 1,250 core-hours in total. At 20 allocations × 16 slots it is roughly 4 h of wall time for the units, plus under 1 h for the 238 meshes.

## Stage 4: reconstruction models on CPU (`s4_models.py`), 2026-11-02
**Ported and measured. Recommendation: train on the amax GPUs; C2 can take the guided-sampling evaluation.**

### Setup
- PyTorch 2.7.1+cpu (aarch64 wheel, bundled OpenBLAS 0.3.29, oneDNN 3.7.1 with ACL) is installed with `pip --target` into `sw/torch`. The wheels are in `pkg/wheels_torch` (torch sha256 a4551cb9…afbdd6e8). It does not use `env.sh`, whose LD_PRELOAD of BiSheng libomp would clash with torch's libgomp.
- **Compute nodes are newer than the login node:** they have SVE2, bf16, i8mm and SME, run at 2.0 GHz max, with 1 thread per core.
- `s4_models.py` is now device-agnostic. Its defaults still reproduce the amax GPU run. The env knobs are DEVICE, AMP, BATCH, CHANNELS_LAST, COMPILE, SAMPLING, GN, REPS and TIMING_OUT. The original is kept in `c2/opt/s4_models_gpu_orig.py`.
- Benchmark inputs are the s0322 worker_test parts. They are used for timing only: the step cost does not depend on the values.

### Thread binding is required
- Without binding, OpenMP threads scale negatively. A 2048³ fp32 matmul runs at 95 GFLOP/s on 1 thread and 9.7 GFLOP/s on 38.
- With `OMP_PROC_BIND=close OMP_PLACES=cores`, 38 threads reach 440–510 GFLOP/s in fp32 and about 1,000 in bf16. Logs: `logs/opt_diag_threads.log` and `opt_diag_blas.log`.
- The cgroup cpuset is 0-607 and only the scheduler affinity is 0-37, so unbound threads wander.
- numpy's own OpenBLAS (pthreads) ignores the OMP binding. That is why the multithreaded GN baseline was slow here; it was not timed.

### Training step, B=64, fp32, one NUMA domain (log `logs/opt_bench_s4_fp32.log`)

| | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder | peak RSS |
|---|---|---|---|---|---|
| **1 process × 38 threads (best)** | 13.2 frames/s | 7.1–7.3 | 1.5–1.8 | 1.0–1.3 | 13.5 / 30 GB |
| channels-last | 13.2 | 4.4 | 1.3 | 0.8 | |
| 2 processes × 19 threads (sum) | 14.6 | 6.5 | 1.2 | 0.9 | |
| 4 processes × 9 threads (sum) | 9.9 | 4.7 | 1.4 | 1.2 | 4 × 30 GB |
| B=128 × 38 threads | 11.6 | 5.9 | 0.8 | 0.7 | 51 GB |
| RTX 4090, bf16 (amax demo) | 1,188 | 284 | 219 | 134 | 9.2 / 18.5 GB |

**Not usable:**
- **bf16 autocast:** one 16-belt encoder+decoder forward+backward takes 415 s, against 9.4 s in fp32 (`logs/opt_diag_s4b.log`).
- **torch.compile:** inductor fails reading a root-only system egg-info (`syssentry`). It was not pursued, because typical CPU compile gains of 10–30% would not change the conclusion.

**Where the time goes** (16-belt step): matmul 40%, convolution backward 19%, convolution forward 10–13%, copies 7%.

### Guided DDIM sampling, per frame, one domain (1 × 38 threads, fp32)

| | 16-belt | 32-belt | RTX 4090 |
|---|---|---|---|
| S16/K50 | 32.9 s | 37.9 s | 2.0–2.1 s |
| S4/K20 | 5.0 s | 5.6 s | 0.54–0.55 s |

### KML SME BLAS for torch's GEMMs (2026-11-02, after the c2-doc review)
- **The fast library.** HPCKit ships KML BLAS builds for SME, SVE512 and NEON. The SME OpenMP build is `/opt/HPCKit/kml-lib/sme/kblas/multi`. On one domain its fp32 `cblas_sgemm` runs at 279 GFLOP/s on 1 thread and 3,380 / 4,850 GFLOP/s on 38 threads (n = 2048 / 4096), with relative error 7e-7. torch's bundled OpenBLAS (SVE kernel) gets 95 and about 500–1,160. Log: `logs/opt_kml_probe.log`.
- **Getting torch to use it.** Two dead ends first:
  - Preloading kblas hangs `import torch` while `torch._C` loads (libomp worker threads in cond_wait). It also hangs with one OpenMP runtime.
  - Calling it through ctypes next to stock torch is slow, about 180 GFLOP/s: torch's GOMP pins the main thread, and KML's separate libomp then inherits a one-core mask.

  What works:
  1. `sw/torch_kml` is a copy of `sw/torch` whose `torch.libs/libgomp-*.so` is a symlink to BiSheng `libomp.so`, so there is one OpenMP runtime. Torch alone runs as before (509 GFLOP/s).
  2. `sw/kml_shim/libkml_sgemm_shim.so` (`c2/opt/kml_sgemm_shim.c`) is an LD_PRELOAD shim that defines `sgemm_` and dlopens `$KML_BLAS_LIB` on the first call. That happens after torch's static initialization, which avoids the hang.

  The forward checksums match stock torch.
- **Run recipe:** `PYTHONPATH=sw/torch_kml`, `LD_PRELOAD=sw/kml_shim/libkml_sgemm_shim.so`, `KML_BLAS_LIB=/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so`, LD_LIBRARY_PATH containing that directory, kml-lib and bisheng-lib, plus `OMP_PROC_BIND=close OMP_PLACES=cores` (`c2/opt/run_bench_s4_kml.sh`).

**Result:** B=64, fp32, 1 × 38 threads, one domain (log `logs/opt_bench_s4_kml.log`).

| | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder | S16/K50 per frame |
|---|---|---|---|---|---|
| stock torch | 13.2 frames/s | 7.1–7.3 | 1.5–1.8 | 1.0–1.3 | 32.9 / 37.9 s |
| **torch_kml + shim** | **28.0** | **7.7** | **2.34** | **1.84** | 32.0 / 36.6 s |
| needed per domain for node = 4090 | 74 | 17.8 | 13.7 | 8.4 | 0.125 / 0.131 s |

- **GEMM time:** in the 16-belt encoder+decoder step, `aten::mm` drops from 4.5 s to 1.0 s, and the step from 10.7 s to 7.7 s.
- **Convolutions now dominate the decoder and sampling:** in oneDNN, convolution backward takes 2.0 s and forward 1.2 s, about 43% of the step.
- **Ruled out:**
  - `MKLDNN=0`, which sends convolutions through torch's fallback im2col path: too slow, the run timed out.
  - An im2col + KML GEMM convolution (`kml_ops.KConv2d`, `KML_CONV=1`): correct to ≤ 1e-5, but 3–9× slower than oneDNN, whose convolution already reaches about 1.9 TFLOP/s in isolation.
- **Where that leaves it:** one RTX 4090 now equals about **2.3–2.7 nodes** for the 16-belt and **4.5–5.8 nodes** for the 32-belt, against 6–8 before. These are per-domain × 16 projections; multi-domain and data-parallel scaling are not measured.

### Profiles: 32-belt and bf16 (KML shim, one domain; logs `logs/opt_prof_s4.log`, `logs/opt_check_attn.log`)
**32-belt pretraining step, fp32, B=64: 16.0 s profiled.** The benchmark above averaged 27.3 s for the same configuration, so step times vary between jobs on shared nodes.
- **Breakdown:**
  - Linear layers (`mm` + `addmm`, rows = 64 × 928 = 59,392 tokens): 6.0 s, about 2.3 TFLOP/s.
  - torch's CPU flash attention ([64, 8, 928, 64] per layer): 4.6 s for 12 layers, about 0.8–1 TFLOP/s.
  - Copies, fills and elementwise ops: about 3–4 s.
- **32-belt decoder step:** 28.9 s. It is the same mix plus oneDNN convolutions (5.2 s).
- **Ceiling:** all FLOPs at KML's square-GEMM rate (about 4.5 TFLOP/s) would be about 18 TFLOP per pretraining step, roughly 4 s. That is the best case for this model on one domain, not something reached.
- **Chunked GEMM attention** (`kml_ops.gemm_attention`; bmm-based, scores recomputed in backward): matches SDPA to ≤ 2e-6, but is 4–9× slower at every s4 shape. It is not used: `patch_attention()` is not called.
- **bf16 on the decoder** (16-belt, B=16): the step takes 102 s, and **oneDNN bf16 convolution backward is 97.7 s of it**, falling back to a slow kernel. bf16 attention (SDPA) is also slower than fp32, and torch's bf16 GEMM (about 950 GFLOP/s) is below KML's fp32 GEMM (3.4–5 TFLOP/s). bf16 therefore gains nothing with this torch build.

**What is left would need kernel work, not library swaps:**
- An SME-aware fused attention.
- A fast bf16/fp32 convolution backward.
- Fused elementwise ops; `torch.compile`, which is blocked by the inductor permission error.
- Multi-domain and data-parallel scaling, still unmeasured.

### Plan phases A, B and C1 (`STAGE4_C2_PLAN.md`), 2026-11-02
**A2 / A3:** 2.0 GHz is the hardware maximum on the compute nodes (userspace governor). DevKit, clang and the KML headers are not installed there; only the HPCKit runtime libraries are.

**C1: KML bf16 GEMM** (`c2/opt/bench_gemm.py`; logs `logs/opt_s4_C1_gemm4.log`, `opt_s4_C1_probe*.log`). There is no header, so the calling conventions were found empirically and from the disassembly:
- **`cblas_bgemm` is all-bf16.** alpha and beta are bf16 (in h0/h1) and C is bf16. Called from ctypes, alpha goes in as an fp32 whose low 16 bits hold the bf16 pattern. Error is about 4e-3 at short K. It also accumulates through the bf16 C across K blocks: relative error 0.15 at K = 59,392 (the dW GEMMs).
- **`cblas_sbgemm` has the OpenBLAS signature** (bf16 A/B, fp32 alpha/beta/C) and accumulates in fp32. It has a bug: some tiles ignore beta = 0 and add into C (every wrong element was exactly ref + the initial C). With C zeroed first it is exact, relative error about 1e-6.

| TFLOP/s, one domain, 38 threads | sgemm (fp32) | bgemm (bf16 out) | sbgemm (fp32 out, C zeroed) | torch |
|---|---|---|---|---|
| square 4096 | 5.0 | 10.8 | 7.6 | 1.3 |
| linear fwd / dX, 32-belt (59,392 tokens) | 4.8–6.8 | 12.9–19.7 | 5.7–10.7 | 0.4–1.9 |
| linear fwd / dX, 16-belt (13,312 tokens) | 3.4–5.4 | 6.6–14.6 | 5.6–9.5 | 0.4–1.8 |
| linear dW (K = tokens) | 1.5–2.9 | 1.1–5.6 (inaccurate at long K) | 1.0–4.7 | 0.5–1.2 |

- **Gate C1 (≥ 1.7× sgemm): passed for forward and dX** (bgemm 2.0–3.5×). For dW it passed only on the qkv dW (sbgemm 2.4×); ff2 dW is 1.5×, and ff1 and out dW are at or below sgemm.

**B1: `kml_ops.KLinear`** (every `F.linear`, `KML_LINEAR=1`; `c2/opt/check_linear.py`, log `logs/opt_s4_B1_linear2.log`, profile `logs/opt_s4_B1_prof.log`):

| One step, one domain | loss vs stock | grad rel diff | step time vs stock |
|---|---|---|---|
| fp32, 16-belt, B16 / B64 | 6e-8 | ≤ 1e-6 | 1.65 vs 1.69 s / 6.53 vs 6.04 s |
| fp32, 32-belt, B64 | 0 | 5e-7 | 33.2 vs 36.9 s |
| bf16 (fwd/dX bgemm, dW sbgemm ≥ 1M outputs, else sgemm), 16-belt B64 | 2.7e-4 | 1.0e-2 | 8.10 vs 6.04 s |
| bf16, 32-belt B64 | 7.1e-4 | 1.1e-2 | 42.6 vs 36.9 s |

- **fp32 KLinear is exact.** In the 32-belt pretraining profile it cuts the linear layers from 6.0 to about 4.3 s, but the step stays at about 16 s. Step times also vary 10–20% between jobs, so the gain is within the noise.
- **bf16 KLinear is correct but slower.** The bf16↔fp32 casts (`aten::copy_`) take 5.4 s, against 1.7 s in fp32. One 59,392 × 2,048 cast runs at about 30 GB/s. The backward GEMM time does not fall either. **Per-layer casting cannot pay off with this torch build.** bf16 would need activations kept in bf16 between layers, which C3 plans.
- **Gate B (linear layers ≥ 4 TFLOP/s in the step):** not met in the step (about 3.2 TFLOP/s effective: about 14 TFLOP of linear GEMMs in 4.3 s), though KML reaches 4.8–6.8 TFLOP/s on these shapes in isolation.

**A1: whole node, 16 domains at once** (`c2/opt/run_node16.sh`). One process per domain, `numactl --cpunodebind --preferred`, KML shim, fp32 KLinear, B=64; each phase starts on all domains together (`SYNC_DIR` barrier in `s4_models.py`); 3 rounds. Log `logs/opt_s4_A1_node16_sync.log`.

| Node, 16 × 38 cores | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder |
|---|---|---|---|---|
| node sum, frames/s (rounds 1/2/3) | 243 / 233 / 237 | 76 / 49 / 49 | 31.0 / 31.1 / 32.7 | 20.5 / 20.4 / 21.3 |
| round-to-round spread (gate ≤ 5%) | 4.2% PASS | 46% FAIL | 5.5% FAIL | 4.3% PASS |
| per-domain median under full load | 15.3 | 4.8 / 3.3 / 3.1 | 1.9–2.0 | 1.2–1.4 |
| single domain alone | 28.0 | 7.7 | 2.34 | 1.84 |
| scaling vs 16 × one domain | 54% | 40–62% | 85% | 70–75% |
| 4090 / node | 5.0 | 3.7–5.8 | 6.9 | 6.4 |

- **One straggler domain per round:**
  - Round 1: domain 5, which had 12 GB free at the start against the 31 GB 32-belt peak.
  - Rounds 2–3: domain 4, up to 10× slower. In round 2 it did not finish its 32-belt decoder within the 90-minute timeout.
  - The HBM nodes 16–19 showed about 54 MB free each. This is the reserved hugepage pool, which is in fact unused; see "Memory residency" below.
  - The 16-belt decoder rate fell on every domain after round 1.

  All of this points to memory placement and residency (spill to remote DDR), not compute.
- **Scaling is 54–85%, not 100%.** One node therefore equals about **1/5–1/7 of a 4090**, not the 1/2.3–1/5.8 from the single-domain × 16 projection.
- **Before Phase G:** strict `--membind` (or a smaller per-rank batch for 32-belt, so it fits in the about 20–25 GB actually free per domain), a free-memory check at job start, and a straggler-tolerant (synchronous-DDP-aware) design.

### Memory residency (2026-11-02; host cn21348; logs `logs/opt_s4_mem_probe.log`, `logs/opt_s4_A1_node16_b32.log`, `logs/opt_s4_scale_probe.log`)

**Node memory.** Each compute domain has 31–32 GB of DDR, of which 20–29 GB is free at job start. 1–4 GB is shmem and cannot be reclaimed (domains 0–1 are the worst). The 4 GB HBM nodes 16–31 (one per DDR domain, nearest distance 61) are fully reserved as a 2 MB hugepage pool: 2,020 pages per node, **all free** (`HugePages_Free` = `HugePages_Total`; `logs/opt_hbm_check.log`). They show about 50 MB "free" only because the pool counts as used. Ordinary allocations (`numactl --membind`) cannot use them. Only hugetlb allocations can (`/dev/hugepages` is mounted as hugetlbfs, 2 MB pages). None of the runs here used HBM. `zone_reclaim_mode` is 0, so under `--preferred` an allocation spills to remote DDR instead of reclaiming local page cache.

**One domain, strict `--membind`, 32-belt** (`c2/opt/run_mem_probe.sh`; `s4_models.py` `CKPT=1` checkpoints each encoder layer):

| 32-belt, one domain | pretrain frames/s | decoder frames/s | peak memory |
|---|---|---|---|
| B64, `--preferred` (earlier) | 2.34 | 1.84 | about 31 GB |
| B64, `--membind` | OOM-killed | – | – |
| B32, `--membind` | 4.08 | 3.04 | 14.4 GB |
| B64 + CKPT, `--membind` | 3.30 | 2.63 | 11.1 GB |

Alone on a domain, the B64 `--preferred` step was memory-limited, and B32 that stays local is 1.7× faster per frame.

**Whole node, B32, strict `--membind`** (`run_node16.sh`, 3 synchronized rounds):

| Node, 16 × 38 cores | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder |
|---|---|---|---|---|
| node sum, frames/s (rounds 1/2/3) | 150 / 151 / 151 | 43 / 46 / 46 | 21.9 / 20.9 / 20.9 | 17.0 / 16.5 / 16.8 |
| spread (gate ≤ 5%) | 0.6% PASS | 5.6% FAIL | 4.6% PASS | 3.0% PASS |
| per-domain median | 9.8–9.9 | 2.5–2.7 | 1.35 | 1.0–1.06 |
| B64 `--preferred` node sum (above) | 243 | 49–76 | 31–33 | 20–21 |

No domain was killed or failed. Peak memory was 8.4 GB (16-belt) and 17.5 GB (32-belt). Even so, **the node sums are lower than with B64 `--preferred`**.

**Concurrency scaling** (`c2/opt/run_scale_probe.sh`; 32-belt pretraining, B32, strict `--membind`; domains 0..N−1 run together):

| Domains at once | 1 | 4 | 8 | 16 |
|---|---|---|---|---|
| per-domain frames/s | 3.99 | 1.32 | 1.31–1.34 | 1.30–1.50 (domain 12: 0.13) |
| sum, frames/s | 3.99 | 5.28 | 10.58 | 20.25 |

Throughout the run, the `/proc/vmstat` counters stayed at zero at every level: direct and kswapd page scans, compaction stalls, `numa_miss`/`numa_foreign`, page migrations and THP fallbacks. The CPU clock held at 2,000 MHz on domains 0 and 12.

- **The node-level loss is contention, not residency.** Per-domain speed drops 3× between one domain and four (domains 0–3), then stays flat out to 16. That is the signature of a resource shared by a group of four domains, probably the memory bandwidth or L3 of one die or socket. The NUMA distances match this: domains 0–3, 4–7, 8–11 and 12–15 are each at distance 20 from one another, against 30–40 to other domains. This could not be confirmed without hardware counters (no DevKit or perf on the compute nodes). A domain running alone gets most of that shared resource, so the single-domain × 16 projections overstate a node by about 3× for 32-belt.
- **B32 under contention is worse per frame than B64** (1.32 against about 1.95 frames/s per domain). The smaller batch costs more than staying local gains.
- **Domain 12 on cn21348 is a host-specific straggler** in every round: 16-belt pretraining about 5× slower, 32-belt pretraining up to 10× slower. Inside the exclusive job, `ps` shows a root `sudo` thread at 27% CPU and a `CSD_26` thread of another user on core 493, which belongs to domain 12. With OpenMP threads bound to each core, one shared core stalls every barrier. Not yet tested: excluding busy cores (`physcpubind` minus core 493, `OMP_NUM_THREADS=37`).
- **Consequence.** Strict `--membind` with B32 (or B64 + CKPT) removes the spill and the OOM, but it does not raise node throughput. The node ceiling under the current kernels is about 21–33 frames/s for 32-belt pretraining (4090: 219) and about 150–243 for 16-belt (4090: 1,188). Per-domain speedups help a full node only if they cut memory traffic: bf16 activations kept between layers, fused attention (Phase D), fewer passes.

### Memory bandwidth and HBM (2026-11-03; logs `logs/opt_hbm_probe.log`, `opt_hbm_probe2.log`, `opt_s4_hbm_ab.log`)

**Bandwidth** (`c2/opt/hbm_probe.py`, `run_hbm_probe.sh`: fp32 triad, three 1 GB arrays, 38 threads per domain, domains 0..N−1 at once; host cn21346):

| Domains at once | 1 | 4 (one die) | 16 |
|---|---|---|---|
| DDR, per domain GB/s | 102 | 26.3 | 26–27 |
| DDR, sum GB/s | 102 | 105.5 | 428 |
| HBM (own node 16+d), per domain GB/s | 62.4 | 62 | 60–64 |
| HBM, sum GB/s | 62 | 250 | 988 |

- **Each die (four domains) shares about 105 GB/s of DDR.** This is the contention measured above. Each domain's own HBM node gives about 62 GB/s regardless of load.
- **HBM access:**
  - The HBM is a free pool of 2 MB hugetlb pages: 2,020 pages per node. The job's hugetlb cgroup limit is unlimited.
  - A hugetlb `mmap` reserves its pages from the task mempolicy's nodes. So the process must be bound to `d,16+d` (`numactl --membind=d,16+d`), or the `mmap` fails with ENOMEM.
  - Ordinary pages still come from DDR d first, because node 16+d has only about 50 MB of non-hugetlb memory.

**HBM allocator** (`c2/opt/hbm_alloc.c` → `sw/hbm_alloc/libhbm_alloc.so`, LD_PRELOAD; `run_node16.sh HBM=1`).
- **How it works:**
  - torch's large CPU buffers (`posix_memalign` ≥ 256 KB) are served from a 3.8 GB hugetlb arena with `mbind` to HBM node 16+d.
  - Freed blocks are reused by exact size class (64 KB granularity); the remainder is bump-allocated.
  - When the arena is full, requests fall back to glibc (DDR).
- **Check:**
  - The 4096² matmul had relative error 4.6e-7.
  - Block reuse is correct.
  - The pages land on node 16 (free hugepages fell from 2,020 to 1,227 while held).
- **Caveat:** hugetlb pages are not counted in RSS, so `peak_mem_GB` under HBM=1 shows only the DDR part.

**One die (NDOM=4, domains 0–3 at once), B32, fp32 KLinear, one round each, host cn21338** (`c2/opt/run_hbm_ab.sh`):

| frames/s, sum of 4 domains | DDR only | HBM=1 | gain |
|---|---|---|---|
| 16-belt pretrain | 36.2 (median 10.6, min 4.1) | 125.6 (median 31.4) | 3.5× |
| 16-belt decoder | 16.4 | 29.3 | 1.8× |
| 32-belt pretrain | 5.61 | 7.21 | 1.29× |
| 32-belt decoder | 4.58 | 6.01 | 1.31× |

- **16-belt with HBM loses its contention:** each domain runs at 31 frames/s, at or above the 28 that one domain reached alone on DDR (B64).
- **32-belt** sends 156 GB of large allocations to HBM against 559 GB to DDR. Its 12–17 GB working set is 3–4× the arena, so the gain is small.
- **Next levers:**
  - Smaller per-rank working sets (CKPT, B32/B16).
  - Placing by heat, not by first come: weights, attention/softmax buffers and recurring activation sizes first.
- **Caveat:** one round, one host, and the DDR-only run had a slow domain.

**Whole node, 16 domains, `SKIP_BUSY=1`, 2 rounds** (logs `logs/opt_s4_A1_node16_b32_hbm.log`, `opt_s4_A1_node16_b64ckpt.log`, `opt_s4_A1_node16_b64ckpt_hbm.log`):

| node sum, frames/s | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder |
|---|---|---|---|---|
| B32 + HBM (rounds 1/2) | 290 / 318 (spread 9.4% FAIL) | 75 / 72 | 21.9 / 21.4 | 18.0 / 18.3 |
| B32, DDR (above) | 150 | 43–46 | 21–22 | 16.5–17 |
| B64 `--preferred`, DDR (above) | 233–243 | 49–76 | 31–33 | 20–21 |
| B64 + CKPT, DDR | 121 / 118 | 56 / 42 (spread 30% FAIL) | 16.6 / 16.8 | 14.3 / 14.0 |
| B64 + CKPT + HBM | no result: bus error | | | |
| per-domain median, B32 + HBM | 18.0 / 20.4 (min 3.3 / 2.8) | 4.9 / 4.5 | 1.34 | 1.08 |

- **On the whole node, HBM doubles 16-belt B32** (pretraining 150 → 290–318, decoder 1.65×). It beats the best DDR configuration (B64 `--preferred`) by 1.2–1.3×. That is one node ≈ **1/3.7–1/4.1 of a 4090** for 16-belt pretraining.
- **It falls short of the one-die rate (4 × 31 = 126 per die, so about 500 per node).** The per-domain median is 18–20, and each round has stragglers at 3 frames/s even with `SKIP_BUSY`. The remaining DDR traffic of the 16-belt step is still contended.
- **32-belt gains nothing on the whole node** (21–22 with or without HBM). Its working set is 3–4× the arena, so most traffic stays on contended DDR.
- **B64 + CKPT is slower than B64 or B32** on DDR, because recomputation costs more than it saves.
- **B64 + CKPT + HBM: bus error on 1–2 domains per round.** The other domains then waited at the first barrier until the 90-minute timeout.
  - **Cause:** the hugetlb reservation at `mmap` counted the task policy's nodes (d,16+d), but faults are bound to the single HBM node. Where that node's pool was short, a fault raised SIGBUS.
  - **Fix (2026-11-03):** `hbm_alloc` sizes the arena from the node's `free_hugepages` (16 kept spare) and binds the calling thread to the HBM node for the `mmap` only. The 5.10 kernel then counts only that node, and a shortfall becomes ENOMEM at start-up.
  - **Tested on one domain** (`run_hbm_fix.sh`, `logs/opt_hbm_fix.log`): an `HBM_MB=9000` request is capped to 4,008 MB with correct data. The B64 + CKPT + HBM whole-node run has not been repeated.

### Projection (not measured beyond one domain; figures predate the KML shim)
These figures assume a node runs 16 domains in parallel with no slowdown and that data-parallel communication is free. Neither has been tested, so they are best cases.

- **Pretraining epoch, 1 M frames (half per belt):** about 6 node-hours, against 0.75 GPU-hours.
- **Decoder epoch:** about 9 node-hours, against 1.5 GPU-hours.
- **Equivalence:** one 4090 ≈ 6–8 C2 nodes for training.
- **Whole plan:** the plan's 6–10 RTX 4090-weeks of training and ablations would come to about 40–80 node-weeks (4–8 M core-hours), against about 1,250 core-hours for the whole corpus.
- **Data-parallel training changes the run itself:** the global batch becomes 1,024 per node, so the learning rate and schedule would need retuning, which is a different experiment from the one planned on GPU.
- **Guided-sampling evaluation is independent per frame,** so it needs no data-parallel setup. At S16/K50, 200k frames take about 120 node-hours per seed (about 6 h on 20 nodes); at S4/K20, about 19 node-hours. That is about the same as the 111 GPU-hours on amax, and it runs in parallel with GPU training.

## Files
- **Code:** `demo/s3_forward.py` and `demo/s6_corpus.py`, with the optimizations above; `demo/s2_mesh.py` with `VOLUME_ONLY`, `GMSH_THREADS` and `GMSH_VERBOSE`.
- **Cluster scripts:** `c2/run_c2_tasks.sh`, `c2/build_gmsh.sh`, and the tests and benchmarks in `c2/opt/`.
- **Stage 4 on CPU:** `demo/s4_models.py` (device-agnostic; `BELTS`, `PARTS`, `SYNC_DIR`/`SYNC_N` for whole-node runs, `KML_LINEAR`/`LINEAR_DTYPE`) and `demo/kml_ops.py` (KML GEMM via ctypes, `KLinear`); the phase A–C1 scripts `c2/opt/bench_gemm.py`, `probe_bgemm.py`, `probe_sbgemm.py`, `check_linear.py`, `run_node16.sh` (`MEMPOL`), `run_prof_klinear.sh`, `run_mem_probe.sh`, `run_scale_probe.sh`, `hbm_probe.py`, `run_hbm_probe.sh`, `hbm_alloc.c`, `run_hbm_ab.sh`, `run_hbm_fix.sh`; the benchmarks `c2/opt/run_bench_s4.sh`, `diag_s4.py`, `diag_blas.py`, `diag_mm.py` and `run_diag_threads.sh`. Cluster outputs are in `eitfm/opt/s4/reports`.
- **On the cluster:** `eitfm/opt/` holds the code copy, test outputs and `run_c2_tasks.sh`. Logs are `eitfm/logs/opt_*.log`.
