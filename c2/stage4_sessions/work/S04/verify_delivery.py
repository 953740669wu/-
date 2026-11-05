"""Standard-library identity/syntax check; NEVER a numerical acceptance gate."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    for name, expected in json.loads((ROOT / 'evidence/PRE_IMPLEMENTATION_FREEZE.json').read_text()).items():
        assert sha(ROOT / name) == expected, 'pre-implementation freeze changed: ' + name
    syntax = []
    for path in sorted(ROOT.rglob('*.py')):
        ast.parse(path.read_text('utf-8'), filename=str(path), feature_version=(3, 9))
        syntax.append(path.relative_to(ROOT).as_posix())
    repo = ROOT.parents[3]
    sources = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text())['source_files']
    for row in sources:
        path = repo / row['path']
        # Package-only offline review may lack the original sibling task. In the
        # workspace these sources must all exist; no silent provenance fallback.
        assert path.is_file() and sha(path) == row['sha256'], 'source changed: ' + row['path']
    for name in ('s4_models.py', 'kml_ops.py'):
        assert (ROOT / 'baseline' / name).read_bytes() == (repo /
            'c2/stage4_sessions/work/S02/round7_seq5_20261105T082315Z/baseline' / name).read_bytes()
    manifest = json.loads((ROOT / 'package/PACKAGE_MANIFEST.json').read_text())
    archive = ROOT / 'package' / manifest['name']
    assert sha(archive) == manifest['sha256'] and archive.stat().st_size == manifest['bytes']
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == sorted(manifest['files'])
        for name, identity in manifest['files'].items():
            blob = z.read(name)
            assert len(blob) == identity['bytes']
            assert hashlib.sha256(blob).hexdigest() == identity['sha256'] == sha(ROOT / name)
    numeric = json.loads((ROOT / 'evidence/block_numeric.json').read_text())
    assert numeric['status'] == 'FAIL_LOCAL_QUANTIZATION_GATE'
    assert len(numeric['metrics']) == 83 and sum(not m['passed'] for m in numeric['metrics']) == 28
    return dict(status='PASS_SYNTAX_SOURCE_PACKAGE_ONLY', syntax=syntax,
                protected_sources_unchanged=len(sources), package_files=len(manifest['files']),
                package_sha256=manifest['sha256'], package_bytes=manifest['bytes'],
                numerical_status=numeric['status'], numeric_pass=55, numeric_fail=28,
                cluster_jobs=0, full_model_runs=0, performance='NOT_RUN')


if __name__ == '__main__':
    result = verify()
    (ROOT / 'evidence/delivery_verification.json').write_text(
        json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
