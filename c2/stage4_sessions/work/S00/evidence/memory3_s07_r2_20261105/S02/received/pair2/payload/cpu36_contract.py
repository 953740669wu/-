"""CPU36_MODEL_V1: allocation, per-TID boundaries and actual framework evidence."""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

VERSION = 'CPU36_MODEL_V1'
ENVIRONMENT = dict(OMP_NUM_THREADS='36', MKL_NUM_THREADS='36', OPENBLAS_NUM_THREADS='1',
                   OMP_PLACES='cores', OMP_PROC_BIND='close')
_HASHES = {}


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def cpu_list(text):
    values = []
    for item in text.strip().split(','):
        if item:
            a, sep, b = item.partition('-')
            values.extend(range(int(a), int(b) + 1) if sep else [int(a)])
    return values


def select_cpus(allocated, domain, siblings):
    siblings = {str(key): value for key, value in siblings.items()}
    if any(type(cpu) is not int or cpu < 0 for cpu in [*allocated, *domain]):
        raise ValueError('invalid CPU identifiers')
    allocated, domain = sorted(set(allocated)), sorted(set(domain))
    if len(domain) != 38 or len(allocated) not in (36, 38) or not set(allocated) <= set(domain):
        raise ValueError('require an authorized 38-core domain or its exact first36')
    groups = [tuple(sorted(siblings[str(cpu)])) for cpu in domain]
    if any(cpu not in group for cpu, group in zip(domain, groups)) or len(set(groups)) != 38:
        raise ValueError('38 distinct physical cores required')
    selected, reserved = domain[:-2], domain[-2:]
    if not set(selected) <= set(allocated):
        raise ValueError('cannot select first36 and reserve last2 from this allocation')
    return dict(allocated=allocated, domain_cpus=domain, selected=selected, reserved=reserved,
                physical_siblings={str(cpu): list(group) for cpu, group in zip(domain, groups)})


def discover_contracts(allowed, count):
    contracts = {}
    for node in sorted(Path('/sys/devices/system/node').glob('node[0-9]*'), key=lambda p: int(p.name[4:])):
        domain = cpu_list((node / 'cpulist').read_text())
        allocated = sorted(set(domain) & set(allowed))
        if allocated:
            siblings = {str(cpu): cpu_list(Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list').read_text())
                        for cpu in domain}
            receipt = select_cpus(allocated, domain, siblings)
            receipt['node'] = int(node.name[4:])
            contracts[receipt['node']] = receipt
            if len(contracts) == count:
                break
    if len(contracts) != count:
        raise ValueError(f'expected {count} authorized CPU36 domains, found {len(contracts)}')
    return contracts


def validate_receipt(receipt):
    rebuilt = select_cpus(receipt['allocated'], receipt['domain_cpus'], receipt['physical_siblings'])
    if receipt['selected'] != rebuilt['selected'] or receipt['reserved'] != rebuilt['reserved']:
        raise ValueError('selected36/reserved2 receipt mismatch')


def snapshot_threads(pid):
    result = dict(complete=True, threads=[], vanished=[], errors=[])
    try:
        entries = list(Path(f'/proc/{pid}/task').iterdir())
    except OSError as exc:
        return dict(complete=False, threads=[], vanished=[], errors=[str(exc)])
    for entry in entries:
        try:
            stat = (entry / 'stat').read_text()
            fields = stat[stat.rfind(')') + 2:].split()
            result['threads'].append(dict(tid=int(entry.name), affinity=sorted(os.sched_getaffinity(int(entry.name))),
                                          ticks=int(fields[11]) + int(fields[12]), start_ticks=int(fields[19]),
                                          last_cpu=int(fields[36]), state=fields[0]))
        except (FileNotFoundError, ProcessLookupError):
            result['complete'] = False
            result['vanished'].append(int(entry.name))
        except (OSError, ValueError, IndexError) as exc:
            result['complete'] = False
            result['errors'].append(f'{entry.name}: {exc}')
    return result


def validate_snapshot(selected, snapshot):
    rows = snapshot['threads']
    if snapshot.get('complete') is not True or snapshot.get('vanished') or snapshot.get('errors') or not rows:
        raise ValueError('missing/incomplete all-TID evidence')
    tids = []
    for row in rows:
        tids.append(row['tid'])
        mask = row['affinity']
        if not isinstance(mask, list) or not mask or any(type(cpu) is not int for cpu in mask) or not set(mask) <= set(selected):
            raise ValueError(f'TID {row["tid"]} outside selected36 boundary')
    if len(set(tids)) != len(tids) or any(type(tid) is not int or tid <= 0 for tid in tids):
        raise ValueError('invalid/duplicate TID evidence')


def runtime_info():
    modules = {}
    for name in ('torch', 'numpy', 'kml_ops'):
        module = sys.modules.get(name)
        if module is not None:
            modules[name] = dict(version=getattr(module, '__version__', None), path=str(Path(module.__file__).resolve()))
    paths = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                    if re.search(r'kml|blas|libomp|libgomp|hbm', line, re.I) and line.split()[-1].startswith('/')})
    libraries = {}
    for path in paths:
        if path not in _HASHES:
            _HASHES[path] = sha(path)
        info = dict(sha256=_HASHES[path])
        lib = ctypes.CDLL(path, mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)
        for name in ('omp_get_max_threads', 'omp_get_dynamic', 'omp_get_proc_bind', 'omp_get_num_places',
                     'openblas_get_num_threads', 'openblas_get_num_threads64_', 'openblas_get_num_threads_64_'):
            if hasattr(lib, name):
                fn = getattr(lib, name)
                fn.argtypes, fn.restype = [], ctypes.c_int
                info[name] = fn()
        libraries[path] = info
    return dict(modules=modules, libraries=libraries)


def required_checkpoints(spec):
    names = ['before_framework', 'after_framework']
    for belt in spec['belts']:
        names += [f'{belt}_after_warmup'] + [f'{belt}_after_{part}' for part in spec['parts']]
    return names + ['publish']


def validate_checkpoint(record, receipt):
    validate_snapshot(receipt['selected'], record['snapshot'])
    caller = next((row for row in record['snapshot']['threads'] if row['tid'] == record['calling_tid']), None)
    if caller is None or caller['affinity'] != record['calling_affinity']:
        raise ValueError('calling TID mask does not match all-TID snapshot')
    if record['environment'] != ENVIRONMENT:
        raise ValueError('conflicting CPU36 worker environment')
    if record['name'] != 'before_framework':
        if type(record['torch_intraop']) is not int or record['torch_intraop'] != 36:
            raise ValueError('actual PyTorch intra-op threads must be36')
        if type(record['torch_interop']) is not int or record['torch_interop'] <= 0 or not record['parallel_info']:
            raise ValueError('missing actual PyTorch thread metadata')
        omp = [entry for entry in record['runtime']['libraries'].values() if 'omp_get_max_threads' in entry]
        if not omp or any(entry['omp_get_max_threads'] != 36 for entry in omp):
            raise ValueError('missing/conflicting loaded OpenMP thread API')


def validate_result(spec, data, state, round_id, rank):
    if spec['cpu36_version'] != VERSION or spec['worker_environment'] != ENVIRONMENT:
        raise ValueError('CPU36 manifest contract missing/conflicting')
    receipt = spec['cpu_contracts'][str(rank)]
    validate_receipt(receipt)
    if spec['cpus'][str(round_id)][str(rank)] != receipt['selected']:
        raise ValueError('manifest selected36 mismatch')
    evidence = data['run']['cpu36']
    if evidence.get('errors'):
        raise ValueError('worker retained a failed CPU36 checkpoint')
    expected_context = dict(version=VERSION, run_id=spec['run_id'], host=spec['host'], job_id=spec['job_id'],
                            round=round_id, rank=rank, receipt=receipt)
    if (evidence['version'] != VERSION
            or json.dumps(evidence['context'], sort_keys=True) != json.dumps(expected_context, sort_keys=True)
            or json.dumps(evidence['context'], sort_keys=True) != json.dumps(spec['cpu_contexts'][str(round_id)][str(rank)], sort_keys=True)):
        raise ValueError('CPU36 worker context identity mismatch')
    names = [item['name'] for item in evidence['checkpoints']]
    if len(set(names)) != len(names) or not set(required_checkpoints(spec)) <= set(names):
        raise ValueError('missing/duplicate CPU36 checkpoints')
    order = [names.index(name) for name in required_checkpoints(spec)]
    if order != sorted(order) or names[:2] != ['before_framework', 'after_framework']:
        raise ValueError('CPU36 checkpoint order mismatch')
    for item in evidence['checkpoints']:
        if (type(item['time']) not in (int, float) or not math.isfinite(item['time'])
                or not data['run']['started'] <= item['time'] <= data['run']['finished']):
            raise ValueError('CPU36 checkpoint outside worker time window')
        if item['pid'] != data['run']['pid'] or item['calling_tid'] not in [row['tid'] for row in item['snapshot']['threads']]:
            raise ValueError('checkpoint PID/TID identity mismatch')
        validate_checkpoint(item, receipt)
        if item['name'] == 'before_framework':
            continue
        actual, reference = item['runtime'], spec['runtime_reference']
        for name, expected in reference['modules'].items():
            if name == 'kml_ops' and item['name'] == 'after_framework':
                continue
            if actual['modules'].get(name) != expected:
                raise ValueError(f'actual module identity mismatch: {name}')
        for path, info in actual['libraries'].items():
            if reference['libraries'].get(path, {}).get('sha256') != info['sha256']:
                raise ValueError(f'unfrozen/changed runtime library: {path}')
        if item['name'] != 'after_framework' and not set(reference['libraries']) <= set(actual['libraries']):
            raise ValueError('required runtime library mapping missing')
    last = evidence['checkpoints'][-1]
    if last['name'] != 'publish' or data['run']['affinity'] != last['calling_affinity']:
        raise ValueError('publication calling-thread metadata mismatch')
    monitor = state['thread_monitor']
    if monitor['pid'] != state['pid'] or type(monitor['snapshots']) is not int or monitor['snapshots'] < 1:
        raise ValueError('missing parent thread monitor evidence')
    if monitor['incomplete_samples'] or monitor['violations'] or not monitor['threads']:
        raise ValueError('incomplete/out-of-bound parent thread evidence')
    for thread in monitor['threads']:
        if not thread['masks']:
            raise ValueError('missing monitored TID mask')
        for mask in thread['masks']:
            validate_snapshot(receipt['selected'], dict(complete=True, threads=[dict(tid=thread['tid'], affinity=mask)]))
