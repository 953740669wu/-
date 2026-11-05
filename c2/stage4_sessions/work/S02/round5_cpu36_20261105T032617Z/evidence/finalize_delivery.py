"""Final read-only identity checks, then index this new S02 delivery only."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


manifest = json.loads((ROOT / 'package/PACKAGE_MANIFEST.json').read_text())
archive = ROOT / 'package' / manifest['code_archive']
assert sha(archive) == manifest['code_archive_sha256']
assert archive.stat().st_size == manifest['code_archive_bytes']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and set(z.namelist()) == set(manifest['entries'])
    for name, entry in manifest['entries'].items():
        assert sha(ROOT / name) == entry['sha256'] == hashlib.sha256(z.read(name)).hexdigest()
        assert (ROOT / name).stat().st_size == entry['bytes']
source = json.loads((ROOT / 'SOURCE_SHA256.json').read_text())
assert all(sha(ROOT / name) == value for name, value in source.items())
for path in ROOT.rglob('*.py'):
    ast.parse(path.read_text('utf-8'), feature_version=(3, 9))
originals = json.loads((ROOT / 'evidence/inputs_before.json').read_text())
protected = {name: entry for name, entry in originals.items() if not name.endswith('COORDINATION\\STATUS.md')}
for name, entry in protected.items():
    path = Path(name)
    assert dict(sha256=sha(path), bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns) == entry, name
tests = (ROOT / 'evidence/guard_tests_after.txt').read_text('utf-8')
assert 'Ran 14 tests' in tests and tests.rstrip().endswith('OK')
assert json.loads((ROOT / 'evidence/local_validation.json').read_text())['status'] == 'PASS_LOCAL_WRAPPER_ONLY'
assert json.loads((ROOT / 'evidence/commands_validation.json').read_text())['shell_exit'] == 0
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
record = dict(status='READY_FOR_COORDINATION_REVIEW_S00_EXECUTION',
    archive_sha256=sha(archive), archive_bytes=archive.stat().st_size, archive_entries=len(manifest['entries']),
    protected_prior_files_unchanged=len(protected), local_guard_tests=14,
    source_manifest_matches=True, archive_matches_current_sources=True, python39_syntax=True,
    shared_status_externally_updated=True, framework_imported=False, model_runs=0,
    cluster_jobs=0, c2_numerical='NOT_RUN', windows_numerical='PREVIOUS_FAIL_194_PRESERVED',
    training_memory='NOT_RUN', hbm='NOT_RUN', substantive_local_code_blockers=[])
(ROOT / 'evidence/final_review.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
files = sorted(path for path in ROOT.rglob('*') if path.is_file() and path.name != 'ARTIFACT_SHA256.txt')
(ROOT / 'ARTIFACT_SHA256.txt').write_text(''.join(sha(path) + '  ' + path.relative_to(ROOT).as_posix() + '\n'
                                               for path in files), encoding='utf-8', newline='\n')
print(json.dumps(dict(record, indexed_files=len(files), report=str((ROOT / 'REPORT.md').resolve()),
                     archive=str(archive.resolve())), indent=2))
