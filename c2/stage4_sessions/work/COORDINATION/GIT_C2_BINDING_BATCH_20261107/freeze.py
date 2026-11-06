"""Freeze only reviewed B01/source-binding records; no Git writes or author execution."""
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
W = ROOT / 'c2/stage4_sessions/work'
C = W / 'COORDINATION'
OUT = Path(__file__).resolve().parent
BASE = '51ef5e93aed4dbefcd7f3a51640381e0f971fe3c'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def ident(p):
    b = Path(p).read_bytes()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def relative(p):
    p = Path(p)
    return (p if p.is_absolute() else ROOT / p).resolve().relative_to(ROOT).as_posix()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

assert git('rev-parse', 'HEAD').decode().strip() == BASE
assert not git('diff', '--cached', '--name-only').strip()
selected, drifts, unchanged, duplicates = {}, [], [], []
duplicate_map = {}
s00 = W / 'S00/real_dual_ddp_c2_source_binding_r1_20261106'
for name, binding in read(s00 / 'INPUT_BINDINGS.json')['verified'].items():
    copy = s00 / 'inputs' / name
    original = Path(binding['path'])
    assert ident(copy) == ident(original) == {k: binding[k] for k in ('bytes', 'sha256')}
    duplicate_map[relative(copy)] = dict(path=relative(copy), original=relative(original), **ident(copy), disposition='EXCLUDE_VERIFIED_DUPLICATE_INPUT_KEEP_LOCAL')
copy = W / 'S02/real_dual_ddp_localization_prepare_r1_20261106/SPEC_SNAPSHOT.json'
original = W / 'S01/real_dual_ddp_proposal_review_20261106/MINIMAL_EVIDENCE_SPEC.json'
assert ident(copy) == ident(original)
duplicate_map[relative(copy)] = dict(path=relative(copy), original=relative(original), **ident(copy), disposition='EXCLUDE_VERIFIED_DUPLICATE_INPUT_KEEP_LOCAL')

def add(p, expected=None):
    p = relative(p)
    f = ROOT / p
    a = ident(f)
    assert f.suffix.lower() not in {'.zip', '.pt', '.npy', '.npz', '.pyc', '.so', '.exe'} and 'known_hosts' not in p, p
    if expected and (a['sha256'] != expected['sha256'] or a['bytes'] != expected.get('bytes', a['bytes'])):
        assert f.name in ('SESSION_STATUS.md', 'ROUND_DELTA.md') and f.parent.parent == W, ('FROZEN_DRIFT', p)
        drift = dict(path=p, historical_index=expected, current=a, disposition='CURRENT_MUTABLE_STATE_FROZEN_OLD_INDEX_PRESERVED')
        if drift not in drifts:
            drifts.append(drift)
    if p in duplicate_map:
        return
    previous = subprocess.run(['git', 'cat-file', 'blob', BASE + ':' + p], cwd=ROOT, capture_output=True)
    if previous.returncode == 0 and hashlib.sha256(previous.stdout).hexdigest() == a['sha256']:
        if p not in unchanged:
            unchanged.append(p)
        return
    selected[p] = dict(scope=p.split('/')[3], path=p, **a)

indexes = [
    'S02/real_dual_ddp_localization_prepare_r1_20261106/ARCHIVE_FILES.json',
    'S01/real_dual_ddp_preparation_blocker_review_20261106/ARCHIVE_SCOPE.json',
    'S00/real_dual_ddp_c2_source_binding_r1_20261106/ARCHIVE_FILES.json',
    'S01/real_dual_ddp_c2_binding_review_r1_20261106/ARCHIVE_SCOPE.json',
]
for name in indexes:
    index = W / name
    rows = read(index)['files']
    rows = rows.items() if isinstance(rows, dict) else [(r.get('absolute_path', r['path']), r) for r in rows]
    for p, row in rows:
        add(p, row)
    add(index)
    artifact = index.parent / 'ARTIFACT_SHA256.json'
    if artifact.exists():
        add(artifact)
        rows = read(artifact)
        if isinstance(rows, list):
            for row in rows:
                add(row['path'], row)

for name in [
    'STATUS.md', 'SESSION_STATUS.md', 'ROUND_DELTA.md', 'COORDINATOR_HANDOFF_20261106.md',
    'GIT_STATIC_SPEC_37_POST_PUSH_REVIEW_20261106.json', 'S01_PREPARATION_BLOCKER_ACCEPTANCE_20261106.json',
    'REAL_DUAL_DDP_C2_SOURCE_BINDING_R1_20261106.md', 'S00_C2_SOURCE_BINDING_RECEIPT_20261106.json',
    'REAL_DUAL_DDP_C2_BINDING_REVIEW_R1_20261106.md', 'S01_C2_BINDING_ACCEPTANCE_20261107.json',
    'REAL_DUAL_DDP_LOCALIZATION_PREPARE_R2_20261107.md', 'GIT_SUBMIT_C2_BINDING_20261107.md',
    'verify_static37_blocker_review_20261106.py',
]:
    add(C / name)
for name in ['SESSION_STATUS.md', 'ROUND_DELTA.md']:
    add(W / 'GIT' / name)

dump('DUPLICATE_INPUT_DISPOSITION.json', list(duplicate_map.values()))
dump('CURRENT_STATE_INDEX_DRIFTS.json', drifts)
dump('ALREADY_ARCHIVED_UNCHANGED.json', unchanged)
old = read(C / 'GIT_STATIC_SPEC_BATCH_20261106/REMAINDER_DISPOSITION.json')
old_map = {r['path']: r for r in old}
release = []
for row in old:
    if row['disposition'] == 'DEFER_PREPARATION_BLOCKER_REVIEW':
        p = row['path']
        assert p in selected or p in duplicate_map or p in unchanged, ('MISSING_RELEASE', p)
        release.append(dict(row, disposition='RELEASED_LIMITED_ARCHIVE_NEW_BATCH' if p in selected else 'VERIFIED_DUPLICATE_OR_ALREADY_ARCHIVED', current=ident(ROOT / p)))
dump('PREPARATION_23_RELEASE.json', release)
tsv = C / 'GIT_SUBMIT_C2_BINDING_20261107.tsv'
ledger = []
pending = [x for x in git('status', '--porcelain=v1', '-z', '--untracked-files=all').decode().split('\0') if x]
for item in pending:
    p, state = item[3:], item[:2]
    if p in selected or p == relative(tsv) or p.startswith(relative(OUT) + '/'):
        continue
    if p in duplicate_map:
        row = dict(duplicate_map[p])
    elif p == relative(s00 / 'evidence/known_hosts_acquisition'):
        row = dict(path=p, disposition='EXCLUDE_LOCAL_SSH_HOST_KEY_RECORD', reason='Author explicitly excluded this local host-key record; retain locally, never add to Git')
    elif p in old_map:
        row = dict(old_map[p])
        assert row['disposition'] != 'DEFER_PREPARATION_BLOCKER_REVIEW', p
    else:
        row = dict(path=p, disposition='DEFER_NEW_UNREVIEWED', reason='Outside reviewed exact scope; retain locally, classify in a future batch')
    row['git_state'] = state
    ledger.append(row)
for row in old:
    if row['disposition'] != 'DEFER_PREPARATION_BLOCKER_REVIEW':
        assert (ROOT / row['path']).exists(), ('HISTORICAL_MISSING', row['path'])
dump('REMAINDER_DISPOSITION.json', ledger)
for f in OUT.iterdir():
    if f.is_file():
        add(f)
with tsv.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['scope', 'path', 'bytes', 'sha256'], delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(sorted(selected.values(), key=lambda r: (r['scope'], r['path'])))
for p, row in selected.items():
    assert ident(ROOT / p) == {k: row[k] for k in ('bytes', 'sha256')}
ignored = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT, input='\n'.join(selected) + '\n', text=True, capture_output=True)
assert not ignored.stdout, ignored.stdout
print(json.dumps(dict(rows=len(selected), with_tsv=len(selected)+1, bytes_including_tsv=sum(r['bytes'] for r in selected.values())+tsv.stat().st_size, scopes_without_tsv=dict(Counter(r['scope'] for r in selected.values())), tsv_sha256=ident(tsv)['sha256'], released_old_preparation=len(release), verified_duplicate_inputs=len(duplicate_map), already_archived_unchanged=len(unchanged), remainder=dict(Counter(r['disposition'] for r in ledger))), ensure_ascii=False, indent=2))
