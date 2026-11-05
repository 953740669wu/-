"""Verify R1 preservation and diagnostic evidence; not numerical acceptance."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
R1 = ROOT.parent
REPO = R1.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text('utf-8'))


def verify():
    protected = read('evidence/R1_PROTECTED_SHA256.json')
    for name, value in protected.items():
        assert sha(R1 / name) == value, name
    for name, value in read('evidence/PRE_IMPLEMENTATION_FREEZE.json').items():
        assert sha(ROOT / name) == value, name
    sources = read('SOURCE_MANIFEST.json')['source_files']
    for row in sources:
        assert sha(REPO / row['path']) == row['sha256'], row['path']
    for name in ('baseline/s4_models.py', 'baseline/kml_ops.py', 'tests/common.py',
                 'tests/test_contract.py', 'tests/test_attention_boundary.py'):
        assert (ROOT / name).read_bytes() == (R1 / name).read_bytes(), name
    syntax = []
    for path in sorted(ROOT.rglob('*.py')):
        ast.parse(path.read_text('utf-8'), filename=str(path), feature_version=(3, 9))
        syntax.append(path.relative_to(ROOT).as_posix())
    fp, bf = read('evidence/fp32_control.json'), read('evidence/bf16_replay.json')
    assert fp['checks'] == bf['checks'] == 83 and fp['failed'] == 7 and bf['failed'] == 28
    old = json.loads((R1 / 'evidence/block_numeric.json').read_text())
    assert bf['metrics'] == [dict(row, same_dtype=True) for row in old['metrics']]
    for row in fp['metrics']:
        assert row['max_abs_limit'] == (2e-6 if row['name'].startswith(('exp_avg.', 'exp_avg_sq.')) else 2e-5)
        assert row['limit'] == 2e-6
        if not row['passed']:
            assert row['name'].startswith(('parameter.', 'update.'))
    for row in read('evidence/local_vjp.json'):
        assert row['reference_reconstruction']['max_abs'] == row['bf16_reconstruction']['max_abs'] == 0
        assert row['gate_only_error']['l2_relative'] > 0.02
    cf = read('evidence/gate_restored_counterfactual.json')
    original_failures = {r['name'] for r in bf['metrics'] if not r['passed']}
    cf_failures = {r['name'] for r in cf['metrics'] if not r['passed']}
    assert cf['forward_unchanged'] and cf['failed'] == 14 and cf_failures < original_failures
    assert read('evidence/relu_gate_changes.json')['changed'] == 63
    assert read('evidence/adamw_replay.json')['exact_parameter_delta_moment_tensors'] == 256
    key = read('evidence/key_bias_rounding.json')
    assert key['bf16_cast_exactly_reproduces_saved_qkv_gradient']
    assert key['rounded_sum_exactly_reproduces_actual_bias_gradient']
    assert key['before_quantization_key_bias_norm'] < 1e-8 < key['after_quantization_key_bias_norm']
    pack = read('package/PACKAGE_MANIFEST.json')
    archive = ROOT / 'package' / pack['name']
    assert sha(archive) == pack['sha256'] and archive.stat().st_size == pack['bytes']
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == sorted(pack['files'])
        for name, info in pack['files'].items():
            blob = z.read(name)
            assert len(blob) == info['bytes']
            assert hashlib.sha256(blob).hexdigest() == info['sha256'] == sha(ROOT / name)
    return dict(status='PASS_IDENTITY_EVIDENCE_RELATIONS_ONLY', round='S04_R2',
                numerical_status='FAIL', fp32_fail=7, bf16_fail=28, counterfactual_fail=14,
                R1_protected_files=len(protected), source_files=len(sources), syntax=syntax,
                package_files=len(pack['files']), package_sha256=pack['sha256'], package_bytes=pack['bytes'],
                cluster_jobs=0, performance='NOT_RUN', full_model_runs=0)


if __name__ == '__main__':
    result = verify()
    (ROOT / 'evidence/delivery_verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
