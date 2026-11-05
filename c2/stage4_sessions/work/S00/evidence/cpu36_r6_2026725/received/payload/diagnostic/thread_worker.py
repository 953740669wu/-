"""Small native operators only. No EIT model, data, optimizer, timing benchmark or HBM."""
import ctypes
import importlib
import hashlib
import os
from pathlib import Path
import re
import sys
import time

from cpu36_contract import atomic_json, snapshot_threads

directory, receipt_path = Path(sys.argv[1]), Path(sys.argv[2])
import json
receipt = json.loads(receipt_path.read_text())
record = dict(pid=os.getpid(), selected=receipt['selected'], stages=[], model_executed=False)
keys = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'OMP_PROC_BIND', 'OMP_PLACES',
        'OMP_THREAD_LIMIT', 'OMP_DYNAMIC', 'MKL_DYNAMIC', 'GOMP_CPU_AFFINITY', 'KMP_AFFINITY',
        'KMP_HW_SUBSET', 'OMP_WAIT_POLICY', 'PYTHONPATH', 'LD_PRELOAD', 'KML_BLAS_LIB')
record['environment'] = {key: os.environ.get(key) for key in keys}
library_hashes = {}


def runtime_info():
    libraries = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                        if re.search(r'libomp|libgomp|openblas|kblas|shim', line, re.I) and line.split()[-1].startswith('/')})
    result = {}
    for path in libraries:
        entry = {}
        try:
            if path not in library_hashes:
                digest = hashlib.sha256()
                with open(path, 'rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                library_hashes[path] = digest.hexdigest()
            entry['sha256'] = library_hashes[path]
            # Only query already-loaded libraries; never introduce another runtime for the probe.
            lib = ctypes.CDLL(path, mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)
            for name in ('omp_get_max_threads', 'omp_get_num_threads', 'omp_get_dynamic', 'omp_get_proc_bind',
                         'omp_get_num_places', 'openblas_get_num_threads', 'openblas_get_num_threads64_',
                         'openblas_get_num_threads_64_'):
                if hasattr(lib, name):
                    fn = getattr(lib, name)
                    fn.argtypes, fn.restype = [], ctypes.c_int
                    entry[name] = fn()
        except (OSError, AttributeError) as exc:
            entry['query_error'] = str(exc)
        result[path] = entry
    return result


def stage(name):
    atomic_json(directory / 'phase.json', dict(name=name, monotonic=time.monotonic()))
    data = dict(name=name, threads=snapshot_threads(os.getpid()))
    if 'torch' in globals():
        data.update(torch_intraop=torch.get_num_threads(), torch_interop=torch.get_num_interop_threads(),
                    parallel_info=torch.__config__.parallel_info(), runtimes=runtime_info())
    record['stages'].append(data)
    atomic_json(directory / 'worker.json', record)


def exercise(name, fn):
    atomic_json(directory / 'phase.json', dict(name=name, monotonic=time.monotonic()))
    start, count = time.monotonic(), 0
    while time.monotonic() - start < 0.5:
        fn()
        count += 1
    record.setdefault('operator_calls', {})[name] = count  # not a throughput metric
    stage('after_' + name)


try:
    stage('before_import')
    if not set(os.sched_getaffinity(0)) <= set(receipt['selected']):
        raise RuntimeError('worker escaped selected36 before framework import')
    import torch
    stage('after_torch_import')
    record['torch'] = dict(version=torch.__version__, path=torch.__file__)
    # Do not call torch.set_num_threads: it would conceal environment precedence.
    a = torch.ones((2048, 2048), dtype=torch.float32)
    output = torch.empty_like(a)
    exercise('torch_elementwise', lambda: torch.add(a, a, out=output))
    import numpy as np
    record['numpy'] = dict(version=np.__version__, path=np.__file__)
    n = np.ones((512, 512), dtype=np.float32)
    dest = np.empty_like(n)
    exercise('numpy_dot', lambda: np.dot(n, n, out=dest))
    ops = importlib.import_module('kml_ops')
    record['kml_ops_path'] = ops.__file__
    if getattr(ops, '_lib', None) is None:
        raise RuntimeError('KML is not actually loaded; do not substitute native torch.mm')
    x = torch.ones((1024, 1024), dtype=torch.float32)
    y = torch.empty_like(x)
    atomic_json(directory / 'phase.json', dict(name='kml_first_call', monotonic=time.monotonic()))
    ops.gemm(x, x, out=y)
    stage('after_kml_first_call')
    exercise('kml_repeated', lambda: ops.gemm(x, x, out=y))
    record['status'] = 'OPERATORS_COMPLETED_NOT_MODEL_ACCEPTANCE'
except Exception as exc:
    record.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
finally:
    atomic_json(directory / 'worker.json', record)
raise SystemExit(0 if record['status'] != 'FAIL' else 1)
