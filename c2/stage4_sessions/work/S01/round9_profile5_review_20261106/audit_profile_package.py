"""R9 frozen package/reference audit only; no Torch, profiler or model runs."""
from pathlib import Path
import ast
import hashlib
import json
import random
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
CODE = WORK / 'S02/round9_profile5_20261106T023240Z'
OLD = WORK / 'S02/overnight_engineering_20261105'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(info):
    path = Path(info['path'])
    assert sha(path) == info['sha256'] and path.stat().st_size == info['bytes'], str(path)
    return path


ready = load(CODE / 'PROFILE_READY.json')
assert ready['immutable_after_publish'] is True and ready['protocol'] == 'ENGINEERING_REAL_CORPUS_PROFILE5_V1'
assert ready['package']['sha256'] == '15621eaa3328e407059c352d86a0f49ee68bfea39f02a68503ded6f94099abe3'
assert ready['source_manifest']['sha256'] == '2a86fd01cab96a85cb2f0f4c8ed998edb956ef81255dfd5ceb950d41264de741'
assert ready['package']['bytes'] == 69674
for field in ('package', 'source_manifest', 'contract', 'reference', 'checks', 'report', 'commands', 'diff', 'baseline_timing'):
    asset(ready[field])
sources = load(asset(ready['source_manifest']))
assert len(sources) == 24
with zipfile.ZipFile(asset(ready['package'])) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist()) == len(set(archive.namelist())) == 25
    assert set(archive.namelist()) == set(sources) | {'SOURCE_SHA256.json'}
    for name in archive.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name and '\\' not in name
        assert archive.read(name) == (CODE / name).read_bytes(), name
    target = HERE / 'frozen_code'
    assert not target.exists(), 'keep the existing audit copy immutable'
    archive.extractall(target)
for name, digest in sources.items():
    assert sha(CODE / name) == digest
    if name.endswith('.py'):
        ast.parse((CODE / name).read_text(encoding='utf-8'), feature_version=(3, 9))
checks = load(asset(ready['checks']))
for name in checks['unchanged_frozen_files']:
    assert sha(CODE / name) == sha(OLD / name), name
assert len(checks['unchanged_frozen_files']) == 16
assert checks['native_fixture_tests'] == 6 and checks['full_encoder_runs'] == checks['new_jobs'] == 0
log = CODE / checks['test_log']
assert 'Ran 6 tests' in log.read_text(encoding='utf-8') and '\nOK' in log.read_text(encoding='utf-8')
for entry in checks['cli_rejections']:
    assert entry['exit'] == 2 and entry['before_framework'] is True
    if 'result' in entry:
        result = load(Path(entry['result']))
        assert result['status'] == 'DATA_NOT_READY' and 'cpu36' not in result
contract = load(asset(ready['contract']))
assert contract['updates'] == dict(total=5, warmup=[1, 2], cpu_samples=[3, 4, 5], optimizer_reinitialized_between_steps=False, checkpoint_restore_extra_updates=0)
limits = contract['profiling']
assert limits['max_events_per_sample'] == 50000 and limits['max_kml_markers_per_sample'] == 256
assert limits['max_traces'] == limits['max_event_summaries'] == 3
assert limits['trace_bytes_each'] == 8388608 and limits['summary_bytes_each'] == 1048576
assert limits['trace_and_summary_total_max_bytes'] == 3 * (limits['trace_bytes_each'] + limits['summary_bytes_each'])
assert ready['resources'] == contract['resources'] == dict(allocated_cores=38, actual_physical_cores=36,
    reserved_cores=2, memory_MB=24576, memory_limit_MB=24576, exclusive=True, job_seconds=900,
    whole_entry_timeout=840, cleanup_seconds=30, closing_seconds=30, stop_new_update_after_seconds=720)
reference = load(asset(ready['reference']))
timing = load(asset(ready['baseline_timing']))
for info in timing['bindings'].values():
    asset(info)  # Identity only; do not repeat the old full engineering audit.
original = load(asset(timing['bindings']['application_result']))
descriptor = WORK / 'S00/overnight_engineering_20261105/ENGINEERING_DESCRIPTOR.json'
assert sha(descriptor) == reference['descriptor_sha256'] == contract['baseline_descriptor_sha256'] == 'b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
description = load(descriptor)
assert reference['corpus'] == description['corpus'] and reference['units'] == description['train']
assert reference['initialization'] == original['initialization'] and reference['normalization'] == original['normalization']
assert len(reference['steps']) == 5
order = list(range(1600))
random.Random(0).shuffle(order)
with asset(timing['bindings']['steps']).open(encoding='utf-8') as stream:
    first5 = [json.loads(next(stream)) for _ in range(5)]
for step, row in zip(reference['steps'], first5):
    for key in ('step', 'frame_indices', 'mask_sha256', 'losses', 'kml_calls'):
        assert step[key] == row[key], (step['step'], key)
    assert step['frame_ids_sha256'] == hashlib.sha256(json.dumps(row['frame_ids'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert row['frame_indices'] == order[(step['step'] - 1) * 64:step['step'] * 64]
assert len({i for row in first5 for i in row['frame_indices']}) == 320
assert len({row['mask_sha256'] for row in first5}) == 5
result = dict(status='PROFILE_CODE_REVIEW_PASS_DEPLOYMENT_PENDING', package=ready['package'],
    source_manifest=ready['source_manifest'], contract=ready['contract'], reference=ready['reference'],
    profile_ready=dict(path=str(CODE / 'PROFILE_READY.json'), sha256=sha(CODE / 'PROFILE_READY.json')),
    descriptor=dict(path=str(descriptor), bytes=descriptor.stat().st_size, sha256=sha(descriptor)),
    source_files=24, zip_members=25, original_unchanged_files=16, baseline_bindings=7,
    first5_reference='EXACT_INITIALIZATION_NORMALIZATION_FRAME_MASK_LOSS_KML_FROM_BOUND_ORIGINALS',
    local_fixture_receipts=6, local_fixture_log_sha256=sha(log),
    new_model_runs=0, new_profiler_runs=0, new_jobs=0, blocking_findings=[],
    remaining='New S00 native identity/resources/time/cleanup/profile completeness gates and collection must be reviewed before release',
    unrun=['C2 profiler capability', 'real CPU/KML/all TID profiling', 'native process-signal cleanup'])
(HERE / 'code_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S02_FROZEN_PROFILE_READY.json').write_bytes((CODE / 'PROFILE_READY.json').read_bytes())
print(json.dumps(result, indent=2))
