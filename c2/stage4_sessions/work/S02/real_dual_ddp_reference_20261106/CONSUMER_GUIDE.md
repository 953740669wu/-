# S02 reference consumer contract

Read INTERFACE_READY.json first, then REFERENCE_READY.json. Bind the exact ZIP,
SOURCE_SHA256.json, task card and interface SHA. Only REFERENCE_READY freezes the
implementation. S07 owns its new deployment, DDP graph and actual run; this
reference has no submission or standalone training command.

Import once from the staged reference root. Its `baseline/` is the only
`kml_ops` origin for training, reference, probe and restore. The unchanged
`diagnostic_common.configure_backend` checks that origin and actual KML rather
than accepting native fallback. Do not add R12 candidate or a second baseline.

```python
sys.path.insert(0, str(reference_root))
import dual_reference as ref
assert Path(ref.__file__).resolve() == reference_root / 'dual_reference.py'
# S07 has already checked job/CPU before importing torch.
runtime, selected = ref.configure_backend(torch, 'kml', selected36)
metadata, loaded, normalization, ledger = ref.load_data(
    descriptor, ref.DESCRIPTOR_SHA256, new_rank_ledger)
encoder, opt, angles, post_init_rng, initialization = ref.initialize(torch)
mask_stream = ref.new_mask_stream(torch, post_init_rng)
# S07 wraps the SAME encoder in its pretraining graph and real DDP.
# Only rank0 creates ref.B64Reference(torch), with RNG isolation.
p = ref.plan(step)
mask = mask_stream.next(step)
frame_ids = [loaded['train']['frame_ids'][i] for i in p['global_indices']]
ref.check_identity(step, frame_ids, mask)
global_values = ref.training.batch(torch, loaded['train'], p['global_indices'], angles)
local_values, local_mask = ref.shard(torch, global_values, mask, rank)
```

Before each real exposure S07 records attempt/confirm (or possible interrupted
use) in a NEW ledger. Per-rank training indices are `p['rank_indices'][rank]`;
global reference observations are the original64 only for steps1..5. Reading
all1600 for train-only normalization and consuming32 for a rank update are
different uses. Never write the old descriptor's runtime ledger. No val/test.

Full training forward must be `ddp(...)` and include Encoder and BOTH heads.
S07 reduces detached global component counts and log sums. Backward uses
`2*(local_voltage_sum/global_mask_count + local_coarse_sum/global_coarse_count)`.
Do not detach the differentiable local sums, average local means, divide DDP
parameter gradients again, resample zero local masks or add an epsilon.

For each first-five step S07 runs the real32/rank update and the original B64
reference sequentially in the same global step (either local order must still
be supervised/bounded). `reference.advance(step, global_values, mask, metrics)`
does not log exposure for S07. It performs one original B64 train_step, not two
microbatches. Current outputs/loss/input grads can be inspected through its
return value; do not retain that dict after this step.

Gather rank0 then rank1 detached outputs and RAW input gradients to rank0.
Use canonical `h=[64,208,512]`, `v=[64,208,1]`, `coarse=[64,256]`. The got dict's
losses must be true global voltage/coarse/total, not a world-scaled local loss.
Pass the original encoder object and the actual optimizer to
`reference.compare(step, ddp.module.encoder, optimizer, got, metrics)` solely
for inspection. This adapter divides raw concatenated input grads by2, compares
already-averaged parameter grads unchanged, and requires all original names
(including both heads) and every optimizer parameter/state. No key filtering or
prefix-stripping heuristics. Update deltas are from original seed0 initialization,
matching the frozen R12 comparator runner. Exact AdamW step checks raise directly
and are not numerical metric rows in the original comparator.

On a gate failure, save the first failure, fail the peer under S07 supervision
and stop; no different reference/threshold. After successful step5 explicitly
`reference.close(); del reference` and any returned capture. There is at most
one pending step and one initial-parameter snapshot; no list of all-step model
copies. Continue steps6..25 on the SAME DDP model/optimizer. Checkpoint the private
`mask_stream.state_dict()` as well as each rank's process RNG; restore requires
cursor/generator agreement and zero optimizer updates. S07 owns this verification.

Local reproducible helper checks, using an existing environment (no install):

```powershell
& 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe' -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\real_dual_ddp_reference_20261106\tests\test_dual_reference.py'
```

This Windows Torch2.7.1 environment reproduces all25 original mask hashes and
full153-name coverage, but its untouched seed0 Encoder weight SHA is
411aa36f4d120512d7de6e6646733ea898a99531144cac84688a9ef1c2a567dd,
different from frozen C2 SHA
2543d05f25883b654141cbc5dc1bb093906e3b360f11ec9f5e87cb4f8bad76b5.
The first failing check and standalone original-model diagnostic are preserved.
Runtime initialize STILL REJECTS this mismatch. Final helper tests verify that
rejection and masks independently; they do not turn Windows initialization into
C2 acceptance. No real-data loading, complete B64 training, KML or real DDP was
run by S02. S01 must review this boundary; actual R4/C2 initialization must still
match the ORIGINAL frozen hash before any training, otherwise stop.
