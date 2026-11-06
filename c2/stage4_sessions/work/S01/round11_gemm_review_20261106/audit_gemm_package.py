"""Frozen R11 source/metadata receipts only; no model, Torch or KML execution."""
from pathlib import Path
import ast
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
CODE = WORK / 'S02/round11_gemm_breakdown_20261106'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(info):
    path = Path(info['path'])
    assert sha(path) == info['sha256'] and path.stat().st_size == info['bytes'], str(path)
    return path


ready = load(CODE / 'GEMM_READY.json')
assert ready['status'] == 'GEMM_READY' and ready['protocol'] == 'ENGINEERING_REAL_CORPUS_GEMM5_V1'
assert ready['immutable_after_publish'] is True
for value in ready.values():
    if isinstance(value, dict) and 'path' in value and 'sha256' in value:
        asset(value)
assert asset(ready['interface']).read_bytes() == (HERE / 'INTERFACE_FROZEN_COPY.json').read_bytes()
sources = load(asset(ready['source_manifest']))
assert len(sources) == 26 and ready['file_count'] == 27
with zipfile.ZipFile(asset(ready['package'])) as archive:
    assert archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist())) == 27
    assert set(archive.namelist()) == set(sources) | {'SOURCE_SHA256.json'}
    for name in archive.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name and '\\' not in name
        assert archive.read(name) == (CODE / name).read_bytes(), name
    target = HERE / 'frozen_code'
    assert not target.exists(), 'keep first frozen audit copy immutable'
    archive.extractall(target)
for name, digest in sources.items():
    assert sha(CODE / name) == digest
    if name.endswith('.py'):
        ast.parse((CODE / name).read_text(encoding='utf-8'), feature_version=(3, 9))
draft = load(HERE / 'preliminary_code_review.json')
for name, digest in draft['sources'].items():
    assert sources[name] == digest, ('changed since manual source review', name)
protected = load(CODE / 'evidence/PROTECTED_INPUTS.json')
r9 = Path(protected['r9_root'])
assert sha(r9 / 'SOURCE_SHA256.json') == protected['r9_manifest_sha256']
for name, digest in protected['r9_files'].items():
    assert sha(r9 / name) == digest, name
for name, original in protected['copied_paths'].items():
    assert sha(CODE / name) == sha(r9 / original), name
assert len(protected['copied_paths']) == 17
assert ready['baseline']['sha256'] == sources['baseline/kml_ops.py'] == 'e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
assert ready['original_data_interface']['sha256'] == '8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669'
assert ready['reference']['sha256'] == '2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8'
contract = load(asset(ready['contract']))
assert contract['baseline_only'] is True and contract['baseline_sha256'] == ready['baseline']['sha256']
assert contract['resources'] == ready['resources']
assert contract['limits'] == dict(max_detail_files=3, max_bytes_each=1048576, max_records_each=256,
    expected_records_each=149, native_pairing_each='one-to-one', truncation=False, retry=False,
    scope='direct kml_ops.gemm/_sgemm calls; not every native BLAS call inside Torch/native SDPA')
assert contract['updates'] == dict(total=5, warmup=[1, 2], detailed=[3, 4, 5], batch_size=64,
    statistics_frames=1600, training_frames=320, train_seed=0, fresh_masks=True, continuous_AdamW=True, full_torch_profiler=False)
descriptor = WORK / 'S00/overnight_engineering_20261105/ENGINEERING_DESCRIPTOR.json'
assert sha(descriptor) == contract['descriptor_sha256'] == 'b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
description, reference = load(descriptor), load(asset(ready['reference']))
assert description['corpus'] == reference['corpus'] and description['train'] == reference['units']
assert len(reference['steps']) == 5 and all(x['kml_calls'] == 149 for x in reference['steps'])
checks = load(asset(ready['checks']))
assert checks['status'] == 'PASS_LOCAL_PREPARED_FAKE_CBLAS_ONLY' and checks['new_observation_tests'] == 9
assert checks['full_encoder_runs'] == checks['new_jobs'] == 0 and checks['actual_KML_observation'] == 'NOT_RUN_BY_S02'
test_log = CODE / checks['log']
assert 'Ran 9 tests' in test_log.read_text(encoding='utf-8') and '\nOK' in test_log.read_text(encoding='utf-8')
for entry in checks['negative_cli_checks']:
    assert entry['exit'] == 2 and entry['before_framework'] is True
    if 'path' in entry:
        result = load(Path(entry['path']))
        assert result['status'] == 'DATA_NOT_READY' and 'cpu36' not in result
observer_ast = ast.parse((CODE / 'gemm_observer.py').read_text(encoding='utf-8'))
assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in
               {'clone', 'copy_', 'numpy', 'tolist', 'item', 'contiguous', 'detach', 'to'} for n in ast.walk(observer_ast))
entry_ast = ast.parse((CODE / 'train_gemm5.py').read_text(encoding='utf-8'))
assert any(isinstance(n, ast.Import) and any(x.name == 'ctypes' for x in n.names) for n in entry_ast.body)
assert 'ctypes._CFuncPtr' in (CODE / 'train_gemm5.py').read_text(encoding='utf-8')
assert 'profile_probe' not in (CODE / 'train_gemm5.py').read_text(encoding='utf-8')
result = dict(status='GEMM_CODE_REVIEW_PASS_DEPLOYMENT_PENDING', package=ready['package'], source_manifest=ready['source_manifest'],
    interface=ready['interface'], contract=ready['contract'], reference=ready['reference'], baseline=ready['baseline'], observer=ready['observer'],
    gemm_ready=dict(path=str(CODE / 'GEMM_READY.json'), sha256=sha(CODE / 'GEMM_READY.json')),
    descriptor=dict(path=str(descriptor), bytes=descriptor.stat().st_size, sha256=sha(descriptor)),
    source_files=26, zip_members=27, immutable_reused_files=17, source_review_matches_frozen=True,
    author_local_fake_cblas_receipts=9, test_log_sha256=sha(test_log), new_model_runs=0, actual_KML_runs=0,
    blocking_findings=[], remaining='Frozen S00 GEMM5 identity/resources/marker/times/cleanup/record collection review',
    scope='Original baseline scalar-only reversible observation; no R10 candidate or A/B, no Torch profiler or new dataset',
    unrun=['actual C2 ctypes/KML149 pairings', 'actual first5 loss/CPU36/library/restore and cleanup'])
(HERE / 'code_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S02_FROZEN_GEMM_READY.json').write_bytes((CODE / 'GEMM_READY.json').read_bytes())
print(json.dumps(result, indent=2))
