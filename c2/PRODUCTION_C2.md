# Corpus production on C2: runbook (2026-11-02)

Layout: one whole-node job per shard of 12 cases, which is 48 tasks (case × placement × belt, 5 units each). The worker restricts itself to 3 single-thread slots per NUMA domain, so 48 slots run at once. The measured basis is `PILOT_C2_REPORT.md`: about 86 units/h per node, 0.56 core-h per unit, and results matching amax.

## Folders
| | where |
|---|---|
| stage-1 inputs (amax) | `/mnt/lvliannas/szl/thorax_eitfm_corpus_20261102/cases/<case>/{prep,body_base}.*`, code frozen in `code/` |
| corpus (C2) | `/home/share/songzhenlong/eitfm/corpus_20261102`: `code/` (frozen, `MD5SUMS`, `HASHES`), `cases/`, `shards/shard_00..09.txt`, `parts/`, `logs/` |
| results copy (amax) | `/mnt/lvliannas/szl/thorax_eitfm_corpus_20261102/c2/` (target of `sync_c2.sh pull`) |

**Launched 2026-11-02: `/home/share/songzhenlong/eitfm/corpus_shape_20261102`.**
- Frozen hashes: config `b1049eac1a` (25 contacts, shape 8 terms, max_rel 0.05), code `d8b2be8d1f`; the same code as pilot4.
- 119 cases in 40 shards of 3 (the last has 2), jobs 2013940–2013985.
- Each shard is 300 units, about 4 h on one node.
- `corpus_20261102` (old code `b51b488a63`) is superseded and was never run.
- **Result of the first pass (2026-11-03):** 38 of 40 shards finished. Units took 9,862–19,604 s per shard.
  - Shards 17 and 19 hit the 6 h limit: the batch system sent SIGTERM (signal 15) mid-solve, leaving 24 units unfinished. All were 16_adjacent contacts 19–24, the last in the queue.
  - 11,876 of 11,900 units are present, 5.7 GB of parts.
  - Both shards were resubmitted with `prod_submit.sh` (14 and 10 units left). The first resubmission (jobs 2015256 and 2015257) used relative shard paths and failed at once, since the jobs run in another folder. **Always pass absolute shard paths.** The second (jobs 2015720 and 2015721) used absolute paths.
  - First pull to amax: 11,876 units, 36,487 files.
- **Complete (2026-11-03):** 11,900 units, 1,190,000 pairs, 0 FAILED, 0 run folders left, every shard log has `PROD_SHARD_DONE`.
  - All units are pulled to amax `/mnt/lvliannas/szl/thorax_eitfm_corpus_20261102/c2`: 11,900 json + 11,900 npz, a 11,900-row manifest, 5.4 GB.
  - The sorted list of parts names and sizes has the same md5 on both hosts.
  - On amax: the frozen `code/` was copied from C2 (MD5SUMS OK) so the analysis scripts can import it. `p4_report.py` passes. `visibility.csv` was written with `p4_vis_flags.py <c2 dir> <corpus>/cases <c2 dir>/cases`; its new third argument is the placements folder, because the NAS has no symlinks. Results are in `reports/P4_corpus.md` §9.
  - Fix in `sync_c2.sh`: the incremental pull failed because C2 and amax sort in different locales and `comm` refused the lists. The script now sets `LC_ALL=C`, both locally and in the remote `sort`.

**Worker change.** `prod_tasks.sh` replaces `opt/run_c2_tasks.sh`. Each solve task is now one unit (one contact), not a whole task: with 25 contacts a whole task would be 25 units in series, about 13 h. It uses the same per-unit placeholder folders as the P4 pilots.
- Tested in `prod_test2` (job 2013719): s0040, 25 contacts, small units.
- Result: 100/100 units, 100 distinct shape draws, 4 Jacobian units, 0 failures, no leftover run folders, manifest of 100 rows.
- Timing: meshes 807 s, units 1,221 s.

## Steps
1. **Stage-1 inputs, done for all 119 cases.** On amax: `amax_prep.sh <amax corpus dir>`. It runs `s1_prepare` and `s2_mesh SURFACE_ONLY=1`, is resumable, and lists `gap_ok false` cases.
2. **Push the inputs.** On the PC:
   ```
   sync_c2.sh push <amax corpus dir> <c2 corpus dir> <case list>
   ```
   Only missing files are sent, gzipped.
3. **Set up the corpus, done.** On the C2 login node: `prod_setup.sh <c2 corpus dir> <case list> 12`. It freezes the code and writes the shards. It refuses to overwrite an existing `code/`.
4. **Submit.** On the C2 login node: `prod_submit.sh <c2 corpus dir> [shard files]`.
   - It submits `cpu=608,mem=480000MB -a "numa[count=16,distribution=pack]" -T 21600` per unfinished shard and skips complete shards. The `numa` option is required: without it, even cpu=608 gives one core per domain.
   - Inside each job, `prod_c2.sh` checks the inputs, picks 3 cores per domain and runs the frozen `run_c2_tasks.sh`: placements, 1-thread meshes, units, manifest.
   - Each job then prints `units present <done> <wanted>`.
5. **Resume.** Rerun `prod_submit.sh`. Finished meshes and units are skipped.
6. **Return the results.** On the PC, repeatable:
   ```
   sync_c2.sh pull <c2 corpus dir> <amax results dir>
   ```
   It rebuilds the manifest on C2, then copies new `parts/*`, placement and mesh sidecars, logs and `manifest.csv`. The meshes (~25 MB each) stay on C2.
7. **Visibility flags.** On amax, after the last pull:
   ```
   python -I demo/p4_vis_flags.py <amax results dir> <amax corpus dir>/cases
   ```
   It writes the sidecar `visibility.csv`, one row per pair, with `visible`, `visible_side` and `visible_silent`. It needs only the parts and the stage-1 `prep.npz` and `placements.json`, and leaves the corpus hashes untouched. Its check line must show pathology-free pairs with max |ratio − 1| at float16 level (pilot3: 0.004). P4 decided to keep low-contrast pathologies and flag them, rather than resize them.

## Expected cost (from pilot4, not yet measured at scale)
- **Units:** 11,900 (1.19 M pairs), about 6,900 core-hours.
- **Wall time:** about 0.25 h of meshing (6 meshes per shard) plus about 4 h for units per shard. Almost all 40 shards started at once.
- **Return volume:** about 6 GB of parts. Most units are ~0.25–0.5 MB; contact-0 units are bigger because they hold the Jacobian. That is a few hours over the PC link.

## Tested
`prod_test` (job 2009838): s0040, 1 shard, small units (1 contact × 1 baseline × 2 breaths).
- 48 slots on cores 0–2, 38–40, …, 570–572.
- 2 meshes in 798 s; 4 units; manifest.
- `prod_submit.sh` reported the shard complete.
- push, and pull twice: the second pass copied only the manifest and logs; unit files md5-identical on both sides.

## Gate
The full submission waits on approval of the P4 pilot report (plan rule: pilot before scale, stop at gates).
