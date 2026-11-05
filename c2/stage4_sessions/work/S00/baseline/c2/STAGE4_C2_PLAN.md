# Stage 4 on C2: plan to reach RTX 4090 throughput per node (2026-11-02)

**Goal:** one C2 node (16 NUMA domains × 38 cores) does the stage 4 work of one RTX 4090, because amax will no longer be available.

**Scope:** the s4_models workload:
- EIT-FM encoder pretraining.
- Diffusion-decoder training.
- Guided DDIM sampling.
- The GN/NOSER and other baselines.

**Basis:** every "measured" number comes from a C2 log named in `C2_OPTIMIZATION_REPORT.md`. Projections are labelled as estimates, and each phase ends in a measured gate.

## Status after phases A, B, C1 (2026-11-02; details and logs in `C2_OPTIMIZATION_REPORT.md`)

| Gate | Result |
|---|---|
| A1 whole-node spread ≤ 5% | **Partly.** Pass for 16-belt pretraining (4.2%) and 32-belt decoder (4.3%); fail for 32-belt pretraining (5.5%) and 16-belt decoder (46%). Each round had one memory-starved straggler domain. |
| A1 finding | Scaling across 16 domains is **54–85%**, not 100%. One node = **1/5.0 (16-belt pretraining) to 1/6.9 (32-belt pretraining) of a 4090**, against the single-domain × 16 projection of 1/2.7–1/5.8. |
| A2 frequency | 2.0 GHz is the hardware maximum; no free factor. |
| A3 DevKit | Not available on compute nodes (runtime libraries only). |
| B linear ≥ 4 TFLOP/s in step | **No.** fp32 `KLinear` is exact and takes the linears from 6.0 to 4.3 s (about 3.2 TFLOP/s); the 32-belt pretraining step stays at about 16 s. |
| C1 bf16 ≥ 1.7× fp32 | **Pass for forward and dX** (`cblas_bgemm` 2.0–3.5×, but bf16 C and bf16 accumulation). dW: `cblas_sbgemm` (fp32 accumulation; needs a zeroed C) 2.4× on qkv only. |
| C2 bf16 `KLinear` (early check) | Correct (loss 3–7e-4, grads 1e-2) but **15–35% slower**: per-layer bf16↔fp32 casts cost 5.4 s per step. |

**Consequences for the rest of the plan:**
- **C2/C3 only pay off with bf16 activations kept between layers** and a fast cast kernel, i.e. inside fused kernels (D/F), not as a per-op cast.
- **Memory residency: fixed, but it was not the main loss.** Strict `--membind` with B32 (14.4 GB) or B64 + CKPT (11.1 GB) stops the spill and the OOM: zero `numa_miss` and zero reclaim on a full node. Node throughput still did not rise: the B32 node sums are 150 (16-belt pretraining) and 21 (32-belt pretraining) frames/s, against 243 and 31 with B64 `--preferred`.
- **Throughput is limited by contention shared by groups of four domains.** The 32-belt step runs at 3.99 frames/s on one domain alone but 1.32 per domain from four domains upward, with the clock steady at 2.0 GHz. The likely cause is per-die bandwidth or L3 (unconfirmed: no counters). So phases B–F count for a full node only where they **cut memory traffic** (bf16 activations, fused attention, fusion), and every gate must be measured with ≥ 4 domains loaded, not on one domain alone.
- **Confirmed: DDR bandwidth per die (about 105 GB/s shared by four domains) is the bottleneck, and HBM is the lever.**
  - Each domain's own HBM gives 62 GB/s under any load: 988 GB/s per node, against 428 from DDR.
  - The `hbm_alloc` preload, which puts large torch buffers in a 3.8 GB HBM arena, gives on one die 16-belt pretraining 3.5× (36 → 126 frames/s for 4 domains) and 32-belt 1.3×.
  - On the whole node, 16-belt pretraining reaches 290–318 frames/s (DDR B32: 150; best DDR: 243), about 1/3.7–1/4.1 of a 4090. That is short of the one-die rate × 4 (about 500) because of the remaining contended DDR traffic and stragglers. 32-belt is unchanged at 21–22.
  - A new phase M (HBM memory placement; see `STAGE4_HANDOVER.md`) comes before D–F: shrink the per-rank working set below about 4 GB and place by heat.
- **Domain 12 on cn21348 runs about 10× slower** because foreign threads (root `sudo`, another user's `CSD_26`) share core 493. G needs a busy-core check at job start, plus excluding those cores or dropping the domain.
- **Per-rank batch for 32-belt:** B32 halves the global batch (512 per node) and is slower per frame under contention than B64. Prefer B64 + CKPT (not yet measured on a full node); this bears on decision §2.3.
- **The single-node target (one node = one 4090) is further away than estimated:** a 5–10× gap at node level.

## 1. Targets and current gap

The FLOPs per frame below are computed from the model shapes, counting forward + backward as 3 × forward. The GPU rate is the amax demo throughput times those FLOPs. The "needed" column is that GPU rate divided by 16 domains.

| Workload (B=64) | GFLOP per frame | 4090 throughput | 4090 effective rate | C2 domain now (fp32, KML shim) | Needed per domain | Gap |
|---|---|---|---|---|---|---|
| 16-belt pretraining | 50 | 1,188 frames/s | 60 TFLOP/s | 28.0 frames/s = 1.41 TFLOP/s | 3.7 TFLOP/s | **2.7×** |
| 16-belt decoder | 103 | 284 | 29 | 7.7 = 0.79 | 1.8 | **2.3×** |
| 32-belt pretraining | 274 | 219 | 60 | 2.34 = 0.64 | 3.7 | **5.8×** |
| 32-belt decoder | 326 | 134 | 44 | 1.84 = 0.60 | 2.7 | **4.6×** |
| Guided sampling S16/K50 | — | 2.0–2.1 s per frame | — | 32–37 s per frame | 32 s | **≈ 1× already** (16 frames in parallel per node) |

**Hardware headroom** (documented peaks: c2-doc `hardware.md`, S02; measured rates: this project):

| Engine, per domain | Documented peak at the observed 2.0 GHz | Measured |
|---|---|---|
| SVE fp32 | 4.9 TFLOP/s | torch OpenBLAS GEMM: 0.5–1.2 TFLOP/s |
| SME fp32 | 19.5 TFLOP/s | KML SME `sgemm`: 3.4–5.0 TFLOP/s |
| SME bf16 (widening to fp32) | about 39 TFLOP/s | not measured (`cblas_bgemm` exists in KML) |

- **Node totals:** about 80 TFLOP/s measured for fp32 GEMM, and up to about 300 / 600 TFLOP/s documented for SME fp32 / bf16. A 4090 offers about 82 TFLOP/s fp32 and 165 TFLOP/s bf16 dense; on this model it achieves 29–60 TFLOP/s effective.
- **The silicon is not the limit.** The software path is. The gap closes only if a training step runs mostly inside SME GEMM-class kernels at 50% or more of KML's GEMM rate, or with bf16 SME.

**Where the time goes now** (profiles `logs/opt_prof_s4.log` and `opt_diag_s4b.log`):

| Step | Linear GEMMs | Attention (torch flash) | Convolutions (oneDNN) | Copies, fills, elementwise | Other |
|---|---|---|---|---|---|
| 32-belt pretraining, 16.0 s | 6.0 s (~2.3 TFLOP/s) | 4.6 s (~1 TFLOP/s) | — | ~3.5 s | ~2 s |
| 16-belt decoder, 7.7 s | 1.5 s | 0.3 s | 3.3 s | ~1.5 s | ~1 s |

## 2. Guiding decisions (need your confirmation)

1. **Training precision: bf16 mixed precision with fp32 master weights.** The amax demo used exactly this (`autocast bf16`), so it keeps the planned numerics. It also doubles the SME rate. Anything bf16 that is slow on C2 (convolution backward, attention) runs in fp32 inside the bf16 step.
2. **Model architecture stays as specified.** That means 12 × 512 encoder, 928 tokens for the 32-electrode belt, and the U-Net channels (128, 256, 256, 512). Only kernels and execution change, so the results remain the planned method.
3. **Batch size and schedule are re-derived for C2 once, then fixed for every method.** One node trains with 16 data-parallel ranks, so the natural global batch is 16 × per-rank batch:
   - Choose a global batch of 256–1,024 and scale the learning rate. Validate it with a short convergence check (Phase G).
   - Freeze the schedule before any reported run.
   - Baselines get the same hardware and tuning budget (fair baselines).
4. **Throughput is measured on whole, exclusive nodes** (`cpu=608, -a "numa[count=16,distribution=pack]"`). Single-domain timings varied from 16 to 27 s for the same step on shared nodes.
5. **Fallback if one node cannot match a 4090 on 32-belt training:** multi-node data parallelism (2–4 nodes per run). That gives 4090-equivalent wall time per run. C2 has plenty of nodes, but node-hours per run go up.

## 3. Phases

Each phase has a gate. Each phase's result is logged under `eitfm/logs/opt_s4_<phase>_*.log` and added to the report. If a gate fails, stop and decide before going on.

### Phase A: measurement baseline (1–2 days)
- **A1. Whole-node benchmark harness.**
  - 16 processes, one per domain (38 threads each, `OMP_PROC_BIND=close OMP_PLACES=cores`, `numactl --membind` to the local DDR node), running the s4 step benchmark at once.
  - Measures per-domain and node throughput, and the slowdown from 16 domains sharing the memory system. That slowdown has not been measured; stage 3 saw 8%.
  - Repeat 3×. **Gate:** spread ≤ 5%.
- **A2. CPU frequency.**
  - Read `cpufreq` on allocated nodes: `scaling_cur_freq` under load, governor, `cpuinfo_max_freq`.
  - The observed maximum is 2.0 GHz, while the manuals give 2.6 / 3.12 GHz. If a queue or partition runs higher, that is 1.3–1.56× for free on every phase.
  - **[person]:** ask the C2 administrators whether 2.0 GHz is a cap and whether any queue allows more.
- **A3. Profiling setup.**
  - Set up DevKit top-down and Roofline `total` mode (documented as working, c2-doc `optimization.md`) on one training step.
  - Records memory-bound vs compute-bound per phase, so later phases target the right limit.
- **A4. Effective-FLOP counter** in the benchmark: FLOPs per frame from shapes (the table above), reported as TFLOP/s per domain next to frames/s.

### Phase B: every GEMM on KML at full rate (2–4 days)
- **B1.** Route all linear-layer GEMMs (forward `addmm` included) to KML.
  - The profile shows forward `addmm` at about 1.3 TFLOP/s, probably via oneDNN/ACL, not the shim.
  - Implement `KLinear`: an autograd Function using `kml_ops.gemm` (ctypes, `cblas_sgemm`) for forward, dX and dW, bias via sum.
  - Swap it into the encoder's feed-forward and output projections and the decoder's linears.
  - Route `nn.MultiheadAttention`'s packed in-projection through the same GEMM, with a small attention module that keeps identical parameters and state-dict keys.
- **B2. Shape tuning for the tall-skinny GEMMs** (59,392 × 512 × 2,048 and transposes):
  - KML at these shapes vs square.
  - `cblas_sgemm_pack` for weights reused across a step.
  - KML's `locking` vs `multi` builds.
  - Thread count per GEMM.
- **B3.** Bind and size the GN/NOSER baseline: KML LAPACK, or torch with bound threads, instead of numpy's unbound OpenBLAS.
- **Gate:** linear layers at ≥ 4 TFLOP/s per domain in the training step. Expected 32-belt pretraining time: about 16 → 13 s (estimate).

### Phase C: bf16 on the SME engine (3–5 days; biggest lever)
- **C1. Measure KML bf16 GEMM** (`cblas_bgemm`, `cblas_bgemm_pack`) on one domain at the model's shapes.
  - Read the signature from the installed `kblas.h`; c2-doc warns that manual and installed APIs differ.
  - **Gate C1:** ≥ 1.7× the fp32 SME rate. If it fails, skip C2/C3 and rely on B and D–F.
- **C2. bf16 `KLinear`:**
  - Casts activations and weights to bf16 for the GEMM, accumulates in fp32, keeps fp32 master weights and the AdamW state.
  - Equals the GPU's autocast semantics for linear layers.
  - Check loss curves against fp32 KLinear over 200 steps (relative difference ≤ 1%).
- **C3. Mixed policy:**
  - bf16 for linears and attention GEMMs.
  - fp32 for convolutions (oneDNN bf16 convolution backward falls back: 98 of 102 s), normalizations and softmax.
  - This replaces `torch.autocast`, which pushes convolutions to bf16.
- **Gate:** 16-belt pretraining ≥ 50 frames/s per domain, and 32-belt pretraining ≥ 5 frames/s.

### Phase D: fused attention on SME (5–10 days; highest risk)
- **The problem:** the 32-belt encoder spends 4.6 s per step in torch's flash attention at about 1 TFLOP/s. A bmm-based version was correct but 4–9× slower (`kml_ops.gemm_attention`, not used). So the fix must be a fused kernel, not more library calls.
- **D1. Toolchain check.**
  - Locate BiSheng `clang` on compute nodes (only `bisheng-lib` was seen) and build a minimal SME kernel with the documented target (`-mcpu=$C2_BISHENG_SME_TARGET`).
  - Run it.
  - c2-doc records a KUPL matrix example that compiled and then hit SIGILL. This is the main risk; check it first.
- **D2. Flash-attention forward and backward** as a torch C++ extension (built with `sw/gxx` or BiSheng against the `sw/torch_kml` headers):
  - Tiles of Q (64–128 rows) × K/V (all 928) per (batch, head).
  - S = QKᵀ and O = PV with SME outer products (`fmopa`), bf16 inputs, fp32 accumulation.
  - Online softmax in SVE.
  - Parallel over batch × head across 38 threads.
  - Fallback if SME intrinsics fail: call KML `bgemm` on 64 × 928 tiles inside the fused loop.
- **D3.** Validate against SDPA (≤ 2e-3 relative in bf16, ≤ 2e-6 in fp32), including gradients, at shapes [64, 8, 928, 64], [64, 8, 208, 64] and the decoder's cross-attention [64, 8, 256, 928].
- **Gate:** attention ≥ 4 TFLOP/s per domain, so the 32-belt pretraining attention drops from 4.6 s to ≤ 1.2 s.

### Phase E: convolutions (3–7 days)
- **E1.** Try a newer torch CPU build (2.8–2.9 aarch64 wheel, newer oneDNN and ACL).
  - Re-measure fp32 and bf16 convolution forward and backward at the U-Net shapes.
  - The bf16 backward fallback may be fixed there.
  - Python 3.9 limits wheel versions. If needed, build a CPython 3.11 in `sw/`, as was done for PETSc and gmsh.
- **E2.** If no wheel helps, build torch from source with `USE_MKLDNN_ACL=1`, ACL targeting `armv8.6-a+sve+bf16+i8mm`, and oneDNN's ACL convolution enabled.
- **E3.** Otherwise write an implicit-GEMM 3×3 convolution extension:
  - No explicit im2col: the earlier im2col version lost to its own data movement.
  - Packed tiles feeding SME or KML GEMM, for forward, dgrad and wgrad.
- **Gate:** U-Net convolutions (fwd+bwd) ≥ 3 TFLOP/s per domain, so the 16-belt decoder's 3.3 s of convolutions drops to ≤ 1.2 s.

### Phase F: fusion and overheads (2–3 days)
- **F1. Fix `torch.compile`.**
  - Inductor failed reading a root-only system egg-info (`syssentry`). Run Python with `-s` / `-I` and a site path that excludes `/usr/lib/python3.9/site-packages`, or use the CPython 3.11 from E1.
  - Use `sw/gxx` g++ 10.3 (SVE target) or BiSheng for codegen.
  - Compile the encoder block and the U-Net block, with the KML/SME kernels registered as custom ops so the compiler leaves them alone.
- **F2.** Cut copies, fills and contiguous calls (about 3.5 s per 32-belt step): in-place ops, preallocated buffers, `zero_grad(set_to_none=True)`, fused AdamW (`foreach`).
- **Gate:** non-GEMM time ≤ 15% of the step.

### Phase G: one node as one training device (3–5 days)
- **G1. Training script** (stage 6 of the plan) built on these kernels:
  - 16 ranks, one per domain.
  - Ranks talk through `torch.distributed` gloo over shared memory, or MPI/UCX per c2-doc `execution.md`.
  - Gradients are reduced in buckets that overlap with backward.
  - Each rank's memory is bound to its domain. The 32-belt case peaks near 30 GB per rank against 32 GB of DDR per domain, so use B = 32 per rank or activation checkpointing for the 32-belt.
  - Data loading on the main thread: the corpus is small and noise is added at load time.
- **G2.** Measure all-reduce cost: 67 M parameters, 268 MB fp32 or 134 MB bf16, per step.
- **G3.** Convergence check of the chosen global batch and learning rate on 200k frames for a short schedule (decision 3). Record the frozen schedule.
- **G4.** Multi-node: the same script on 2 and 4 nodes over the interconnect. Gives the fallback's scaling efficiency.
- **Gate:** node throughput ≥ 14 × the single-domain throughput (≥ 88% scaling); multi-node efficiency ≥ 80%.

### Phase H: evaluation and baselines (1–2 days)
- **H1. Guided sampling** is already at about 4090 parity per node: 16 frames in parallel at 32–37 s each, against 2.0 s per frame on the GPU.
  - Batch several frames per domain, which makes larger GEMMs.
  - Add the B–F kernels.
  - Shard the 200k test + OOD frames over nodes. About 120 node-hours per seed now; target ≤ 60.
- **H2.** Baselines (GREIT, GN variants, fully connected net, U-Net post-processing, D-bar, CDEIT, PINN) on the same C2 software stack, with the same tuning budget.

## 4. Expected outcome (estimates, to be replaced by gate measurements)

| Workload | Now (domain) | After B + C | + D (attention) | + E (convolutions) | + F (fusion) | Needed per domain | Estimated node / 4090 |
|---|---|---|---|---|---|---|---|
| 16-belt pretraining | 28 frames/s | 55–75 | 60–80 | — | 70–95 | 74 | 0.9–1.3 |
| 16-belt decoder | 7.7 | 9–11 | 10–12 | 15–20 | 17–23 | 17.8 | 0.9–1.3 |
| 32-belt pretraining | 2.34 | 4–6 | 7–10 | — | 8–12 | 13.7 | 0.6–0.9 |
| 32-belt decoder | 1.84 | 3–4 | 4.5–6 | 5.5–7.5 | 6–8.5 | 8.4 | 0.7–1.0 |

- **A higher CPU clock (A2), if available, multiplies everything by up to 1.3–1.56.**
- **16-electrode belt:** these estimates put one node at about one 4090.
- **32-electrode belt:** one node lands at about 0.6–1.0 of a 4090, so 2 nodes per run (G4) is the likely operating point.
- **Multi-domain scaling:** the estimates assume ≥ 88% scaling (G gate).

## 5. Order, dependencies and effort

- **Order:**
  1. A, B and C1 go first (cheap, and they decide everything after).
  2. D and E can run in parallel once B is done, because they touch different kernels.
  3. F comes after D and E, so the custom ops are registered.
  4. G needs B–F. H needs only B and C.
- **Effort:** about 4–6 weeks of agent work.
- **Highest-risk items:**
  - D1: SME code execution on these nodes.
  - E2: building torch from source on aarch64 without root.
- **Kill criteria:**
  - If C1 fails and D1 fails, plan on 2–3 nodes per 4090-equivalent rather than more kernel work.
  - If G scaling is below 75%, use 8 ranks × 76 cores (2 domains each) instead.

## 6. Items needing a person
- Confirm decisions 1–3 in §2 (bf16 mixed precision, fixed architecture, C2-derived batch and schedule).
- Ask the C2 administrators about the 2.0 GHz clock (A2) and about access to whole nodes for long jobs.
- Approve the node-hours: the plan's 6–10 4090-weeks of training and ablations would be about 7–14 k node-hours at one node per 4090, and up to about 2× that for the 32-belt at 2 nodes per run.

## 7. What already exists (reuse)

| Piece | Location |
|---|---|
| CPU PyTorch 2.7.1 | `sw/torch` |
| torch on BiSheng libomp (one OpenMP runtime) | `sw/torch_kml` |
| KML `sgemm_` preload shim | `sw/kml_shim` |
| `kml_ops` (ctypes KML GEMM, KConv2d, gemm_attention: correct, slower, off) | `demo/kml_ops.py` |
| Device-agnostic `s4_models.py` with env knobs | `demo/s4_models.py` |
| Benchmarks and profilers | `c2/opt/run_bench_s4*.sh`, `prof_s4.py`, `check_*.py` |
| Thread-binding rule: `OMP_PROC_BIND=close OMP_PLACES=cores` (unbound threads scale negatively) | `C2_OPTIMIZATION_REPORT.md` |
