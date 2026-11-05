"""Tiny fp32 compile diagnostics. Invoke with -I -S -B and explicit package roots."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
STAGES = ('imports', 'pointwise', 'conv', 'block', 'kml-explain', 'kml')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_source(path, expected):
    if sha256(path) != expected:
        raise RuntimeError('SHA256 mismatch: ' + str(path))


def isolate(roots):
    if not (sys.flags.isolated and sys.flags.no_site):
        raise RuntimeError('Use Python -I -S -B; -s or -I alone does not exclude system site-packages')
    packages = []
    for root in roots:
        path = Path(root).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        if str(path) not in packages:
            packages.append(str(path))
    base = Path(sys.base_prefix).resolve()
    stdlib = [p for p in sys.path if p and Path(p).resolve().is_relative_to(base)
              and 'site-packages' not in Path(p).parts and 'dist-packages' not in Path(p).parts]
    sys.path[:] = packages + stdlib
    sys.dont_write_bytecode = True


def module_identity(name):
    mod = importlib.import_module(name)
    path = getattr(mod, '__file__', None)
    return {'version': str(getattr(mod, '__version__', 'unknown')), 'file': path,
            'sha256': sha256(path) if path else None}


def check_values(torch, actual, expected):
    # Fixed before C2 execution. Diagnostic tolerances do not replace model criteria.
    metrics = []
    for value, ref in zip(actual, expected):
        if value is None or ref is None or value.shape != ref.shape or value.dtype != ref.dtype:
            raise AssertionError('Missing gradient or shape/dtype changed')
        if not torch.isfinite(value).all() or not torch.isfinite(ref).all():
            raise AssertionError('NaN/Inf')
        metrics.append({'max_abs': float((value - ref).abs().max()),
                        'relative_l2': float((value - ref).norm() / ref.norm().clamp_min(1e-12))})
        torch.testing.assert_close(value, ref, rtol=1e-6, atol=1e-6)
    if len(actual) != len(expected):
        raise AssertionError('Missing output/gradient')
    return metrics


def numerical_probe(torch, stage, report):
    torch.manual_seed(0)
    if stage == 'pointwise':
        fn = lambda x: x.sin() * x + x.square()
        args = (torch.randn(32, 32),)
        params = ()
    elif stage == 'conv':
        mod = torch.nn.Conv2d(128, 128, 3, padding=1)
        fn, params = mod, tuple(mod.parameters())
        args = (torch.randn(1, 128, 8, 8),)
    elif stage == 'block':
        # Load original module without invoking its CLI or main(); no model source edits.
        saved = sys.argv[:]
        try:
            sys.argv = ['s4_models.py', str(ROOT), 'probe_no_data_read']
            model = importlib.import_module('s4_models')
        finally:
            sys.argv = saved
        mod = model.Block(128, 128, 512)  # original first decoder block, no attention
        fn, params = mod, tuple(mod.parameters())
        args = (torch.randn(1, 128, 8, 8), torch.randn(1, 512), torch.randn(1, 1, 512))
        report['block_source'] = module_identity('s4_models')
    else:
        ops = importlib.import_module('kml_ops')
        if ops._lib is None or ops.LINEAR_DTYPE != torch.float32:
            raise RuntimeError('Actual fp32 KML required; fallback torch.mm is not a KML probe')
        report['kml_source'] = module_identity('kml_ops')
        fn, params = ops.kml_linear, ()
        args = (torch.randn(128, 512), torch.randn(128, 512), torch.randn(128))
        if args[0].numel() < 2 ** 16:
            raise AssertionError('Would select tiny-GEMM fallback')
        if stage == 'kml-explain':
            result = torch._dynamo.explain(fn)(*(x.requires_grad_() for x in args))
            report['explain'] = {'graph_count': result.graph_count,
                                 'graph_break_count': result.graph_break_count,
                                 'reasons': [str(r) for r in result.break_reasons]}
            report['scope'] = 'FORWARD_GRAPH_DIAGNOSTIC_ONLY; no compiled backward or speed claim'
            return
    report['input_shapes'] = [list(x.shape) for x in args]
    report['precision'] = 'CPU fp32; autocast off; MKLDNN retained'
    report['comparison_order'] = ['output'] + ['input_grad_' + str(i) for i in range(len(args))]
    report['comparison_order'] += ['parameter_grad_' + str(i) for i in range(len(params))]

    def run(call):
        # The unused context argument in the attention-free original Block has no gradient.
        values = tuple(x.detach().clone().requires_grad_(stage != 'block' or i != 2)
                       for i, x in enumerate(args))
        active = tuple(x for x in values if x.requires_grad) + params
        y = call(*values)
        grads = torch.autograd.grad(y, active, torch.ones_like(y), allow_unused=False)
        return (y.detach(),) + tuple(g.detach() for g in grads)

    if stage == 'block':
        report['comparison_order'] = ['output', 'input_grad_x', 'input_grad_t'] + [
            'parameter_grad_' + str(i) for i in range(len(params))]
    start = time.perf_counter()
    expected = run(fn)
    report['eager_first_fwd_bwd_s'] = time.perf_counter() - start
    torch._dynamo.config.suppress_errors = False
    compiled = torch.compile(fn, backend='inductor', fullgraph=True, dynamic=False)
    start = time.perf_counter()
    report['differences'] = check_values(torch, run(compiled), expected)
    report['first_compile_and_fwd_bwd_and_check_s'] = time.perf_counter() - start
    report['warm_diagnostic_fwd_bwd_s'] = []
    for _ in range(2):
        start = time.perf_counter()
        actual = run(compiled)
        report['warm_diagnostic_fwd_bwd_s'].append(time.perf_counter() - start)
        check_values(torch, actual, expected)
    report['scope'] = 'TINY_OPERATOR_ONLY; no optimizer/full-model/performance acceptance'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--package-root', action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args()
    report = {'status': 'FAILED', 'stage': options.stage, 'host': platform.node(),
              'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
              'flags': str(sys.flags), 'rtol': 1e-6, 'atol': 1e-6, 'pid': os.getpid(),
              'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    step = 'isolation'
    try:
        isolate(options.package_root)
        report['sys_path'] = list(sys.path)
        report['environment'] = {k: os.environ.get(k) for k in (
            'PYTHONPATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'KML_BLAS_LIB', 'CXX',
            'OMP_NUM_THREADS', 'OMP_PLACES', 'OMP_PROC_BIND', 'TORCHINDUCTOR_CACHE_DIR',
            'TORCHINDUCTOR_COMPILE_THREADS', 'MAX_JOBS', 'DEVICE', 'AMP', 'KML_LINEAR', 'LINEAR_DTYPE')}
        report['cpu_affinity'] = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
        step = 'source_identity'
        sources = json.loads((ROOT / 'source_identity.json').read_text())['baseline_sha256']
        for name, digest in sources.items():
            verify_source(ROOT / 'baseline' / name, digest)
        report['source_sha256'] = sources
        step = 'torch_import'
        import torch
        report['torch'] = module_identity('torch')
        report['torch_config'] = torch.__config__.show()
        torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '1')))
        report['threads'] = torch.get_num_threads()
        step = 'numpy_import'
        report['numpy'] = module_identity('numpy')
        step = 'environment_identity'
        environment = json.loads((ROOT / 'baseline' / 'environment_expected.json').read_text())
        for name in ('torch', 'numpy'):
            if report[name]['version'] != environment[name]['version'] or (
                    Path(report[name]['file']).resolve() != Path(environment[name]['file']).resolve()):
                raise RuntimeError('Environment drift: ' + name)
        for path, digest in environment['library_sha256'].items():
            verify_source(path, digest)
        report['verified_environment_libraries'] = environment['library_sha256']
        for name in ('torch._dynamo', 'torch._inductor'):
            step = name + '_import'
            report[name] = module_identity(name)
        step = 'toolchain_identity'
        compiler = os.environ.get('CXX') or shutil.which('g++') or shutil.which('c++')
        report['compiler'] = compiler
        if compiler:
            report['compiler_sha256'] = sha256(compiler)
            result = subprocess.run([compiler, '--version'], capture_output=True, text=True, timeout=10)
            report['compiler_version'] = {'returncode': result.returncode, 'stdout': result.stdout,
                                          'stderr': result.stderr}
        else:
            report['compiler_version'] = 'NOT_FOUND; inductor stage will expose actual codegen failure'
        if options.stage != 'imports':
            step = options.stage
            torch._dynamo.config.suppress_errors = False
            numerical_probe(torch, options.stage, report)
        report['status'] = 'PASS_DIAGNOSTIC_ONLY'
    except Exception as error:
        report['blocked_at'] = step
        report['exception'] = {'type': type(error).__name__, 'message': str(error),
                                'traceback': traceback.format_exc()}
        traceback.print_exc()
    finally:
        try:
            paths = set()
            for line in Path('/proc/self/maps').read_text().splitlines():
                fields = line.split()
                if fields and fields[-1].startswith('/') and any(
                        key in fields[-1] for key in ('libomp', 'libgomp', 'libkblas', 'libkml_sgemm', 'libtorch_cpu')):
                    paths.add(fields[-1])
            report['loaded_libraries'] = {p: sha256(p) for p in sorted(paths)}
        except OSError as error:
            report['loaded_libraries_unavailable'] = str(error)
        options.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0 if report['status'] == 'PASS_DIAGNOSTIC_ONLY' else 1


if __name__ == '__main__':
    sys.exit(main())
