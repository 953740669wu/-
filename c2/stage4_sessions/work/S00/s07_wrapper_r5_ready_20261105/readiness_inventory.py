"""Read-only terminal readiness consistency; never create or repair protocol files."""
import hashlib
import json
from pathlib import Path

from trace_inventory import CASES


def events(path, issues):
    try:
        raw = path.read_bytes()
        if not raw.endswith(b'\n'): issues.append(path.name + ': truncated event tail')
        rows = [json.loads(line) for line in raw.splitlines()]
        clocks = [row['monotonic_ns'] for row in rows]
        if any(type(t) is not int for t in clocks) or clocks != sorted(clocks):
            raise ValueError('invalid event clock order')
        return rows
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        issues.append(path.name + ': incomplete event evidence: ' + str(exc)); return []


def inspect(root):
    root = Path(root)
    result = dict(status='NOT_RUN', complete=False, cases={}, not_run=[], issues=[],
        scope='archived readiness consistency only; no communication verdict or cross-rank publication-time inference')
    for name in CASES:
        directory = root / 'payload/checks_current_job' / name
        if not directory.is_dir(): result['not_run'].append(name); continue
        issues, files, values = [], {}, {}
        verified_context = None
        temporary = sorted(p.name for p in directory.glob('*.tmp*') if p.is_file())
        for filename in ['participants.json', 'ready_rank0.json', 'ready_rank1.json'] + temporary:
            path = directory / filename
            if not path.is_file(): issues.append(filename + ': missing'); continue
            raw = path.read_bytes()
            files[filename] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), mtime_ns=path.stat().st_mtime_ns)
            try: values[filename] = json.loads(raw)
            except (UnicodeError, ValueError):
                files[filename]['parse_error'] = True; issues.append(filename + ': invalid JSON retained')
        if temporary: issues.append('publication temporary residuals retained')
        try:
            manifest = json.loads((directory / 'manifest.json').read_bytes())
            summary = json.loads((directory / 'summary.json').read_bytes())
            identity = {k:manifest[k] for k in ('run_id', 'job_id', 'ready_token')}
            if any(type(v) is not str or not v.strip() for v in identity.values()):
                raise ValueError('missing manifest identity/token')
            if identity['job_id'] != (root / 'job_id.txt').read_text().strip():
                raise ValueError('manifest job differs from collected scheduler job')
            parent = events(directory / 'supervisor.events.jsonl', issues)
            context = values['participants.json']
            pids, stop = context['pids'], context['deadline_ns']
            if (type(pids) is not list or len(pids) != 2 or len(set(pids)) != 2
                    or any(type(pid) is not int or pid <= 0 for pid in pids) or type(stop) is not int
                    or context != dict(identity, pids=pids, deadline_ns=stop)):
                raise ValueError('invalid participants run/job/token/PID/deadline')
            actual_pids = summary['supervisor']['pids']
            if pids != actual_pids or any(type(pid) is not int for pid in actual_pids):
                raise ValueError('participants differ from actual supervisor PIDs')
            spawned = [row for row in parent if row['event'] == 'spawned']
            if (len(spawned) != 2 or any(type(row['rank']) is not int or type(row['child_pid']) is not int for row in spawned)
                    or {row['rank']:row['child_pid'] for row in spawned} != dict(enumerate(pids))):
                raise ValueError('participants differ from parent spawn events')
            begin = next(row for row in parent if row['event'] == 'supervisor_begin')
            if (manifest['pg_timeout'] != 5 or manifest['deadline'] != 30 or begin['deadline_seconds'] != 30
                    or not 0 < stop-begin['monotonic_ns'] <= 30_000_000_000):
                raise ValueError('deadline not derived from the original supervisor boundary')
            own_times = {}
            for rank in (0, 1):
                ready = values['ready_rank' + str(rank) + '.json']
                if (type(ready.get('rank')) is not int or type(ready.get('pid')) is not int
                        or ready != dict(identity, rank=rank, pid=pids[rank])):
                    raise ValueError('wrong ready run/job/token/rank/PID for rank' + str(rank))
                rows = events(directory / ('rank' + str(rank) + '.events.jsonl'), issues)
                ordered, times = [], {}
                required = ['after_framework', 'preparation_complete', 'ready_published', 'both_ready', 'init_process_group_begin']
                for event in required:
                    if event == 'after_framework':
                        matches = [(i, row) for i, row in enumerate(rows)
                                   if row['event'] == 'checkpoint_end' and row.get('stage') == 'after_framework']
                    else:
                        matches = [(i, row) for i, row in enumerate(rows) if row['event'] == event]
                    if len(matches) != 1: raise ValueError('rank' + str(rank) + ': missing/duplicate own event ' + event)
                    index, row = matches[0]; ordered.append(index)
                    times[event] = row['monotonic_ns']
                    if row['pid'] != pids[rank]: raise ValueError('worker event PID mismatch')
                    if event == 'ready_published' and any(row.get(k) != v for k, v in dict(identity, rank=rank).items()):
                        raise ValueError('ready_published identity mismatch')
                    if event == 'both_ready' and row.get('pids') != pids: raise ValueError('both_ready PID mismatch')
                    if event in ('both_ready', 'init_process_group_begin') and row['monotonic_ns'] >= stop:
                        raise ValueError('both-ready/init attempt outside original deadline')
                if ordered != sorted(ordered): raise ValueError('worker own readiness event order mismatch')
                own_times[str(rank)] = times
                # Never compare peer ready_published clocks: file replacement precedes that log.
            verified_context = dict(identity, pids=pids, deadline_ns=stop,
                                    supervisor_begin_ns=begin['monotonic_ns'], worker_event_ns=own_times)
        except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError, AttributeError, StopIteration) as exc:
            issues.append('readiness evidence incomplete: ' + str(exc))
        case = dict(complete=not issues, files=files, temporary_files=temporary,
                    verified_context=verified_context, issues=issues)
        result['cases'][name] = case
        result['issues'].extend(name + ': ' + text for text in issues)
    if result['cases']:
        result['complete'] = not result['issues']
        result['status'] = 'CONSISTENT_AVAILABLE_READINESS_ONLY' if result['complete'] else 'READINESS_EVIDENCE_INCOMPLETE'
    return result
