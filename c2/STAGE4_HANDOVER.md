# Stage 4 on C2: optimization handover (2026-11-03)

This is where the work on running Stage 4 training (`s4_models.py`) efficiently on C2 Kunpeng nodes stopped, and how to pick it up again. Read it with:
- `STAGE4_C2_PLAN.md`: the plan and the phase gates.
- `C2_OPTIMIZATION_REPORT.md`: every measurement, with its log.

Nothing here changes the model or the experiment. All changes are kernels, memory placement and the launcher.

## 1. Where it stands

The goal is one C2 node (16 NUMA domains × 38 cores) delivering the throughput of one RTX 4090.

| frames/s per node | 16-belt pretrain | 16-belt decoder | 32-belt pretrain | 32-belt decoder |
|---|---|---|---|---|
| RTX 4090 | 1,188 | 284 | 219 | 134 |
| whole node, DDR only, B64 `--preferred` (measured) | 233–243 | 49–76 | 31–33 | 20–21 |
| whole node, DDR only, B32 `--membind` (measured) | 150 | 43–46 | 21–22 | 16.5–17 |
| whole node, DDR only, B64 + CKPT (measured) | 118–121 | 42–56 | 16.6–16.8 | 14.0–14.3 |
| **whole node, HBM, B32 (measured, best so far)** | **290–318** | **72–75** | 21.4–21.9 | 18.0–18.3 |
| one die (4 domains) with HBM, × 4 (upper bound not reached) | about 500 | about 117 | about 29 | about 24 |

**Best so far against a 4090:**
- 16-belt pretraining: 1/3.7–1/4.1.
- 16-belt decoder: 1/3.8.
- 32-belt pretraining: 1/10.
- 32-belt decoder: 1/7.4.

**What we learned, in order of importance:**
1. **The node is memory-bandwidth bound.** Each die (four domains, NUMA distance 20) shares about 105 GB/s of DDR. One domain alone gets 102 GB/s; four together get 26 GB/s each. So one domain run in isolation overstates a full node by about 3×. **Measure every gate with at least four domains loaded** (`run_node16.sh NDOM=4`).
2. **Each domain's HBM is a free 4 GB pool (2 MB hugetlb pages) at 62 GB/s that does not degrade under load.** `hbm_alloc` puts torch's large buffers there.
   - On one die: 16-belt pretraining 3.5×, 32-belt 1.3×.
   - On the whole node: 16-belt about 2×, 32-belt none. The rest of the working set stays on contended DDR, and stragglers persist.
   - The bigger the share of the working set that fits in about 4 GB, the bigger the gain.
3. **Residency.** With `--preferred`, allocations spill to remote DDR. B64 on 32-belt is OOM-killed under strict `--membind` (about 31 GB needed against 20–29 GB free). B32 needs 14.4 GB and B64 + CKPT 11.1 GB, and both stay local. Neither raises throughput on its own.
4. **GEMMs.**
   - KML SME sgemm through the LD_PRELOAD shim is the base.
   - fp32 `KLinear` is exact but takes only the linears from 6.0 to 4.3 s.
   - bf16 GEMM (`cblas_bgemm`) runs 2.0–3.5× fp32 on forward and dX, but per-op casts make bf16 `KLinear` 15–35% slower.
   - bf16 pays only with bf16 activations kept between layers.
5. **Hosts.**
   - Some nodes run foreign threads on a few cores; one shared core slows that domain up to 10×. `SKIP_BUSY=1` drops those cores.
   - 2.0 GHz is the hardware maximum.
   - There is no DevKit, perf or headers on compute nodes, so no hardware counters; gcc works in jobs.

## 2. How to run (cluster `hpc-vpn`, `/home/share/songzhenlong/eitfm`, Donau queue `q_hpcai`)

```bash
source /etc/profile.d/donaukit_scheduler.sh
H=/home/share/songzhenlong/eitfm
dsub -q q_hpcai -n eitfm_x -R cpu=608,mem=480000MB -a "numa[count=16,distribution=pack]" -T 14400 \
  -oo $H/logs/opt_s4_A1_x.log bash -c "cp $H/opt/run_node16.sh /tmp/n16_\$\$.sh && \
  ROUNDS=2 SKIP_BUSY=1 HBM=1 bash /tmp/n16_\$\$.sh x BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32"
```

- **Copy a launcher to `/tmp` before running it:** bash reads scripts while they run, so editing a script in place breaks running jobs.
- **Per-process environment** (`run_node16.sh` sets it):
  - `PYTHONPATH=$H/sw/torch_kml:$H/opt/code`
  - `LD_PRELOAD=$H/sw/kml_shim/libkml_sgemm_shim.so`; with HBM, `$H/sw/hbm_alloc/libhbm_alloc.so` goes in front.
  - `KML_BLAS_LIB=/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so`; `LD_LIBRARY_PATH` gets `kml-lib` and `bisheng-lib`.
  - `OMP_PROC_BIND=close OMP_PLACES=cores`.
  - `numactl --physcpubind=<domain cores> --membind=d` (with HBM: `--membind=d,16+d`, `HBM_NODE=16+d`).
- **`run_node16.sh` knobs:**
  - `ROUNDS`, `REPS`.
  - `MEMPOL` (`membind` or `preferred`).
  - `SKIP_BUSY=1`: drop cores already busy.
  - `HBM=1`.
  - `NDOM=n`: first n domains only; 4 = one die.
- **`s4_models.py` knobs:**
  - `BATCH`.
  - `BELTS` (`16_adjacent,32_skip4`), `PARTS` (`pre,dec`).
  - `CKPT=1`: per-layer activation checkpointing.
  - `KML_LINEAR=1` and `LINEAR_DTYPE=fp32|bf16`.
  - `SYNC_DIR`/`SYNC_N`: phase barrier.
  - `TIMING_OUT`.
- **`hbm_alloc` knobs:** `HBM_NODE`, `HBM_MB` (default 3800), `HBM_MIN_KB` (default 256), `HBM_STATS=1`.
- **Rebuilding the preload libraries** (inside a job, with gcc): `gcc -O2 -shared -fPIC -o $H/sw/hbm_alloc/libhbm_alloc.so $H/opt/hbm_alloc.c -lpthread` (see `run_hbm_ab.sh`), and `run_kml_shim.sh` for the KML shim.

## 3. Files (this archive mirrors `demo/`)

| File | Role |
|---|---|
| `s4_models.py` | Stage 4 models and step timing, device-agnostic, with the knobs above. Cluster copy: `eitfm/opt/code/` |
| `kml_ops.py` | KML GEMM via ctypes (`sgemm`, `bgemm`, `sbgemm` conventions in its header), `KLinear` |
| `c2/opt/kml_sgemm_shim.c`, `run_kml_shim.sh` | LD_PRELOAD shim: torch BLAS `sgemm_` → KML SME |
| `c2/opt/hbm_alloc.c` | LD_PRELOAD HBM arena for large torch buffers |
| `c2/opt/run_node16.sh` | Whole-node / one-die harness, gate A1 summary |
| `c2/opt/run_scale_probe.sh` | 1/4/8/16-domain scaling of one step |
| `c2/opt/hbm_probe.py`, `run_hbm_probe.sh` | DDR vs HBM triad bandwidth under load |
| `c2/opt/run_hbm_ab.sh` | Allocator check plus one-die DDR/HBM A/B |
| `c2/opt/run_hbm_fix.sh` | One-domain check of the SIGBUS fix (arena capped to the node's free hugepages) |
| `c2/opt/run_mem_probe.sh` | One-domain memory: B64 / B32 / B64 + CKPT under `--membind` |
| `c2/opt/bench_gemm.py`, `probe_bgemm.py`, `probe_sbgemm.py`, `check_linear.py`, `run_prof_klinear.sh`, `prof_s4.py`, `run_prof_s4.sh` | GEMM benchmarks, bf16 probes, `KLinear` check, profiles |
| `c2/STAGE4_C2_PLAN.md`, `c2/C2_OPTIMIZATION_REPORT.md` | Plan with gate status; full measurements |

Cluster outputs are in `eitfm/opt/s4/reports/<tag>/` (per-domain `r<round>_d<domain>.json` and `.log`). Logs are in `eitfm/logs/opt_*.log`.

## 4. Open issues at handover

No jobs are running. The cluster's `eitfm/opt/run_node16.sh` is the current version, identical to this archive (md5 e11cb0ef…); the old one is kept as `run_node16_old.sh`. `sw/hbm_alloc/libhbm_alloc.so` is built from the fixed `hbm_alloc.c`.

1. **Rerun B64 + CKPT + HBM (32-belt) on the whole node.** The earlier run hit SIGBUS on 1–2 domains, because one HBM node's hugepage pool was short. That is now fixed (arena sized from the node's free pages; reservation counted on the HBM node only) and tested on one domain only.
   ```bash
   ROUNDS=2 SKIP_BUSY=1 HBM=1 bash run_node16.sh node16_b64ckpt_hbm2 BATCH=64 CKPT=1 BELTS=32_skip4 KML_LINEAR=1 LINEAR_DTYPE=fp32
   ```
   CKPT costs time on DDR (16-belt pretraining 121 against 150 for B32), so test B32 + CKPT + HBM as well.
2. **Stragglers persist with `SKIP_BUSY=1`:** 1–2 domains per round at 3 frames/s against a median of 18–20 (16-belt). `ps` is a lifetime-average snapshot taken before the round, which misses bursts. Next: sample per-core load during the run, or give each rank fewer than 38 threads (for example 36) as slack.
3. **A single unexplained 16-belt pretraining round-to-round spread of 9.4%** with HBM.

## 5. Next steps and time estimate

Estimates are working days for one person with cluster access. Every gate is measured at one die (NDOM=4) and then the whole node.

| Step | What | Days | Expected effect |
|---|---|---|---|
| M1 | Fix the stragglers and rerun the CKPT + HBM cases (§4); repeat on 2 hosts | 1 | 16-belt from about 300 toward about 400–500 frames/s |
| M2 | Fit the per-rank working set in about 4 GB: CKPT, B16/B32 per rank with gradient accumulation, free or reuse buffers | 1–2 | Raises 32-belt gain beyond 1.3×. Batch semantics must match the GPU run (plan §2.3) |
| M3 | Heat-based placement in `hbm_alloc`: weights, grads, optimizer state, attention/softmax buffers first; a size-class allowlist from an `HBM_STATS` trace | 2–3 | More HBM traffic per GB of arena |
| C/F | bf16 activations kept between layers (halves bytes moved; bf16 GEMM is already 2–3.5× faster) with fused casts | 3–5 | Bandwidth-bound, so roughly up to 2× on top |
| D | Fused attention on SME (no N² score buffer in memory) | 5–10 | Largest for 32-belt (long sequences); highest risk |
| G | 16 ranks as one data-parallel device: gradient all-reduce, straggler handling, busy-core check at start | 3–5 | Needed for real training |

**Estimate:**
- **16-belt:** now 1/3.7–1/4.1 of a 4090 per node (measured). M1–M3 (about 1–1.5 weeks) likely bring it to about 1/2.5–1/3. With C/F, perhaps about 1/2.
- **32-belt:** now 1/10 (measured), and HBM does not yet help on the whole node. It needs M2 plus D; after about 3–4 weeks it is realistically 1/4–1/6 of a 4090.
- **Full parity** with one 4090 on a single node is **not expected**: per-node bandwidth is about 1.4 TB/s (HBM plus DDR), the 4090's 1 TB/s is used far more efficiently, and fp32/bf16 compute is lower.
- **The practical plan** is several nodes per training run once G is in place.
