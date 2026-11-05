"""S07 fixed 2-rank CPU/Gloo probe. No model, data loader or optimizer."""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import traceback

import cpu36_contract as cpu36

ENVIRONMENT = cpu36.ENVIRONMENT
BROADCAST = [1.0, -2.0, 0.5, 4.0]
TOTAL = [3.0, 6.0, -2.0, 1.0]


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def backend_info():
    try:
        import torch
        import torch.distributed as dist
        available = dist.is_available()
        gloo = available and dist.is_gloo_available()
        libraries = {}
        if sys.platform == 'linux':
            paths = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                     if '/' in line and any(name in line for name in
                                             ('libtorch', 'libc10', 'libgloo', 'torch/_C.'))}
            libraries = {path: cpu36.sha(path) for path in sorted(paths) if Path(path).is_file()}
        return dict(status='AVAILABLE_BUILT_NOT_COMM_TESTED' if gloo else 'UNAVAILABLE',
                    python=sys.version, executable=sys.executable, host=socket.gethostname(),
                    torch_version=torch.__version__, torch_path=torch.__file__,
                    torch_sha256=cpu36.sha(torch.__file__), distributed=available, gloo=gloo,
                    mpi=available and dist.is_mpi_available(),
                    nccl=available and dist.is_nccl_available(), build=torch.__config__.show(),
                    environment={key: os.environ.get(key) for key in
                                 (*ENVIRONMENT, 'PYTHONPATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD',
                                  'GLOO_SOCKET_IFNAME')},
                    loaded_torch_libraries=libraries, communication='NOT_RUN')
    except Exception as exc:
        return dict(status='UNAVAILABLE', executable=sys.executable, python=sys.version,
                    host=socket.gethostname(), error=f'{type(exc).__name__}: {exc}',
                    communication='NOT_RUN')


def validate_pair(receipts):
    if (len(receipts) != 2 or receipts[0]['node'] == receipts[1]['node']
            or set(receipts[0]['allocated']) & set(receipts[1]['allocated'])):
        raise ValueError('require two distinct, disjoint authorized domains')


def validate_current_job(job_id):
    current = os.environ.get('CCS_JOB_ID')
    if not current or not current.strip():
        raise ValueError('missing current CCS_JOB_ID')
    if job_id != current:
        raise ValueError('configured job_id does not match current CCS_JOB_ID')


def load_allocation(path):
    if sys.platform != 'linux':
        raise ValueError('CPU36 live probe requires Linux sysfs and affinity APIs')
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_current_job(data.get('job_id'))
    if set(data['ranks']) != {'0', '1'}:
        raise ValueError('exactly rank0/rank1 required')
    evidence = Path(data['scheduler_evidence'])
    if not evidence.is_absolute() or not evidence.is_file():
        raise ValueError('absolute raw scheduler allocation evidence required')
    allowed = set(os.sched_getaffinity(0))
    receipts = []
    for rank in range(2):
        entry = data['ranks'][str(rank)]
        node = entry['node']
        if type(node) is not int or node < 0:
            raise ValueError('invalid NUMA node')
        domain = cpu36.cpu_list(Path(f'/sys/devices/system/node/node{node}/cpulist').read_text())
        allocated = entry['allocated']
        if len(set(allocated)) != len(allocated) or not set(allocated) <= allowed:
            raise ValueError('duplicate CPU or allocation outside inherited authority')
        siblings = {str(cpu): cpu36.cpu_list(Path(
            f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list').read_text())
                    for cpu in domain}
        receipt = cpu36.select_cpus(allocated, domain, siblings)
        receipt['node'] = node
        receipts.append(receipt)
    validate_pair(receipts)
    return dict(job_id=str(data['job_id']), scheduler_evidence=str(evidence),
                scheduler_sha256=cpu36.sha(evidence), inherited_allowed=sorted(allowed),
                allocation_sha256=cpu36.sha(path), ranks=receipts)


def validate_reports(reports, run_id, pids):
    if len(reports) != 2:
        raise ValueError('missing or extra rank result')
    for rank, report in enumerate(reports):
        expected = dict(status='PASS', run_id=run_id, rank=rank, world_size=2,
                        pid=pids[rank], backend='gloo', identity=[0, 1],
                        broadcast=BROADCAST, total=TOTAL, shape=[4], dtype='torch.float32')
        for key, value in expected.items():
            if report.get(key) != value:
                raise ValueError(f'rank{rank}: {key} mismatch')


def supervise(commands, directory, deadline, environment):
    processes, logs = [], []
    state = dict(reason='complete', errors=[])
    started = time.monotonic()
    try:
        for rank, command in enumerate(commands):
            log = (directory / f'rank{rank}.log').open('w', encoding='utf-8')
            logs.append(log)
            processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                               env=environment, start_new_session=(os.name == 'posix')))
        while True:
            codes = [process.poll() for process in processes]
            if any(code is not None and code != 0 for code in codes):
                state['reason'] = 'child_failed'
                break
            if all(code == 0 for code in codes):
                break
            if time.monotonic() - started >= deadline:
                state['reason'] = 'deadline'
                break
            time.sleep(0.05)
    except Exception as exc:
        state.update(reason='launch_failed', errors=[str(exc)])
    finally:
        # Only the sessions created here are signalled. Always reap direct children.
        for process in processes:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.terminate()
        grace = time.monotonic() + 2
        while any(process.poll() is None for process in processes) and time.monotonic() < grace:
            time.sleep(0.05)
        for process in processes:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait(timeout=2)
        for log in logs:
            log.close()
    state.update(pids=[p.pid for p in processes], exit_codes=[p.returncode for p in processes],
                 all_reaped=all(p.returncode is not None for p in processes),
                 wall_seconds=time.monotonic() - started)
    return state


def worker(directory, rank):
    spec = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    validate_current_job(spec.get('job_id'))
    validate_current_job(spec['allocation'].get('job_id'))
    receipt = spec['allocation']['ranks'][rank]
    cpu36.validate_receipt(receipt)
    if not set(receipt['selected']) <= set(os.sched_getaffinity(0)):
        raise ValueError('worker CPU boundary exceeds inherited authority')
    os.sched_setaffinity(0, receipt['selected'])
    record = dict(status='FAIL', rank=rank, pid=os.getpid(), run_id=spec['run_id'],
                  world_size=2, host=socket.gethostname(), cpu_receipt=receipt, checkpoints=[])

    def checkpoint(stage):
        record['stage'] = stage
        snapshot = cpu36.snapshot_threads(os.getpid())
        cpu36.validate_snapshot(receipt['selected'], snapshot)
        record['checkpoints'].append(dict(stage=stage, snapshot=snapshot))
        write_json(directory / f'rank{rank}.json', record)

    try:
        checkpoint('before_framework')
        record['environment'] = {key: os.environ.get(key) for key in ENVIRONMENT}
        if record['environment'] != ENVIRONMENT:
            raise ValueError('CPU36 environment mismatch')
        info = backend_info()
        record['runtime'] = info
        if info['status'] != 'AVAILABLE_BUILT_NOT_COMM_TESTED':
            raise RuntimeError('Gloo backend unavailable: ' + json.dumps(info))
        import torch
        import torch.distributed as dist
        record['torch_intraop'] = torch.get_num_threads()
        record['torch_interop'] = torch.get_num_interop_threads()
        if record['torch_intraop'] != 36:
            raise ValueError('actual torch intraop must be36')
        checkpoint('init_process_group')
        dist.init_process_group('gloo', init_method=(directory / 'rendezvous').as_uri(),
                                rank=rank, world_size=2,
                                timeout=timedelta(seconds=spec['pg_timeout']))
        record.update(backend=str(dist.get_backend()), actual_rank=dist.get_rank(),
                      actual_world_size=dist.get_world_size())
        if record['actual_rank'] != rank or record['actual_world_size'] != 2:
            raise ValueError('runtime rank/world identity mismatch')
        identities = [torch.empty(1, dtype=torch.int64) for _ in range(2)]
        checkpoint('all_gather_identity')
        dist.all_gather(identities, torch.tensor([rank], dtype=torch.int64))
        record['identity'] = [int(value.item()) for value in identities]
        if record['identity'] != [0, 1]:
            raise ValueError('gathered rank identity mismatch')
        if spec['case'] == 'crash' and rank == 1:
            checkpoint('injected_crash')
            os._exit(17)
        if spec['case'] == 'watchdog' or (spec['case'] == 'collective-timeout' and rank == 1):
            checkpoint('injected_hang')
            time.sleep(spec['deadline'] * 2)
        value = torch.tensor(BROADCAST if rank == 0 else [-999.0] * 4, dtype=torch.float32)
        checkpoint('broadcast')
        dist.broadcast(value, src=0)
        record.update(broadcast=value.tolist(), shape=list(value.shape), dtype=str(value.dtype))
        if record['broadcast'] != BROADCAST:
            raise ValueError('broadcast result mismatch')
        total = torch.tensor([rank + 1, 2 * (rank + 1), -1, 0.5], dtype=torch.float32)
        checkpoint('all_reduce_sum')
        dist.all_reduce(total, op=dist.ReduceOp.SUM)
        record['total'] = total.tolist()
        if record['total'] != TOTAL:
            raise ValueError('all_reduce SUM result mismatch')
        checkpoint('final_barrier')
        dist.barrier()
        checkpoint('destroy_process_group')
        dist.destroy_process_group()
        checkpoint('finished')
        record['status'] = 'PASS'
        write_json(directory / f'rank{rank}.json', record)
        return 0
    except Exception as exc:
        record['error'] = f'{type(exc).__name__}: {exc}'
        write_json(directory / f'rank{rank}.json', record)
        traceback.print_exc()
        return 1


def run(args):
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    summary = dict(status='FAIL', communication='NOT_PASSED', case=args.case)
    try:
        if not 1 <= args.pg_timeout < args.deadline <= 120:
            raise ValueError('require 1 <= pg-timeout < deadline <= 120 seconds')
        allocation = load_allocation(args.allocation.resolve())
        source = {p.name: cpu36.sha(p) for p in (Path(__file__), Path(cpu36.__file__))}
        spec = dict(run_id=directory.name, case=args.case, pg_timeout=args.pg_timeout,
                    deadline=args.deadline, allocation=allocation, source_sha256=source,
                    tensor_contract=dict(broadcast=BROADCAST, total=TOTAL, tolerance=0,
                                         dtype='torch.float32', shape=[4]),
                    job_id=allocation['job_id'], host=socket.gethostname())
        write_json(directory / 'manifest.json', spec)
        os.sched_setaffinity(0, set().union(*(set(r['selected']) for r in allocation['ranks'])))
        environment = dict(os.environ, **ENVIRONMENT, GLOO_SOCKET_IFNAME='lo', PYTHONDONTWRITEBYTECODE='1')
        commands = [[sys.executable, '-B', str(Path(__file__).resolve()), '_worker',
                     '--output', str(directory), '--rank', str(rank)] for rank in range(2)]
        write_json(directory / 'commands.json', commands)
        state = supervise(commands, directory, args.deadline, environment)
        summary['supervisor'] = state
        if (state['reason'] != 'complete' or state['exit_codes'] != [0, 0]
                or not state['all_reaped']):
            raise ValueError('workers did not complete normally')
        reports = [json.loads((directory / f'rank{rank}.json').read_text(encoding='utf-8'))
                   for rank in range(2)]
        validate_reports(reports, directory.name, state['pids'])
        if source != {p.name: cpu36.sha(p) for p in (Path(__file__), Path(cpu36.__file__))}:
            raise ValueError('probe source changed while running')
        if args.case != 'normal':
            raise ValueError('fault case unexpectedly succeeded')
        summary.update(status='PASS', communication='FIXED_TENSOR_2_RANK_ONLY')
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
    write_json(directory / 'summary.json', summary)
    print(json.dumps(summary))
    return 0 if summary['status'] == 'PASS' else (124 if summary.get('supervisor', {}).get('reason') == 'deadline' else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    env = sub.add_parser('environment')
    env.add_argument('--output', required=True, type=Path)
    launch = sub.add_parser('run')
    launch.add_argument('--output', required=True, type=Path)
    launch.add_argument('--allocation', required=True, type=Path)
    launch.add_argument('--case', choices=['normal', 'crash', 'collective-timeout', 'watchdog'], default='normal')
    launch.add_argument('--pg-timeout', type=int, default=5)
    launch.add_argument('--deadline', type=int, default=30)
    child = sub.add_parser('_worker')
    child.add_argument('--output', required=True, type=Path)
    child.add_argument('--rank', required=True, type=int, choices=[0, 1])
    args = parser.parse_args()
    if args.action == 'environment':
        # Import-only diagnostic; not a CPU36 tensor/operator run.
        os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        if args.output.exists():
            parser.error('environment evidence already exists')
        info = backend_info()
        info['scope'] = 'SINGLE_THREAD_IMPORT_ONLY'
        write_json(args.output, info)
        print(json.dumps(info))
        return 0 if info['status'] == 'AVAILABLE_BUILT_NOT_COMM_TESTED' else 3
    if args.action == '_worker':
        return worker(args.output, args.rank)
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
