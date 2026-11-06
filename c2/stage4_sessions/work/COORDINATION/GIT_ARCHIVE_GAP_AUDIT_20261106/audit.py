"""Read-only Git/archive inventory. Writes only this audit directory."""
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
COORD = ROOT / 'c2/stage4_sessions/work/COORDINATION'


def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


def relative(value, index=None):
    value = str(value).replace('\\', '/')
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return None
    if value.startswith('c2/'):
        return path.as_posix()
    if value.startswith('work/'):
        return 'c2/stage4_sessions/' + value
    if index is not None:
        try:
            return (index.parent / value).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return None
    return None


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


started = datetime.now().astimezone().isoformat()
head = git('rev-parse', 'HEAD').decode().strip()
origin = git('rev-parse', 'origin/main').decode().strip()
manifests = {}
for index in sorted(COORD.glob('GIT_SUBMIT*.tsv')):
    manifests[index.name] = list(csv.DictReader(io.StringIO(index.read_text('utf-8-sig')), delimiter='\t'))
needed = {row['path'] for rows in manifests.values() for row in rows}
latest_name = 'GIT_SUBMIT_R9_R12_S07R7_20261106.tsv'
latest_self = (COORD / latest_name).relative_to(ROOT).as_posix()
needed.add(latest_self)

head_objects = {}
for item in git('ls-tree', '-rz', head).split(b'\0'):
    if item:
        meta, path = item.split(b'\t', 1)
        head_objects[path.decode('utf-8')] = meta.split()[2].decode()

# Track historical blobs at their actual paths; a newer status is not a missing old submission.
history = collections.defaultdict(set)
all_paths_by_oid = collections.defaultdict(set)
tokens = git('log', '--all', '--raw', '--no-renames', '--no-abbrev', '--format=', '-z',
             '--', 'c2/stage4_sessions').split(b'\0')
position = 0
while position < len(tokens):
    entry = tokens[position].lstrip(b'\n')
    if entry.startswith(b':') and position + 1 < len(tokens):
        fields = entry.split()
        path = tokens[position + 1].decode('utf-8')
        for oid in fields[2:4]:
            if oid.strip(b'0'):
                all_paths_by_oid[oid.decode()].add(path)
        if path in needed:
            for oid in fields[2:4]:
                if oid.strip(b'0'):
                    history[path].add(oid.decode())
        position += 2
    else:
        position += 1
oids = {oid for path in needed for oid in history[path]}
oids.update(head_objects[path] for path in needed if path in head_objects)
batch = git('cat-file', '--batch', data=('\n'.join(sorted(oids)) + '\n').encode())
blob_identity = {}
cursor = 0
for requested in sorted(oids):
    end = batch.index(b'\n', cursor)
    oid, kind, size = batch[cursor:end].split()
    size = int(size)
    payload = batch[end + 1:end + 1 + size]
    if oid.decode() != requested or kind != b'blob':
        raise ValueError('Unexpected Git object identity/type')
    blob_identity[requested] = (size, hashlib.sha256(payload).hexdigest())
    cursor = end + size + 2

manifest_results = {}
for name, rows in manifests.items():
    results = []
    for row in rows:
        path = row['path']
        expected = (int(row['bytes']), row['sha256'].lower())
        current = blob_identity.get(head_objects.get(path))
        historic = any(blob_identity[oid] == expected for oid in history[path])
        state = 'HEAD_EXACT' if current == expected else 'HISTORICAL_EXACT' if historic else 'NOT_FOUND_IN_LOCAL_HISTORY'
        results.append(dict(path=path, state=state, expected_bytes=expected[0], expected_sha256=expected[1]))
    manifest_results[name] = dict(counts=dict(collections.Counter(x['state'] for x in results)), files=results)
latest_self_ok = blob_identity.get(head_objects.get(latest_self)) == ((ROOT / latest_self).stat().st_size, digest(ROOT / latest_self))
exceptions = [dict(manifest=name, **item) for name, value in manifest_results.items()
              for item in value['files'] if item['state'] == 'NOT_FOUND_IN_LOCAL_HISTORY']
expected_sizes = {item['expected_bytes'] for item in exceptions}
other_oids = sorted(set(all_paths_by_oid) - set(blob_identity))
checks = git('cat-file', '--batch-check', data=('\n'.join(other_oids) + '\n').encode()).splitlines() if other_oids else []
candidate_oids = [line.split()[0].decode() for line in checks
                  if len(line.split()) == 3 and line.split()[1] == b'blob' and int(line.split()[2]) in expected_sizes]
other_matches = collections.defaultdict(list)
if candidate_oids:
    candidate_data = git('cat-file', '--batch', data=('\n'.join(candidate_oids) + '\n').encode())
    offset = 0
    for oid in candidate_oids:
        end = candidate_data.index(b'\n', offset)
        size = int(candidate_data[offset:end].split()[2])
        sha = hashlib.sha256(candidate_data[end + 1:end + 1 + size]).hexdigest()
        other_matches[sha].extend(sorted(all_paths_by_oid[oid]))
        offset = end + size + 2
for oid, (size, sha) in blob_identity.items():
    if size in expected_sizes:
        other_matches[sha].extend(sorted(all_paths_by_oid[oid]))
for item in exceptions:
    item['exact_archived_at_other_paths'] = sorted(set(other_matches[item['expected_sha256']]))

status_raw = git('status', '--porcelain=v1', '-z', '--untracked-files=all')
status_tokens = status_raw.split(b'\0')
changes = {}
position = 0
while position < len(status_tokens):
    item = status_tokens[position]
    position += 1
    if not item:
        continue
    state, path = item[:2].decode(), item[3:].decode('utf-8')
    changes[path] = state
    if 'R' in state or 'C' in state:
        position += 1
visible = {p.decode('utf-8') for p in git('ls-files', '-c', '-o', '--exclude-standard', '-z').split(b'\0') if p}
working_matches = collections.defaultdict(list)
for path in visible:
    source = ROOT / path
    if source.is_file() and source.stat().st_size in expected_sizes:
        working_matches[digest(source)].append(path)
for item in exceptions:
    item['exact_working_copies'] = sorted(working_matches[item['expected_sha256']])
archive_indices = [ROOT / p for p in visible if Path(p).name in {'ARCHIVE_FILES.json', 'ARCHIVE_SCOPE.json', 'ARCHIVE_FILES.txt'}]
memberships = collections.defaultdict(list)
archive_issues = []
for index in sorted(archive_indices):
    members = []
    try:
        if index.suffix == '.txt':
            members = [(line.strip(), {}) for line in index.read_text('utf-8-sig').splitlines()
                       if line.strip() and not line.startswith('#')]
        else:
            value = json.loads(index.read_text('utf-8-sig'))
            if isinstance(value, list):
                members = [(x if isinstance(x, str) else x['path'], {} if isinstance(x, str) else x) for x in value]
            else:
                for key in ('git_candidate_paths', 'files'):
                    items = value.get(key, [])
                    if isinstance(items, dict):
                        members.extend((p, meta if isinstance(meta, dict) else {}) for p, meta in items.items())
                    elif isinstance(items, list):
                        members.extend((x if isinstance(x, str) else x['path'], {} if isinstance(x, str) else x) for x in items)
        for value, meta in members:
            path = relative(value, index)
            if not path:
                archive_issues.append(dict(index=str(index.relative_to(ROOT)), path=str(value), reason='OUTSIDE_WORKSPACE'))
                continue
            memberships[path].append(index.relative_to(ROOT).as_posix())
            source = ROOT / path
            if not source.is_file():
                archive_issues.append(dict(index=str(index.relative_to(ROOT)), path=path, reason='LISTED_FILE_MISSING'))
            elif meta.get('sha256') and digest(source) != meta['sha256'].lower():
                archive_issues.append(dict(index=str(index.relative_to(ROOT)), path=path, reason='CURRENT_DIFFERS_FROM_INDEX_SNAPSHOT',
                                           mutable_status=source.name in {'SESSION_STATUS.md', 'ROUND_DELTA.md', 'STATUS.md'}))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        archive_issues.append(dict(index=str(index.relative_to(ROOT)), reason='INDEX_PARSE_ERROR', error=str(exc)))

old_path = Path('E:/Codex/home/visualizations/2026/11/05/01a1a9d7-f74b-7e30-b951-571b11c51ea1/r9_r12_s07r7_20261106/remaining_files.json')
old_remaining = {x['path'] for x in json.loads(old_path.read_text('utf-8-sig'))}
inventory = []
for path, state in sorted(changes.items()):
    if path.startswith(OUT.relative_to(ROOT).as_posix() + '/'):
        continue
    parts = path.split('/')
    group = '/'.join(parts[:5]) if path.startswith('c2/stage4_sessions/work/') else '/'.join(parts[:2])
    source = ROOT / path
    inventory.append(dict(path=path, git_state=state, group=group,
                          prior_remaining=path in old_remaining, archive_indices=memberships[path],
                          bytes=source.stat().st_size if source.is_file() else None))
groups = collections.defaultdict(list)
for item in inventory:
    groups[item['group']].append(item)
group_counts = [dict(group=group, files=len(items), previously_pending=sum(x['prior_remaining'] for x in items),
                     author_indexed=sum(bool(x['archive_indices']) for x in items)) for group, items in sorted(groups.items())]
changed_indices = [p for p in changes if Path(p).name in {'ARCHIVE_FILES.json', 'ARCHIVE_SCOPE.json', 'ARCHIVE_FILES.txt'}]
summary = dict(snapshot_started=started, snapshot_finished=datetime.now().astimezone().isoformat(),
               head=head, origin_tracking=origin, remote_live_checked=False,
               index_changed_by_audit=False, staged_diff_empty=not bool(git('diff', '--cached', '--name-only').strip()),
               latest_manifest=latest_name, latest_manifest_counts=manifest_results[latest_name]['counts'],
               latest_manifest_self_exact=latest_self_ok,
               historical_manifest_counts={k: v['counts'] for k, v in manifest_results.items()},
               historical_exception_rows=len(exceptions),
               historical_exceptions_found_other_archive_paths=sum(bool(x['exact_archived_at_other_paths']) for x in exceptions),
               historical_exceptions_found_working_copies=sum(bool(x['exact_working_copies']) for x in exceptions),
               current_pending_files=len(inventory), prior_remaining_files=len(old_remaining),
               still_pending_from_prior=sum(x['prior_remaining'] for x in inventory),
               added_pending_since_prior=sum(not x['prior_remaining'] for x in inventory),
               author_indexed_pending=sum(bool(x['archive_indices']) for x in inventory),
               archive_index_count=len(archive_indices), archive_issue_count=len(archive_issues),
               changed_archive_indices=changed_indices,
               notes=['Author archive indices are proposed scopes, not coordinator acceptance.',
                      'This audit directory is excluded from the pending-file counts.',
                      'Mutable status hashes may legitimately differ after later rounds.',
                      'Ignored data, weights, environments and packages are excluded from the pending-file inventory.',
                      'Concurrent author edits can change this snapshot; never use it as an approved submission manifest.'])
write('SUMMARY.json', summary)
write('MANIFEST_VERIFICATION.json', manifest_results)
write('HISTORICAL_EXCEPTIONS.json', exceptions)
write('PENDING_FILES.json', inventory)
write('PENDING_GROUPS.json', group_counts)
write('ARCHIVE_INDEX_ISSUES.json', archive_issues)
print(json.dumps(summary, ensure_ascii=False, indent=2))
