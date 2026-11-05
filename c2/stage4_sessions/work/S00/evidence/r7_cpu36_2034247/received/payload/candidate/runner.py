"""S01 stdlib-only process, barrier and result-integrity support. No model computation."""
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import statistics as st
import subprocess
import sys
import time
import hashlib
from collections import deque
import cpu36_contract as cpu

_STARTED = time.time()
RATE = {'pre': 'pretrain', 'dec': 'decoder'}
_CPU36_KEY, _CPU36_EVIDENCE = None, None


def atomic_json(path, data):
    path = Path(path)
    content = json.dumps(data, indent=1, allow_nan=False) + '\n'
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    try:
        tmp.write_text(content, encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    value = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError(f'expected JSON object: {path}')
    return value


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def barrier(name):
    directory = os.environ.get('SYNC_DIR')
    if not directory:
        return
    directory = Path(directory)
    ranks = [int(d) for d in os.environ['SYNC_RANKS'].split(',')]
    rank = int(os.environ['SYNC_RANK'])
    timeout = float(os.environ.get('SYNC_TIMEOUT', '300'))
    if len(ranks) != int(os.environ['SYNC_N']) or len(set(ranks)) != len(ranks) or rank not in ranks or not positive(timeout):
        raise ValueError('invalid barrier rank set or timeout')
    if not re.fullmatch(r'[A-Za-z0-9_]+', name):
        raise ValueError('invalid barrier name')
    run_id = os.environ['RUN_ID']
    marker = directory / f'{name}.{rank}.json'
    if marker.exists():
        raise RuntimeError(f'duplicate barrier arrival: {marker}')
    atomic_json(marker, dict(run_id=run_id, rank=rank))
    deadline = time.monotonic() + timeout
    while True:
        if (directory / 'ABORT.json').exists():
            raise RuntimeError(f'peer failed: {read_json(directory / "ABORT.json")}')
        ready = 0
        for peer in ranks:
            path = directory / f'{name}.{peer}.json'
            if path.exists():
                if read_json(path) != dict(run_id=run_id, rank=peer):
                    raise RuntimeError(f'stale or invalid barrier marker: {path}')
                ready += 1
        if ready == len(ranks):
            return
        if time.monotonic() >= deadline:
            atomic_json(directory / 'ABORT.json', dict(reason=f'barrier timeout: {name}', rank=rank))
            raise TimeoutError(f'barrier {name}: {ready}/{len(ranks)} ranks after {timeout}s')
        time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def thread_checkpoint(name, torch_threads=None, torch_interop=None, parallel_info=None):
    """Fail closed and retain evidence outside the measured model step."""
    if not os.environ.get('RUN_ID'):
        return
    global _CPU36_KEY, _CPU36_EVIDENCE
    path = Path(os.environ['CPU36_CONTEXT']).resolve()
    if path.parent != Path(os.environ['SYNC_DIR']).resolve():
        raise ValueError('CPU36 context must belong to this round sync directory')
    context = read_json(path)
    if context['version'] != cpu.VERSION or not context['job_id']:
        raise ValueError('CPU36 context version/job identity missing')
    for key, value in [('run_id', os.environ['RUN_ID']), ('host', socket.gethostname()),
                       ('round', int(os.environ['RUN_ROUND'])), ('rank', int(os.environ['SYNC_RANK']))]:
        if context[key] != value:
            raise ValueError(f'CPU36 context identity mismatch: {key}')
    cpu.validate_receipt(context['receipt'])
    key = (str(path), sha(path))
    if key != _CPU36_KEY:
        _CPU36_KEY = key
        _CPU36_EVIDENCE = dict(version=cpu.VERSION, context=context, checkpoints=[])
    runtime = cpu.runtime_info() if name != 'before_framework' else None
    item = dict(name=name, pid=os.getpid(), calling_tid=os.getpid(), time=time.time(),
                calling_affinity=sorted(os.sched_getaffinity(0)), snapshot=cpu.snapshot_threads(os.getpid()),
                torch_intraop=torch_threads, torch_interop=torch_interop, parallel_info=parallel_info,
                environment={key: os.environ.get(key) for key in cpu.ENVIRONMENT}, runtime=runtime)
    _CPU36_EVIDENCE['checkpoints'].append(item)
    try:
        cpu.validate_checkpoint(item, context['receipt'])
    except (ValueError, KeyError, TypeError) as exc:
        _CPU36_EVIDENCE.setdefault('errors', []).append(str(exc))
        raise
    finally:
        atomic_json(path.parent / f'thread_rank{context["rank"]}.json', _CPU36_EVIDENCE)


def publish_result(out, output, torch_threads=None, torch_interop=None, parallel_info=None):
    if os.environ.get('RUN_ID'):
        thread_checkpoint('publish', torch_threads, torch_interop, parallel_info)
        code = Path(__file__).resolve().parent
        out['run'] = dict(run_id=os.environ['RUN_ID'], host=socket.gethostname(),
                          input_protocol=os.environ['INPUT_PROTOCOL'],
                          round=int(os.environ['RUN_ROUND']), rank=int(os.environ['SYNC_RANK']),
                          pid=os.getpid(), started=_STARTED, finished=time.time(),
                          omp_threads=int(os.environ['OMP_NUM_THREADS']),
                          affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
                          source_sha256={name: sha(code / name) for name in ('s4_models.py', 'runner.py', 'kml_ops.py', 'cpu36_contract.py')},
                          cpu36=_CPU36_EVIDENCE)
    atomic_json(Path(output) / 'reports' / os.environ.get('TIMING_OUT', 'models_timing.json'), out)


def diagnostic_config(env):
    # The remote sampler was identified by hash only; never execute unreviewed shared code.
    if env.get('SAMPLE_FOREIGN', '0') != '0':
        raise ValueError('SAMPLE_FOREIGN cannot be enabled: sample_foreign.py source unavailable')
    limit = int(env.get('CORES_PER_DOM', '36'))
    if limit != 36:
        raise ValueError('this candidate requires CORES_PER_DOM=36')
    return dict(sample_foreign=False, sample_foreign_reason='disabled: sample_foreign.py source unavailable',
                cores_per_domain=limit, python_faulthandler=True)


def verify_legacy_inputs(paths, identity):
    if identity['input_protocol'] != 'LEGACY_TIMING_ONLY' or set(paths) != set(identity['cases']):
        raise ValueError('legacy timing input protocol/case set mismatch')
    for case, path in paths.items():
        if sha(path) != identity['cases'][case]:
            raise ValueError(f'legacy timing file hash mismatch: {case}')


def supervise(commands, environments, directory, timeout):
    """Own each child/session; record every exit, fail fast, bound termination."""
    if not positive(timeout) or not commands:
        raise ValueError('positive timeout and at least one child required')
    directory = Path(directory)
    processes, states, logs = {}, {}, []
    thread_logs, observed, monitor_contexts = {}, {}, {}
    reason = None
    try:
        for rank, command in commands.items():
            states[rank] = dict(pid=None, started=time.time(), finished=None, exit_code=None, timed_out=False)
            stream = open(directory / f'rank{rank}.log', 'wb')
            logs.append(stream)
            try:
                proc = subprocess.Popen(command, env=environments[rank], stdout=stream, stderr=subprocess.STDOUT,
                                        start_new_session=(os.name == 'posix'))
            except OSError as exc:
                states[rank].update(exit_code=127, finished=time.time(), error=str(exc))
                reason = f'rank {rank}: spawn failed: {exc}'
                break
            processes[rank] = proc
            states[rank]['pid'] = proc.pid
            if environments[rank].get('CPU36_CONTEXT'):
                monitor_contexts[rank] = read_json(environments[rank]['CPU36_CONTEXT'])
                thread_logs[rank] = open(directory / f'rank{rank}.threads.jsonl', 'w', encoding='utf-8')
                logs.append(thread_logs[rank])
                observed[rank] = {}
                states[rank]['thread_monitor'] = dict(pid=proc.pid, snapshots=0, incomplete_samples=0,
                                                      violations=[], threads=[])
        deadline = time.monotonic() + timeout
        while not reason:
            for rank, proc in processes.items():
                status = states[rank]
                code = proc.poll()
                if code is not None and status['exit_code'] is None:
                    status.update(exit_code=code, finished=time.time())
                if code is not None and code != 0:
                    reason = f'rank {rank}: exit {code}'
                marker = directory / f'thread_rank{rank}.json'
                if code is None and rank in thread_logs and marker.exists():
                    evidence = read_json(marker)
                    monitor = status['thread_monitor']
                    selected = monitor_contexts[rank]['receipt']['selected']
                    if evidence['context'] != monitor_contexts[rank] or evidence['checkpoints'][0]['pid'] != proc.pid:
                        reason = f'rank {rank}: thread monitor handshake identity mismatch'
                    if evidence.get('errors'):
                        reason = f'rank {rank}: CPU36 worker checkpoint failed'
                    snap = cpu.snapshot_threads(proc.pid)
                    thread_logs[rank].write(json.dumps(dict(time_ns=time.time_ns(), snapshot=snap)) + '\n')
                    for row in snap['threads']:
                        entry = observed[rank].setdefault(row['tid'], dict(tid=row['tid'], masks=[]))
                        if row['affinity'] not in entry['masks']:
                            entry['masks'].append(row['affinity'])
                        if not row['affinity'] or not set(row['affinity']) <= set(selected):
                            monitor['violations'].append(row)
                            reason = f'rank {rank}: TID outside selected36'
                    if snap['complete'] and snap['threads']:
                        monitor['snapshots'] += 1
                    elif proc.poll() is None:
                        monitor['incomplete_samples'] += 1
                        reason = f'rank {rank}: incomplete live all-TID evidence'
            if reason or all(p.poll() is not None for p in processes.values()):
                break
            if time.monotonic() >= deadline:
                for rank, proc in processes.items():
                    if proc.poll() is None:
                        states[rank]['timed_out'] = True
                reason = f'round timeout after {timeout}s'
                break
            time.sleep(0.05)
    except BaseException:
        reason = 'supervisor interrupted'
        raise
    finally:
        if reason:
            atomic_json(directory / 'ABORT.json', dict(reason=reason))
            for proc in processes.values():
                try:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGTERM)
                    elif proc.poll() is None:
                        proc.terminate()
                except ProcessLookupError:
                    pass
            grace = time.monotonic() + 0.5
            while any(p.poll() is None for p in processes.values()) and time.monotonic() < grace:
                time.sleep(0.02)
            for proc in processes.values():
                try:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGKILL)
                    elif proc.poll() is None:
                        proc.kill()
                except ProcessLookupError:
                    pass
        for rank in commands:
            status = states.setdefault(rank, dict(pid=None, started=time.time(), finished=None,
                                                   exit_code=125, timed_out=False, error='not launched: peer failure'))
            if rank in processes:
                status['exit_code'] = processes[rank].wait(timeout=2)
            if status['finished'] is None:
                status['finished'] = time.time()
            if rank in observed:
                status['thread_monitor']['threads'] = list(observed[rank].values())
            matches, count = deque(maxlen=20), 0
            log = directory / f'rank{rank}.log'
            if log.is_file():
                with log.open(encoding='utf-8', errors='replace') as stream:
                    for number, line in enumerate(stream, 1):
                        if re.search(r'Killed|MemoryError|Traceback|dumped core|Fatal Python error|Bus error|Segmentation', line):
                            count += 1
                            matches.append(f'{number}: {line.rstrip()[:1024]}')
            status['diagnostic_matches'] = dict(count=count, tail=list(matches))
            atomic_json(directory / f'rank{rank}.status.json', status)
        for stream in logs:
            stream.close()
    return states


def summarize(directory, completed_rounds=None):
    directory = Path(directory)
    errors, values = [], {}
    try:
        spec = read_json(directory / 'manifest.json')
        ranks, planned = spec['domains'], spec['rounds']
        if not ranks or len(set(ranks)) != len(ranks) or any(type(d) is not int or d < 0 for d in ranks):
            raise ValueError('invalid expected domains')
        if type(planned) is not int or planned < 3:
            raise ValueError('stability requires at least three complete rounds')
        rounds = planned if completed_rounds is None else completed_rounds
        if type(rounds) is not int or not 1 <= rounds <= planned:
            raise ValueError('invalid completed-round count')
        if not spec['belts'] or not set(spec['belts']) <= {'16_adjacent', '32_skip4'}:
            raise ValueError('invalid expected belts')
        if not spec['parts'] or not set(spec['parts']) <= set(RATE):
            raise ValueError('invalid expected parts')
        expected = {f'r{r}_d{d}.json' for r in range(1, rounds + 1) for d in ranks}
        actual = {p.name for p in directory.glob('r*_d*.json') if not p.name.endswith('.status.json')}
        if actual != expected:
            errors.append(f'result file set mismatch; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}')
        statuses = {p.name for p in directory.glob('r*_d*.status.json')}
        expected_statuses = {name.replace('.json', '.status.json') for name in expected}
        if statuses != expected_statuses:
            errors.append('process status file set mismatch')
        runtime = None
        for r in range(1, rounds + 1):
            for d in ranks:
                label = f'r{r}_d{d}'
                try:
                    data = read_json(directory / f'{label}.json')
                    state = read_json(directory / f'{label}.status.json')
                    if type(state['exit_code']) is not int or state['exit_code'] != 0 or state['timed_out'] is not False:
                        raise ValueError(f'process failed/timed out: {state}')
                    if type(state['pid']) is not int or state['pid'] <= 0:
                        raise ValueError('missing/invalid observed process PID')
                    meta = data['run']
                    for key, expected_value in [('run_id', spec['run_id']), ('host', spec['host']),
                                                ('input_protocol', spec['input_protocol']),
                                                ('round', r), ('rank', d), ('pid', state['pid'])]:
                        if type(meta[key]) is not type(expected_value) or meta[key] != expected_value:
                            raise ValueError(f'identity mismatch: {key}')
                    if not (positive(state['started']) and positive(state['finished']) and positive(meta['started'])
                            and positive(meta['finished']) and state['started'] <= meta['started'] <= meta['finished'] <= state['finished']):
                        raise ValueError('result outside this process time window')
                    mtime = (directory / f'{label}.json').stat().st_mtime
                    if not state['started'] - 2 <= mtime <= state['finished'] + 2:
                        raise ValueError('stale/future result mtime')
                    for key in ('config', 'device', 'cases'):
                        if json.dumps(data[key], sort_keys=True) != json.dumps(spec[key], sort_keys=True):
                            raise ValueError(f'{key} mismatch')
                    if 'source_sha256' in spec and meta['source_sha256'] != spec['source_sha256']:
                        raise ValueError('loaded candidate source hash mismatch')
                    cpu.validate_result(spec, data, state, r, d)
                    if 'cpus' in spec and meta['omp_threads'] != len(spec['cpus'][str(r)][str(d)]):
                        raise ValueError('thread count mismatch')
                    if not isinstance(data['torch'], str) or not data['torch']:
                        raise ValueError('runtime version missing')
                    if runtime is None:
                        runtime = data['torch']
                    elif data['torch'] != runtime:
                        raise ValueError('torch runtime mismatch')
                    batch = spec['config']['batch']
                    for belt in spec['belts']:
                        peak = data[belt]['peak_mem_GB']
                        if not positive(peak):
                            raise ValueError('invalid legacy RSS/peak metric')
                        for part in spec['parts']:
                            prefix = RATE[part]
                            rate, step = data[belt][f'{prefix}_frames_per_s'], data[belt][f'{prefix}_step_s_B{batch}']
                            if not positive(rate) or not positive(step) or not math.isclose(rate * step, batch, rel_tol=1e-9):
                                raise ValueError(f'invalid/inconsistent measurement: {belt}/{part}')
                            values.setdefault((belt, part, r), []).append((rate, step, peak))
                except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
                    errors.append(f'{label}: {exc}')
        if errors:
            return dict(status='FAIL', errors=errors)
        if rounds < planned:
            return dict(status='INCOMPLETE', errors=[], completed_rounds=rounds, planned_rounds=planned)
        metrics = {}
        for belt in spec['belts']:
            for part in spec['parts']:
                rows = []
                for r in range(1, rounds + 1):
                    data = values[belt, part, r]
                    rates = [x[0] for x in data]
                    rows.append(dict(round=r, domains=len(ranks), sum=sum(rates), minimum=min(rates),
                                     median=st.median(rates), maximum=max(rates), conservative=len(ranks) * min(rates),
                                     slowest_step_s=max(x[1] for x in data), legacy_peak_mem_GB=max(x[2] for x in data)))
                sums = [row['sum'] for row in rows]
                spread = (max(sums) - min(sums)) / st.mean(sums)
                metrics[f'{belt}/{part}'] = dict(rounds=rows, sums=sums, conservative=[x['conservative'] for x in rows],
                                                spread=spread, stable=spread <= 0.05)
        return dict(status='PASS' if all(x['stable'] for x in metrics.values()) else 'UNSTABLE', errors=[], metrics=metrics,
                    scope='runner integrity and legacy A1 spread only; no numerical or deployment acceptance')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(status='FAIL', errors=[f'manifest: {exc}'])


def model_config(env):
    return dict(amp=env['AMP'], batch=int(env['BATCH']), channels_last=env['CHANNELS_LAST'] == '1',
                compile=env['COMPILE'] == '1', reps=int(env['REPS']), kml_conv=env['KML_CONV'] == '1',
                kml_blas=env['KML_BLAS_LIB'], ckpt=env['CKPT'] == '1', kml_linear=env['KML_LINEAR'] == '1',
                linear_dtype=env['LINEAR_DTYPE'] if env['KML_LINEAR'] == '1' else None)


def preflight(root, contracts, sources, files, job_id):
    """Actual imports only; a fresh same-job reference is mandatory for model launch."""
    if os.environ.get('RUN_ID'):
        raise ValueError('preflight cannot inherit a worker RUN_ID')
    selected = sorted({cpu_id for receipt in contracts.values() for cpu_id in receipt['selected']})
    os.sched_setaffinity(0, selected)
    import importlib
    import torch
    import numpy
    import kml_ops
    saved = sys.argv
    try:
        sys.argv = [str(root / 'candidate/s4_models.py'), str(root / 'output'), 's0322p0,s0322p1']
        importlib.import_module('s4_models')
    finally:
        sys.argv = saved
    if torch.get_num_threads() != 36:
        raise ValueError('actual preflight PyTorch intra-op threads !=36')
    snapshot = cpu.snapshot_threads(os.getpid())
    cpu.validate_snapshot(selected, snapshot)
    runtime = cpu.runtime_info()
    for path in [root / 'lib/libkml_sgemm_shim.so', Path(os.environ['KML_BLAS_LIB'])]:
        mappings = {str(Path(name).resolve()): info['sha256'] for name, info in runtime['libraries'].items()}
        if mappings.get(str(path.resolve())) != sha(path):
            raise ValueError(f'required library not actually loaded with frozen identity: {path}')
    record = dict(status='PASS_IMPORT_ONLY', version=cpu.VERSION, job_id=job_id, host=socket.gethostname(),
                  source_sha256=sources, frozen_files=files,
                  cpu_contracts={str(d): value for d, value in contracts.items()}, runtime=runtime,
                  torch_intraop=torch.get_num_threads(), torch_interop=torch.get_num_interop_threads(),
                  snapshot=snapshot, environment={key: os.environ.get(key) for key in cpu.ENVIRONMENT},
                  model_forward_backward='NOT_RUN', timestamp_ns=time.time_ns())
    directory = root / 'evidence'
    directory.mkdir(exist_ok=True)
    path = directory / f'CPU36_PREFLIGHT_{time.time_ns()}.json'
    atomic_json(path, record)
    print(path, flush=True)
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--summarize':
        result = summarize(sys.argv[2])
        print(json.dumps(result, indent=1))
        return 0 if result['status'] == 'PASS' else 1
    if sys.platform != 'linux':
        raise ValueError('cluster launch requires Linux; use tests for local protocol verification')
    if socket.gethostname().lower().startswith('login'):
        raise ValueError('model/import preflight requires an allocated compute node')
    env = os.environ.copy()
    if {key: env.get(key) for key in cpu.ENVIRONMENT} != cpu.ENVIRONMENT:
        raise ValueError('use the explicit CPU36 C-group launcher environment')
    job_id = env.get('CCS_JOB_ID') or env.get('S01_JOB_ID')
    if not job_id:
        raise ValueError('an allocated compute job identity is required')
    import_only = len(sys.argv) == 2 and sys.argv[1] == '--preflight'
    defaults = dict(DEVICE='cpu', AMP='fp32', BATCH='64', REPS='5', BELTS='16_adjacent,32_skip4', PARTS='pre,dec',
                    CHANNELS_LAST='0', COMPILE='0', MKLDNN='1', CKPT='0', KML_LINEAR='0', LINEAR_DTYPE='fp32', KML_CONV='0')
    for key, value in defaults.items():
        env.setdefault(key, value)
    tag = 'preflight' if import_only else (sys.argv[1] if len(sys.argv) > 1 else 'node16')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', tag):
        raise ValueError('tag must be a single safe directory name')
    for assignment in sys.argv[2:]:
        key, sep, value = assignment.partition('=')
        if not sep or key not in defaults:
            raise ValueError(f'unsupported/protected environment assignment: {key}')
        env[key] = value
    if env['DEVICE'] != 'cpu' or env['AMP'] != 'fp32' or env['LINEAR_DTYPE'] != 'fp32':
        raise ValueError('S01 candidate keeps CPU fp32 fixed')
    if any(env[k] not in ('0', '1') for k in ('CHANNELS_LAST', 'COMPILE', 'MKLDNN', 'CKPT', 'KML_LINEAR', 'KML_CONV')):
        raise ValueError('boolean knobs must be 0 or 1')
    diagnostics = diagnostic_config(env)
    env.update(GN='0', SAMPLING='0', PYTHONDONTWRITEBYTECODE='1', PYTHONFAULTHANDLER='1',
               INPUT_PROTOCOL='LEGACY_TIMING_ONLY')
    rounds, count = int(env.get('ROUNDS', '3')), int(env.get('NDOM', '16'))
    timeout, sync_timeout = float(env.get('RUN_TIMEOUT', '5400')), float(env.get('SYNC_TIMEOUT', '300'))
    if rounds < 3 or count < 1 or not positive(timeout) or not positive(sync_timeout):
        raise ValueError('require >=3 rounds, positive domain count and finite positive timeouts')
    if int(env['BATCH']) < 1 or int(env['REPS']) < 1:
        raise ValueError('positive batch/reps required')
    belts, parts = env['BELTS'].split(','), env['PARTS'].split(',')
    if not set(belts) <= {'16_adjacent', '32_skip4'} or not set(parts) <= set(RATE):
        raise ValueError('unknown belt/part')
    mempol = env.get('MEMPOL', 'membind')
    if mempol not in ('membind', 'preferred'):
        raise ValueError('unsupported memory policy')
    root = Path(env['S01_RUN']).resolve()
    code, output = root / 'candidate', root / 'output'
    if Path(__file__).resolve().parent != code:
        raise ValueError('runner must execute from S01_RUN/candidate')
    allowed = os.sched_getaffinity(0)
    contracts = cpu.discover_contracts(allowed, count)
    ranks = sorted(contracts)
    hbm = env.get('HBM', '0') == '1'
    libraries = [root / 'lib/libkml_sgemm_shim.so', Path(env['KML_BLAS_LIB'])]
    if hbm:
        libraries.append(root / 'lib/libhbm_alloc.so')
        for d in ranks:
            node = Path(f'/sys/devices/system/node/node{16+d}')
            if d >= 16 or not node.is_dir() or (node / 'cpulist').read_text().strip():
                raise ValueError(f'historical HBM mapping 16+{d} is not a memory-only node; require topology review')
    sources = {name: sha(code / name) for name in ('s4_models.py', 'runner.py', 'kml_ops.py', 'cpu36_contract.py')}
    inputs = {case: output / f'cases/{case}/frames.npz' for case in ('s0322p0', 's0322p1')}
    verify_legacy_inputs(inputs, read_json(code / 'legacy_inputs.json'))
    files = {str(path): sha(path) for path in [*inputs.values(), *libraries, code / 'run_node16.sh', code / 'legacy_inputs.json']}
    if import_only:
        return preflight(root, contracts, sources, files, job_id)
    reference_path = Path(env['CPU36_RUNTIME_REFERENCE']).resolve()
    reference_path.relative_to((root / 'evidence').resolve())
    reference = read_json(reference_path)
    if not (reference['status'] == 'PASS_IMPORT_ONLY' and reference['version'] == cpu.VERSION
            and reference['job_id'] == job_id and reference['host'] == socket.gethostname()
            and reference['source_sha256'] == sources and reference['frozen_files'] == files
            and reference['cpu_contracts'] == {str(d): value for d, value in contracts.items()}
            and reference['environment'] == cpu.ENVIRONMENT and reference['torch_intraop'] == 36):
        raise ValueError('fresh same-job CPU36 import/source/input/library reference mismatch')
    files[str(reference_path)] = sha(reference_path)
    files.update({path: info['sha256'] for path, info in reference['runtime']['libraries'].items()})
    os.sched_setaffinity(0, sorted({c for receipt in contracts.values() for c in receipt['selected']}))
    directory = output / 'reports' / tag
    directory.mkdir(parents=True, exist_ok=False)  # Never reuse even an empty old tag.
    spec = dict(run_id=tag, host=socket.gethostname(), domains=ranks, rounds=rounds, belts=belts, parts=parts,
                config=model_config(env), device=env['DEVICE'], cases=['s0322p0', 's0322p1'], source_sha256=sources,
                input_protocol=env['INPUT_PROTOCOL'], diagnostics=diagnostics,
                cpu36_version=cpu.VERSION, job_id=job_id, worker_environment=cpu.ENVIRONMENT,
                cpu_contracts={str(d): value for d, value in contracts.items()}, cpu_contexts={},
                runtime_reference=reference['runtime'],
                frozen_files=files, cpus={}, memory_policy=mempol, hbm=hbm, skip_busy=env.get('SKIP_BUSY', '0'),
                run_timeout=timeout, sync_timeout=sync_timeout)
    atomic_json(directory / 'manifest.json', spec)
    for r in range(1, rounds + 1):
        sync = directory / f'sync_r{r}'
        sync.mkdir()
        busy = set()
        if env.get('SKIP_BUSY', '0') == '1':
            sample = subprocess.check_output(['ps', '-eLo', 'psr,pcpu', '--no-headers'], text=True)
            (sync / 'busy_snapshot.txt').write_text(sample)
            busy = {int(line.split()[0]) for line in sample.splitlines() if float(line.split()[1]) > 5}
        # Validate ALL domains before launching ANY process. Never drop an empty/slow domain.
        selected = {d: contracts[d]['selected'] for d in ranks}
        if any(set(cpus) & busy for cpus in selected.values()):
            raise ValueError('SKIP_BUSY conflicts with the fixed first36/reserved2 CPU contract')
        spec['cpus'][str(r)] = {str(d): cpus for d, cpus in selected.items()}
        atomic_json(directory / 'manifest.json', spec)
        commands, environments = {}, {}
        for d in ranks:
            context = dict(version=cpu.VERSION, run_id=tag, host=socket.gethostname(), job_id=job_id,
                           round=r, rank=d, receipt=contracts[d])
            context_path = sync / f'cpu36_d{d}.json'
            atomic_json(context_path, context)
            spec['cpu_contexts'].setdefault(str(r), {})[str(d)] = context
            child = env.copy()
            child.update(RUN_ID=tag, RUN_ROUND=str(r), SYNC_DIR=str(sync), SYNC_N=str(len(ranks)),
                         SYNC_RANKS=','.join(map(str, ranks)), SYNC_RANK=str(d), SYNC_TIMEOUT=str(sync_timeout),
                         TIMING_OUT=f'{tag}/r{r}_d{d}.json', OMP_NUM_THREADS=str(len(selected[d])))
            child.update(cpu.ENVIRONMENT)
            child['CPU36_CONTEXT'] = str(context_path)
            if hbm:
                child.update(HBM_NODE=str(16+d), HBM_STATS='1', LD_PRELOAD=f'{root}/lib/libhbm_alloc.so:' + env['LD_PRELOAD'])
            memory = f'{d},{16+d}' if hbm else str(d)
            commands[d] = ['numactl', '--physcpubind=' + ','.join(map(str, selected[d])), f'--{mempol}={memory}',
                           sys.executable, str(code / 's4_models.py'), str(output), 's0322p0,s0322p1']
            environments[d] = child
        atomic_json(directory / 'manifest.json', spec)
        atomic_json(sync / 'commands.json', {str(d): command for d, command in commands.items()})
        states = supervise(commands, environments, sync, timeout)
        for d, state in states.items():
            atomic_json(directory / f'r{r}_d{d}.status.json', state)
        if any(s['exit_code'] != 0 or s['timed_out'] for s in states.values()):
            atomic_json(directory / 'summary.json', dict(status='FAIL', errors=[f'round {r}: process failure; see sync logs/statuses']))
            print('NODE16_FAILED', flush=True)
            return 1
        if any(sha(Path(path)) != digest for path, digest in files.items()) or any(sha(code / name) != digest for name, digest in sources.items()):
            raise ValueError('frozen source/input/library changed during run')
        result = summarize(directory, completed_rounds=r)
        atomic_json(directory / 'summary.json', result)
        if result['status'] == 'FAIL':
            print(json.dumps(result, indent=1), flush=True)
            print('NODE16_FAILED', flush=True)
            return 1
    print(json.dumps(result, indent=1), flush=True)
    print('NODE16_DONE' if result['status'] == 'PASS' else 'NODE16_FAILED', flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, KeyboardInterrupt) as exc:
        print(f'NODE16_FAILED: {exc}', file=sys.stderr, flush=True)
        raise SystemExit(1)
