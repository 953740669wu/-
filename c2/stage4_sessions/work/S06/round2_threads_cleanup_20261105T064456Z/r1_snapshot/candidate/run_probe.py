"""Bounded sequential launcher; never submits a scheduler job or installs packages."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STAGES = ('imports', 'pointwise', 'conv', 'block', 'kml-explain', 'kml')


def run_child(command, folder, timeout):
    folder.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=os.name == 'posix')
        try:
            code = process.wait(timeout=timeout)
            status = 'PASS' if code == 0 else 'FAILED'
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()
            code, status = 124, 'TIMEOUT'
    return {'status': status, 'exit_code': code, 'elapsed_s': time.monotonic() - start,
            'command': command, 'process_group_cleanup': os.name == 'posix'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--package-root', action='append', default=[])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stage', choices=STAGES + ('all',), default='all')
    options = parser.parse_args()
    out = options.out.resolve()
    if not out.is_relative_to(ROOT):
        parser.error('--out must stay under this S06 directory')
    out.mkdir(parents=True, exist_ok=False)  # never mix a previous run with fresh results
    cache = out / 'cache'
    cache.mkdir()
    os.environ.update(TORCHINDUCTOR_CACHE_DIR=str(cache / 'inductor'),
                      TRITON_CACHE_DIR=str(cache / 'triton'), TMPDIR=str(cache),
                      TMP=str(cache), TEMP=str(cache), XDG_CACHE_HOME=str(cache / 'xdg'),
                      TORCHINDUCTOR_COMPILE_THREADS='1', MAX_JOBS='1',
                      PYTHONDONTWRITEBYTECODE='1')
    # Exact fp32 path of the current CPU decoder. No HBM or precision experiments.
    os.environ.update(DEVICE='cpu', AMP='fp32', LINEAR_DTYPE='fp32', KML_LINEAR='1',
                      KML_CONV='0', MKLDNN='1', COMPILE='0', CKPT='0', CHANNELS_LAST='0')
    stages = STAGES if options.stage == 'all' else (options.stage,)
    summary = {'scope': 'PREP_ONLY', 'status': 'RUNNING', 'stages': [],
               'not_run': list(stages), 'budget_s': 600, 'full_model': 'NOT_RUN'}
    deadline = time.monotonic() + 600
    for stage in stages:
        folder = out / stage
        command = [options.python, '-I', '-S', '-B', str(ROOT / 'candidate' / 'probe.py'),
                   '--stage', stage, '--out', str(folder / 'result.json')]
        for path in [str(ROOT / 'baseline')] + options.package_root:
            command.extend(['--package-root', path])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            summary['status'] = 'TIMEOUT'
            break
        result = run_child(command, folder, min(120, remaining))
        result['stage'] = stage
        summary['stages'].append(result)
        summary['not_run'].remove(stage)
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        if result['status'] != 'PASS':
            summary['status'] = result['status']
            break
    else:
        summary['status'] = 'PASS_DIAGNOSTIC_ONLY'
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary['status'] == 'PASS_DIAGNOSTIC_ONLY' else 1


if __name__ == '__main__':
    sys.exit(main())
