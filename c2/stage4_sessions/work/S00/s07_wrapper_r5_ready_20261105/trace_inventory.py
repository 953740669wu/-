"""Describe archived diagnostic completeness without changing communication verdicts."""
import hashlib
import json
from pathlib import Path

CASES = ['normal', 'crash', 'collective-timeout', 'watchdog']


def read_events(path, expected_pid, issues):
    if not path.is_file():
        issues.append(path.name + ': missing stream'); return [], {}
    raw = path.read_bytes()
    info = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), mtime_ns=path.stat().st_mtime_ns)
    rows, pending = [], set()
    if not raw or not raw.endswith(b'\n'): issues.append(path.name + ': empty or truncated final line')
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line.decode('utf-8'))
            if (not isinstance(row['event'], str) or row['pid'] != expected_pid
                    or any(type(row[k]) is not int or row[k] <= 0 for k in ('time_ns', 'monotonic_ns', 'pid'))):
                raise ValueError('invalid event/PID/clock')
            if rows and row['monotonic_ns'] < rows[-1]['monotonic_ns']:
                raise ValueError('monotonic clock moved backwards')
            event = row['event']
            if event.endswith(('_begin', '_end')) and event not in ('supervisor_begin', 'supervisor_end', 'cleanup_begin', 'spawn_begin'):
                key = (event.rsplit('_', 1)[0], row.get('stage'), row.get('library'))
                if event.endswith('_begin'):
                    if key in pending: issues.append(path.name + ': duplicate begin')
                    pending.add(key)
                elif key not in pending: issues.append(path.name + ': end without begin')
                else: pending.remove(key)
            rows.append(row)
        except (UnicodeError, ValueError, KeyError, TypeError) as exc:
            issues.append(path.name + ': invalid line ' + str(number) + ': ' + str(exc))
    if pending: issues.append(path.name + ': unclosed intervals ' + repr(sorted(pending)))
    info.update(valid_rows=len(rows), open_intervals=[list(x) for x in pending])
    return rows, info


def inspect(root):
    root = Path(root); checks = root / 'payload/checks_current_job'
    result = dict(status='NOT_RUN', complete=False, cases={}, not_run=[], issues=[],
                  scope='trace completeness only; I/O included; no root-cause or communication verdict')
    for case in CASES:
        directory = checks / case
        if not directory.is_dir(): result['not_run'].append(case); continue
        issues, files = [], {}
        try:
            manifest = json.loads((directory / 'manifest.json').read_bytes())
            state = json.loads((directory / 'summary.json').read_bytes())['supervisor']
            parent_path = directory / 'supervisor.events.jsonl'
            parent_first = json.loads(parent_path.read_bytes().splitlines()[0])
            parent, files[parent_path.name] = read_events(parent_path, parent_first['pid'], issues)
            if not parent or parent[0]['event'] != 'supervisor_begin' or parent[-1]['event'] != 'supervisor_end':
                issues.append('missing supervisor boundary rows')
            if ([x['child_pid'] for x in parent if x['event'] == 'spawned'] != state['pids']
                    or [x['child_pid'] for x in parent if x['event'] == 'child_reaped'] != state['pids']
                    or not any(x['event'] == 'cleanup_begin' for x in parent) or not state['all_reaped']):
                issues.append('missing spawn/cleanup/reap rows')
            if len(state['pids']) != 2: issues.append('missing worker PID identity')
            for rank in range(2):
                path = directory / ('rank' + str(rank) + '.events.jsonl')
                rows, files[path.name] = read_events(path, state['pids'][rank], issues)
                if not rows or any(rows[0].get(k) != v for k, v in dict(event='worker_ready', rank=rank,
                        job_id=manifest['job_id'], run_id=manifest['run_id']).items()):
                    issues.append(path.name + ': missing/wrong worker identity row')
        except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError) as exc:
            issues.append('missing or malformed case/parent evidence: ' + repr(exc))
        for p in directory.glob('rank*.log'):
            if b'TRACE_WRITE_ERROR' in p.read_bytes(): issues.append(p.name + ': TRACE_WRITE_ERROR')
        result['cases'][case] = dict(complete=not issues, files=files, issues=issues)
        result['issues'].extend(case + ': ' + item for item in issues)
    for p in (root / 'job.log', root / 'job_evidence/run_checks.txt'):
        if p.is_file() and b'TRACE_WRITE_ERROR' in p.read_bytes(): result['issues'].append(str(p.relative_to(root)) + ': TRACE_WRITE_ERROR')
    if result['cases']:
        result['complete'] = not result['issues']
        result['status'] = 'COMPLETE_AVAILABLE_TRACES_ONLY' if result['complete'] else 'DIAGNOSTIC_EVIDENCE_INCOMPLETE'
    return result
