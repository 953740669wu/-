# Phase 4 pilot rerun on C2 vs amax (2026-11-02)

Same 100 units as the amax pilot (`/mnt/lvliannas/szl/thorax_eitfm_pilot_20261101`): 5 cases (s0040, s0369, s0628, s0913, s1233) × 2 placements × 2 belts × 5 contacts, 100 pairs and 105 solves per unit.

- **Inputs:** prep, placements and meshes were copied from amax; their md5 matches. Mesh median is 514k nodes. Config hash `ff867cf3b6` matches the pilot.
- **C2 runs:**
  - Optimized code (`opt/code`, code hash `b51b488a63`) with CHOLMOD on KML (`env.sh`).
  - One single-thread process per unit; 2 whole-node jobs (2009337 on cn21339, 2009338 on cn21340), 50 units each, round-robin over the 16 NUMA domains (3 per domain, 4 in domains 0–1).
  - Scripts: `pilot_c2.sh`, `pilot_c2_compare.py`. Logs: `eitfm/logs/pilot_c2_{a,b}.log`. Outputs: `eitfm/pilot_c2/parts`.
- **amax pilot:** old code with MUMPS, 20 tasks × 3 threads (60 of 96 Xeon Gold 5418Y cores). Each task runs its 5 contacts in sequence.

## Correctness
- **79/100 units float32-identical to amax.** In the other 21, only `v_cur` differs, by at most 1.5e-8 of the array maximum. That is below one float32 step (about 6e-8), so it is last-bit rounding of float64 values that differ near 1e-15.
- **Identical everywhere:** `v_ref`, `images` and `J_img`. `J_img` is stored only for contact 0 of each task: 20 units.
- **C2 checks:**
  - conservation ≤ 2.1e-12 A
  - reciprocity ≤ 6.1e-14
  - all finite
  - peak RSS ≤ 5.68 GB
  - no failed units

## Timing (medians per unit)

| | amax 16-belt | C2 16-belt | amax 32-belt | C2 32-belt |
|---|---|---|---|---|
| assembly | 453 s | 51 s (+18 s map) | 446 s | 50 s (+18 s map) |
| factorization (105) | 1799 s | 1344 s | 1772 s | 1388 s |
| solve | 482 s | 239 s | 965 s | 413 s |
| setup + states + targets + Jacobian | 130 s | 201 s | 204 s | 276 s |
| **unit wall** | **2818 s** (2620–3574) | **1784 s** (1398–3892) | **3295 s** (2672–4254) | **2018 s** (1525–3149) |
| cores per unit | 3 | 1 | 3 | 1 |

- **Refactorization on C2:** median 12.6–12.9 s per solve on these meshes.
- **Single-thread Python steps** (setup, states) are about 1.7–1.9× slower on C2's 2.0 GHz cores.

## Throughput

| | amax | C2, per node |
|---|---|---|
| Batch as run (includes the tail) | 100 units in 5.26 h on 60 cores: **19 units/h** | node a 50 in 4012 s: **45/h**; node b 50 in 2766 s: **65/h** |
| Steady state (slots ÷ mean unit wall) | 20 × 3600 / ~3060 s ≈ **24 units/h** | 48 × 3600 / ~2000 s ≈ **86 units/h** |
| Core-hours per unit | ~2.6 (3 × 3060 s); 3.2 counting idle tail | **~0.56** |

- **Node a's wall time:** set by one unit, s0913 p0 16_adjacent c4, in domain 0. It took 3891 s, with refactorization at 29.8 s per solve against about 17 s for its neighbours.
  - Domain 0's 4-unit group averaged 2400 s on node a but 2024 s on node b. That points to node-specific load in domain 0, though this was not confirmed.
  - Mean unit wall is otherwise the same on both nodes (2038 vs 1957 s).
- **The batch runs were single waves.** A queue-fed production run (476 tasks of 5 units) amortizes such stragglers, so the steady-state row is the production estimate.
- **Rerun overhead:** splitting tasks into single-contact processes repeats about 1 min of setup per unit (setup 45 s + map 18 s), about 3% of unit wall.

## Corpus estimate (2,380 units: 119 cases × 2 placements × 2 belts × 5 contacts)

| | Wall time | CPU cost |
|---|---|---|
| amax (old code) | ~4–5 days | |
| C2, 1 node | ~28 h | ~1,330 core-hours |
| C2, 10 nodes | ~3 h | |

The C2 figures exclude meshing.
