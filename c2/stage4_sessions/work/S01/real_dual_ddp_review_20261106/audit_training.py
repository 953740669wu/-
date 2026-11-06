"""Read-only verification of S07 frozen delivery and disclosed failed gate."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

OWN = Path(__file__).resolve().parent
WORK = OWN.parent.parent
SRC = WORK / 'S07/real_dual_ddp_20261106'
REF = WORK / 'S02/real_dual_ddp_reference_20261106'


def asset(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    inputs = {}

    def verify(value, root=None):
        if isinstance(value, dict):
            if {'path', 'sha256'} <= value.keys():
                path = Path(value['path'])
                if not path.is_absolute():
                    assert root is not None
                    path = root / path
                actual = asset(path)
                assert actual['sha256'] == value['sha256'], str(path)
                if 'bytes' in value:
                    assert actual['bytes'] == value['bytes'], str(path)
                inputs[actual['path']] = actual
            for item in value.values():
                verify(item, root)
        elif isinstance(value, list):
            for item in value:
                verify(item, root)

    ready = json.loads((SRC / 'TRAINING_READY.json').read_text(encoding='utf-8'))
    inputs[str(SRC / 'TRAINING_READY.json')] = asset(SRC / 'TRAINING_READY.json')
    verify(ready)
    source = json.loads((SRC / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    verify(source, SRC)
    delivery = {row['path'] for row in source['delivery_files']}
    assert len(delivery) == 19
    with zipfile.ZipFile(ready['package']['path']) as package:
        names = package.namelist()
        assert len(names) == len(set(names)) == 21 and package.testzip() is None
        assert set(names) == delivery | {'SOURCE_MANIFEST.json', 'evidence/'}
        for name in names:
            posix = PurePosixPath(name)
            assert not posix.is_absolute() and '..' not in posix.parts and ':' not in name and '\\' not in name
            if name.endswith('/'):
                continue
            assert package.read(name) == (SRC / name).read_bytes()
            if name.endswith('.py'):
                assert b'\r' not in package.read(name)
                ast.parse(package.read(name).decode('utf-8'), feature_version=(3, 9))
    evidence = json.loads((SRC / 'EVIDENCE_MANIFEST.json').read_text(encoding='utf-8'))
    verify(evidence, SRC)
    binding = json.loads((SRC / 'reference_binding.json').read_text(encoding='utf-8'))
    verify(binding, REF)
    assert len(binding['files']) == 18
    assert binding['ready_sha256'] == asset(REF / 'REFERENCE_READY.json')['sha256']
    config = json.loads((SRC / 'training_config.json').read_text(encoding='utf-8'))
    assert config == ready['training_configuration'] == source['training']
    assert (config['world_size'], config['per_rank_batch'], config['global_batch'],
            config['total_updates'], config['reference_updates']) == (2, 32, 64, 25, 5)
    assert (config['job_seconds'], config['application_seconds'], config['cleanup_seconds'],
            config['collection_seconds'], config['pg_timeout_seconds']) == (900, 840, 30, 30, 120)
    components = json.loads((SRC / 'evidence/R7_COMPONENTS.json').read_text(encoding='utf-8'))
    original = Path(components['source'])
    assert asset(original)['sha256'] == components['source_sha256']
    texts = [(original, original.read_text(encoding='utf-8')),
             (SRC / 'candidate/runtime_guard.py', (SRC / 'candidate/runtime_guard.py').read_text(encoding='utf-8'))]
    for item in components['functions']:
        for path, text in texts:
            node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == item['function'])
            raw = ''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno]).encode()
            assert hashlib.sha256(raw).hexdigest() == item['sha256'], (str(path), item['function'])
    checks = json.loads((SRC / 'evidence/LOCAL_CHECKS.json').read_text(encoding='utf-8'))
    assert (checks['total_methods'], checks['passed'], checks['failed'], checks['skipped']) == (19, 17, 1, 1)
    metric_path = SRC / 'evidence/tiny_ddp_192181562000000/strict_pair_metrics.json'
    metrics = json.loads(metric_path.read_text(encoding='utf-8'))
    assert len(metrics) == 13
    for row in metrics:
        expected = row['max_abs'] <= 2e-5 and (row['reference_norm'] <= 1e-8 or row['l2_relative'] <= 2e-6)
        assert row['passed'] == expected
    failed = [row for row in metrics if not row['passed']]
    assert failed == ready['strict_pair_failed_metrics'] == checks['strict_pair_failed_metrics']
    assert [row['name'] for row in failed] == ['val.weight', 'pos.weight', 'tf.weight']
    assert ready['all_local_checks_passed'] is False and ready['training_acceptance'] is False
    result = dict(status='FAIL_CURRENT_CANDIDATE_LOCAL_STRICT_NUMERICAL_GATE',
                  package_members=21, package_files=20, delivery_files=19,
                  reference_bound_files=18, reused_r7_functions=7,
                  evidence_files=len(evidence['files']),
                  local_tests=dict(total=19, passed=17, failed=1, skipped=1),
                  strict_metrics=dict(total=13, failed=failed, evidence=asset(metric_path)),
                  original_thresholds_preserved=True, author_tests_repeated=0,
                  C2_numerical_result='NOT_RUN_NOT_INFERRED_FROM_WINDOWS',
                  inputs=sorted(inputs.values(), key=lambda row: row['path']))
    (OWN / 'training_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'inputs'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
