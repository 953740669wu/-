"""Five-minute, one-CPU compute-node prerequisite probe; no model or training."""
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

H = Path('/home/share/songzhenlong/eitfm')


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return 'UNAVAILABLE: ' + str(error)


def resources():
    status = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
              for line in read('/proc/self/status').splitlines() if ':' in line}
    memory = {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
              for line in read('/proc/meminfo').splitlines() if ':' in line}
    groups, files = read('/proc/self/cgroup'), {}
    for line in groups.splitlines():
        parts = line.split(':', 2)
        if len(parts) != 3:
            continue
        controllers, relative = parts[1], parts[2].lstrip('/')
        bases = ['/sys/fs/cgroup'] if not controllers else [
            '/sys/fs/cgroup/' + controller for controller in controllers.split(',')]
        if 'cpu' in controllers.split(','):
            bases.append('/sys/fs/cgroup/cpu,cpuacct')
        for base in bases:
            folder = Path(base) / relative
            for key in ('memory.max', 'memory.current', 'memory.limit_in_bytes',
                        'memory.usage_in_bytes', 'memory.soft_limit_in_bytes',
                        'cpu.max', 'cpu.cfs_quota_us', 'cpu.cfs_period_us',
                        'cpuset.cpus', 'cpuset.mems', 'cpuset.cpus.effective', 'cpuset.mems.effective'):
                path = folder / key
                try:
                    files[str(path)] = path.read_text().strip()
                except FileNotFoundError:
                    continue
                except OSError as error:
                    files[str(path)] = 'UNAVAILABLE: ' + str(error)
    return dict(affinity=sorted(os.sched_getaffinity(0)), host_cpu_count=os.cpu_count(),
        proc_status={k: status.get(k) for k in ('Cpus_allowed_list', 'Mems_allowed_list', 'VmRSS', 'Threads')},
        host_memory={k: memory.get(k) for k in ('MemTotal', 'MemAvailable', 'SwapFree', 'HugePages_Total', 'HugePages_Free', 'Hugepagesize')},
        host_memory_is_not_job_budget=True, cgroup=groups, cgroup_files=files)


def worker():
    import numpy as np
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    x = torch.tensor([1., 2.], requires_grad=True)
    x.square().sum().backward()
    assert torch.equal(x.grad, torch.tensor([2., 4.]))
    bridge = {}
    try:
        value = torch.from_numpy(np.arange(4, dtype=np.float32))
        bridge = dict(status='PASS', values=value.tolist())
    except Exception as error:
        bridge = dict(status='FAIL', error=repr(error))
    paths = sorted({line.split()[-1] for line in read('/proc/self/maps').splitlines()
                    if '/' in line and any(token in line for token in
                    ('/torch', '/numpy', 'libomp', 'libgomp', 'libopenblas', 'libkblas', 'libkml_sgemm'))})
    print(json.dumps(dict(status='PASS_ACTUAL_IMPORT_AND_TINY_AUTOGRAD', host=platform.node(),
        executable=sys.executable, executable_realpath=os.path.realpath(sys.executable),
        python=sys.version, sys_path=sys.path, torch_version=torch.__version__, torch_file=torch.__file__,
        numpy_version=np.__version__, numpy_file=np.__file__, torch_config=torch.__config__.show(),
        threads=torch.get_num_threads(), interop_threads=torch.get_num_interop_threads(),
        numpy_bridge=bridge, loaded_paths=paths, resources=resources())))


def main():
    root = Path(sys.argv[1]).resolve()
    root.relative_to(Path('/home/share/dengqingtian/opt/stage4_sessions/S00').resolve())
    started = time.monotonic()
    out = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        host=platform.node(), user=os.environ.get('USER'), root=str(root), resources=resources(),
        request=dict(queue='q_hpcai', cpu=1, memory_argument='4096MB', runtime_limit_s=300),
        scheduler_env={k: os.environ[k] for k in ('CCS_JOB_ID', 'CCS_JOBID', 'JOB_ID', 'BATCH_JOB_ID') if k in os.environ},
        attempts=[], model_started=False, hbm_started=False)
    if out['host'].startswith('login'):
        out['status'] = 'REFUSED_LOGIN_NODE'
    else:
        variants = [('/usr/bin/python3', 'torch_kml'),
                    (str(H / 'sw/venv/bin/python'), 'torch_kml'),
                    ('/usr/bin/python3', 'torch')]
        for interpreter, tree in variants:
            if not Path(interpreter).exists():
                continue
            env = os.environ.copy()
            env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
                PYTHONPATH=str(H / ('sw/' + tree)), OMP_NUM_THREADS='1',
                OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
            env.pop('LD_PRELOAD', None)
            env.pop('KML_BLAS_LIB', None)
            if tree == 'torch_kml':
                k = '/opt/HPCKit/kml-lib/sme/kblas/multi'
                env['LD_LIBRARY_PATH'] = ':'.join([k, '/opt/HPCKit/kml-lib', '/opt/HPCKit/bisheng-lib'])
                shim = H / 'sw/kml_shim/libkml_sgemm_shim.so'
                if shim.is_file():
                    env['LD_PRELOAD'] = str(shim)
                env['KML_BLAS_LIB'] = k + '/libkblas.so'
            command = [interpreter, '-B', str(Path(__file__).resolve()), '--worker']
            attempt = dict(interpreter=interpreter, tree=tree, command=command,
                environment={k: env[k] for k in ('PYTHONPATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'KML_BLAS_LIB',
                    'PYTHONNOUSERSITE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS') if k in env})
            try:
                p = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, timeout=55)
                attempt.update(exit_code=p.returncode, stderr=p.stderr, stdout=p.stdout)
                if p.returncode == 0:
                    attempt['result'] = json.loads(p.stdout.strip().splitlines()[-1])
            except subprocess.TimeoutExpired:
                attempt['status'] = 'IMPORT_TIMEOUT_55S'
            out['attempts'].append(attempt)
            if attempt.get('exit_code') == 0:
                out['status'] = 'PASS_COMPUTE_ACTUAL_IMPORTS'
                out['selected_attempt'] = len(out['attempts']) - 1
                break
        else:
            out['status'] = 'NO_VERIFIED_TORCH_NUMPY_ENVIRONMENT'
    out.update(finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               elapsed_s=time.monotonic() - started)
    (root / 'compute_environment.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(dict(status=out['status'], host=out['host'], root=str(root), elapsed_s=out['elapsed_s'])))
    return 0 if out['status'] == 'PASS_COMPUTE_ACTUAL_IMPORTS' else 2


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        sys.exit(main())
