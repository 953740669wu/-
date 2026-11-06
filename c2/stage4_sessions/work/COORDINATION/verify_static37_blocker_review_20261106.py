"""Read-only Git objects and local delivery binding verification; no author execution."""
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
C = ROOT / 'c2/stage4_sessions/work/COORDINATION'
W = C.parent

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def digest(b):
    return hashlib.sha256(b).hexdigest()

manifest = C / 'GIT_SUBMIT_STATIC_SPEC_20261106.tsv'
assert digest(manifest.read_bytes()) == 'b9575ab91491a4c12b341c034538f7bffc2faa01a072e4923628ba52bc9c81e9'
rows = list(csv.DictReader(manifest.read_text(encoding='utf-8-sig').splitlines(), delimiter='\t'))
rows.append(dict(scope='COORDINATION', path=manifest.relative_to(ROOT).as_posix(), bytes=manifest.stat().st_size, sha256=digest(manifest.read_bytes())))
base = '05ded1bfd2b9339dcb5cd0c6708ec0b29dfa44a5'
head = '51ef5e93aed4dbefcd7f3a51640381e0f971fe3c'
assert git('rev-parse', 'HEAD').decode().strip() == head
assert git('rev-parse', 'origin/main').decode().strip() == head
assert not git('diff', '--cached', '--name-only').strip()
changed = set(git('diff', '--name-only', base, head).decode().splitlines())
assert changed == {r['path'] for r in rows}
for r in rows:
    b = git('cat-file', 'blob', head + ':' + r['path'])
    assert len(b) == int(r['bytes']) and digest(b) == r['sha256'], r['path']
commits = dict(S02='933bed8cc90438e9052630cc2592b3e0ead3b474', S01='bceec9f72109df41d9b9a2eb257df63e87992c38', COORDINATION='59589ac0fcb2300029d1d085f76c9735cf60f229', GIT=head)
for scope, commit in commits.items():
    actual = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', commit).decode().splitlines())
    assert actual == {r['path'] for r in rows if r['scope'] == scope}, scope
git_result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), base=base, head=head, files=len(rows), bytes=sum(int(r['bytes']) for r in rows), exact_scope=True, object_bytes_sha_verified=True, commits=commits, remote_main=head, remote_evidence='Coordinator separate successful git ls-remote origin refs/heads/main this round; network-required command not repeated by this script.', staged_files=0)
(C / 'GIT_STATIC_SPEC_37_POST_PUSH_REVIEW_20261106.json').write_text(json.dumps(git_result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

bindings = {}
def walk(x):
    if isinstance(x, dict):
        p = x.get('path')
        if isinstance(p, str) and len(p) > 2 and p[1] == ':' and 'sha256' in x and 'bytes' in x:
            bindings[p] = x
        for key, value in x.items():
            if isinstance(key, str) and len(key) > 2 and key[1] == ':' and isinstance(value, dict) and 'sha256' in value and 'bytes' in value:
                bindings[key] = dict(value, path=key)
            walk(value)
    elif isinstance(x, list):
        for value in x:
            walk(value)

s01 = W / 'S01/real_dual_ddp_preparation_blocker_review_20261106'
s02 = W / 'S02/real_dual_ddp_localization_prepare_r1_20261106'
inputs = [s01 / name for name in ('ARCHIVE_SCOPE.json', 'BLOCKER_REVIEW.json', 'BLOCKER_AUDIT.json', 'MISSING_BINDING_SPEC.json')]
inputs += [s02 / name for name in ('ARCHIVE_FILES.json', 'PREPARATION_BLOCKED.json', 'SOURCE_SHA256.json', 'evidence/SOURCE_INPUTS.json')]
for p in inputs:
    walk(json.loads(p.read_text(encoding='utf-8-sig')))
    bindings[str(p)] = dict(path=str(p), bytes=p.stat().st_size, sha256=digest(p.read_bytes()))
verified = []
for p, row in bindings.items():
    b = Path(p).read_bytes()
    assert len(b) == int(row['bytes']) and digest(b) == row['sha256'], p
    verified.append(dict(path=p, bytes=len(b), sha256=digest(b)))
result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), decision='ACCEPT_BLOCKED_WITH_PRESERVED_LIMITATIONS', verified_local_bindings=len(verified), files=verified, original_spec_and_FAIL_preserved=True, author_tests_rerun=False, numerical_validation=False, preparation_ready=False, archive_disposition='S02 blocked preparation and S01 blocker review accepted for a future exact batch; ZIP/raw exclusions remain; no staging/commit/push by coordinator', next='S00 source-only target binding packet; S02 stays blocked pending packet and review')
(C / 'S01_PREPARATION_BLOCKER_ACCEPTANCE_20261106.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(git_files=len(rows), git_bytes=git_result['bytes'], verified_local_bindings=len(verified), decision=result['decision'])))
