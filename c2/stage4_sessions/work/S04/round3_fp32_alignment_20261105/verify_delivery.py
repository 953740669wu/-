"""Source/package and evidence audit; never executes or accepts a new model."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
S04 = ROOT.parent
REPO = S04.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text('utf-8'))


def verify():
    protected = read('evidence/R1_R2_PROTECTED_SHA256.json')
    for name, expected in protected.items():
        assert sha(S04 / name) == expected, name
    for name, expected in read('evidence/PRE_IMPLEMENTATION_FREEZE.json').items():
        assert sha(ROOT / name) == expected, name
    for row in read('SOURCE_MANIFEST.json')['source_files']:
        assert sha(REPO / row['path']) == row['sha256'], row['path']
    for row in read('evidence/torch_source_identity.json')['functions']:
        assert sha(Path(row['path'])) == row['file_sha256'], row['name']
    for row in read('evidence/library_identity.json')['files']:
        assert sha(Path(row['path'])) == row['sha256']
    for name in ('baseline/s4_models.py', 'baseline/kml_ops.py', 'tests/common.py'):
        assert (ROOT / name).read_bytes() == (S04 / name).read_bytes()
    assert all(read('evidence/unchanged_components.json').values())
    syntax = []
    for path in sorted(ROOT.rglob('*.py')):
        ast.parse(path.read_text('utf-8'), filename=str(path), feature_version=(3, 9))
        syntax.append(path.relative_to(ROOT).as_posix())
    control, bf = read('evidence/fp32_aligned.json'), read('evidence/bf16_unchanged.json')
    assert control['checks'] == len(control['metrics']) == bf['checks'] == 83
    assert control['failed'] == 0 and bf['failed'] == 28
    for row in control['metrics']:
        assert row['passed'] and row['same_dtype'] and row['max_abs'] == row['l2_relative'] == 0
        assert row['limit'] == 2e-6
        assert row['max_abs_limit'] == (2e-6 if row['name'].startswith(('exp_avg.', 'exp_avg_sq.')) else 2e-5)
    old = json.loads((S04 / 'evidence/block_numeric.json').read_text())
    assert bf['metrics'] == [dict(row, same_dtype=True) for row in old['metrics']]
    change = read('evidence/failure_transitions.json')
    assert len(change['original_seven']) == 7 and not change['newly_failed']
    assert all(t['current']['passed'] for t in change['original_seven'])
    assert len(change['all_83_statuses']) == 83
    summary = read('evidence/summary.json')
    assert summary['alignment_attempts'] == 1 and summary['all_83_bitwise_equal']
    assert summary['whole_reference_block_and_MHA_forbidden']
    package = read('package/PACKAGE_MANIFEST.json')
    path = ROOT / 'package' / package['name']
    assert sha(path) == package['sha256'] and path.stat().st_size == package['bytes']
    with zipfile.ZipFile(path) as z:
        assert sorted(z.namelist()) == sorted(package['files'])
        for name, info in package['files'].items():
            blob = z.read(name)
            assert hashlib.sha256(blob).hexdigest() == info['sha256'] == sha(ROOT / name)
            assert len(blob) == info['bytes']
    return dict(status='PASS_SOURCE_PACKAGE_EVIDENCE_AUDIT_ONLY', round='S04_R3',
                protected_prior_files=len(protected), fp32_checks=83, fp32_fail=0, old_seven_resolved=7,
                new_failures=0, bf16_fail=28, alignment_attempts=1, proposals=1, proposal_implemented=False,
                syntax=syntax, package_files=len(package['files']), package_sha256=package['sha256'],
                package_bytes=package['bytes'], cluster_jobs=0, performance='NOT_RUN', full_model_runs=0)


if __name__ == '__main__':
    result = verify()
    (ROOT / 'evidence/delivery_verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
