"""Actual import/input/library preflight. Does not execute model forward/backward or HBM."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import sys
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
if sys.platform != 'linux':
    raise SystemExit('NOT_RUN: Linux required')
if not os.environ.get('S01_JOB_ID') or os.environ.get('S01_COMPUTE_HOST') != socket.gethostname():
    raise SystemExit('NOT_RUN: supply the S00-allocated job ID and exact compute hostname')
if 'login' in socket.gethostname().lower():
    raise SystemExit('NOT_RUN: use the allocated compute node')
directory = root / 'evidence' / ('RUNTIME_PREFLIGHT_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
directory.mkdir(parents=True)
out = dict(scope='ACTUAL_IMPORT_AND_INPUT_IDENTITY_ONLY', status='IN_PROGRESS',
           host=socket.gethostname(), declared_job_id=os.environ['S01_JOB_ID'],
           python=sys.executable, python_version=sys.version, platform=platform.platform(),
           model_forward_backward='NOT_RUN', cluster_performance='NOT_RUN')
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
try:
    manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text())
    assert Path(os.environ['S01_RUN']).resolve() == root
    for relative, digest in manifest.items():
        assert sha(root / relative) == digest, relative
    out['source_sha256'] = manifest
    out['cpu_affinity'] = sorted(os.sched_getaffinity(0))
    out['allowed_sets'] = [line for line in Path('/proc/self/status').read_text().splitlines()
                           if line.startswith(('Cpus_allowed_list:', 'Mems_allowed_list:'))]
    keys = ('PYTHONPATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'KML_BLAS_LIB', 'OMP_PLACES',
            'OMP_PROC_BIND', 'OMP_NUM_THREADS', 'DEVICE', 'AMP', 'KML_LINEAR', 'LINEAR_DTYPE')
    out['environment'] = {key: os.environ.get(key) for key in keys}
    sys.path.insert(0, str(root / 'candidate'))
    import runner
    paths = {case: root / f'output/cases/{case}/frames.npz' for case in ('s0322p0', 's0322p1')}
    runner.verify_legacy_inputs(paths, runner.read_json(root / 'candidate/legacy_inputs.json'))
    out['input_protocol'] = 'LEGACY_TIMING_ONLY'
    out['inputs'] = {case: dict(path=str(path), sha256=sha(path)) for case, path in paths.items()}
    for name in ('numpy', 'torch', 'kml_ops'):
        module = importlib.import_module(name)
        out[name] = dict(version=getattr(module, '__version__', None), path=str(Path(module.__file__).resolve()))
    sys.argv = [str(root / 'candidate/s4_models.py'), str(root / 'output'), 's0322p0,s0322p1']
    model = importlib.import_module('s4_models')
    assert Path(model.__file__).resolve() == root / 'candidate/s4_models.py'
    out['model_import'] = str(Path(model.__file__).resolve())
    mapped = sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                     if re.search(r'kml|blas|libomp|libgomp|hbm', line, re.I) and line.split()[-1].startswith('/')})
    out['loaded_libraries'] = {path: sha(path) for path in mapped if Path(path).is_file()}
    for path in [root / 'lib/libkml_sgemm_shim.so', Path(os.environ['KML_BLAS_LIB'])]:
        assert str(path.resolve()) in {str(Path(p).resolve()) for p in mapped}, f'not actually loaded: {path}'
    out.update(status='PASS', limitation='Imports and legacy file identity only; OMP ABI pairing and actual training require further review')
except Exception as exc:
    out.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
finally:
    out['finished_utc'] = datetime.now(timezone.utc).isoformat()
    result = directory / 'RESULT.json'
    result.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(result)
raise SystemExit(0 if out['status'] == 'PASS' else 1)
