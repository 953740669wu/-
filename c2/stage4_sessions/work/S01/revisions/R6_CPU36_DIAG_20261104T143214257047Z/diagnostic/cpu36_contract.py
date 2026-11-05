"""CPU36 selection and per-TID boundary checks, independent of torch."""
import json
import os
from pathlib import Path


def cpu_list(text):
    values = []
    for item in text.strip().split(','):
        if item:
            a, sep, b = item.partition('-')
            values.extend(range(int(a), int(b) + 1) if sep else [int(a)])
    return values


def select_cpus(allocated, domain, siblings):
    allocated, domain = sorted(set(allocated)), sorted(set(domain))
    if len(domain) != 38 or len(allocated) not in (36, 38) or not set(allocated) <= set(domain):
        raise ValueError('require an authorized 38-core domain or its exact first 36 cores')
    if len({tuple(sorted(siblings[cpu])) for cpu in domain}) != 38:
        raise ValueError('domain does not contain 38 distinct physical cores')
    selected, reserved = domain[:-2], domain[-2:]
    if not set(selected) <= set(allocated):
        raise ValueError('allocation cannot provide first36 while reserving the last2 cores')
    return dict(allocated=allocated, domain_cpus=domain, selected=selected, reserved=reserved)


def validate_threads(selected, snapshot, torch_threads, expected_threads=36):
    errors = []
    if len(set(selected)) != 36:
        errors.append('selected CPU set must contain 36 CPUs')
    if type(torch_threads) is not int or torch_threads != expected_threads:
        errors.append(f'actual torch intra-op threads {torch_threads} != {expected_threads}')
    rows = snapshot.get('threads', [])
    if snapshot.get('complete') is not True or not rows:
        errors.append('all-TID evidence is missing/incomplete')
    tids = []
    for row in rows:
        tids.append(row.get('tid'))
        mask = row.get('affinity')
        if not isinstance(mask, list) or not mask or not set(mask) <= set(selected):
            errors.append(f'TID {row.get("tid")} outside/unknown selected36 boundary: {mask}')
    if len(set(tids)) != len(tids) or any(type(tid) is not int or tid <= 0 for tid in tids):
        errors.append('invalid/duplicate TID evidence')
    return errors


def snapshot_threads(pid):
    result = dict(complete=True, threads=[], vanished=[], errors=[])
    try:
        entries = list(Path(f'/proc/{pid}/task').iterdir())
    except OSError as exc:
        return dict(complete=False, threads=[], errors=[str(exc)])
    for entry in entries:
        try:
            stat = (entry / 'stat').read_text()
            fields = stat[stat.rfind(')') + 2:].split()  # fields start at Linux stat field3
            result['threads'].append(dict(tid=int(entry.name), affinity=sorted(os.sched_getaffinity(int(entry.name))),
                                          ticks=int(fields[11]) + int(fields[12]), last_cpu=int(fields[36]),
                                          state=fields[0], start_ticks=int(fields[19])))
        except (FileNotFoundError, ProcessLookupError):
            result['vanished'].append(int(entry.name))
        except (OSError, ValueError, IndexError) as exc:
            result['complete'] = False
            result['errors'].append(f'{entry.name}: {exc}')
    return result


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)
