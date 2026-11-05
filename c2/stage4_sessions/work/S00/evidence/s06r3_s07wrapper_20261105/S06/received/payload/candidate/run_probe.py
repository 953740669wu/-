"""Bounded sequential launcher; never submits a scheduler job or installs packages."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
STAGES = ('imports', 'pointwise', 'conv', 'block', 'kml-explain', 'kml')


class ParentInterrupted(BaseException):
    def __init__(self, signum):
        self.signum = signum


def parent_signal(signum, frame):
    raise ParentInterrupted(signum)


def cleanup_child(process):
    """Only the session created by run_child; every direct-child wait is bounded."""
    receipt = dict(scope='owned_process_group' if os.name == 'posix' else 'direct_child_only',
                   pid=process.pid, status='FAILED', direct_child_reaped=False, errors=[])
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGTERM)
        elif process.poll() is None:
            process.terminate()
    except ProcessLookupError:
        pass
    except OSError as error:
        receipt['errors'].append(str(error))
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    except Exception as error:
        receipt['errors'].append(str(error))
    # The leader can exit while a compiler descendant ignores TERM. Kill the owned
    # group even after its leader has exited; Windows only guarantees the direct child.
    try:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass
    except OSError as error:
        receipt['errors'].append(str(error))
    try:
        receipt['returncode'] = process.wait(timeout=1.0)
        receipt['direct_child_reaped'] = True
    except Exception as error:
        receipt['errors'].append(str(error))
    if receipt['direct_child_reaped'] and not receipt['errors']:
        receipt['status'] = 'REAPED'
    return receipt


def run_child(command, folder, timeout):
    folder.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
        process, handlers = None, {}
        pending = []
        result = dict(status='ERROR', exit_code=1, command=command)

        def handle_signal(signum, frame):
            # Defer during Popen construction until its owned handle is available.
            # Do not block the OS signal mask, which the child would inherit.
            if process is None:
                pending.append(signum)
            else:
                parent_signal(signum, frame)

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                handlers[sig] = signal.signal(sig, handle_signal)
            process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=os.name == 'posix')
            if pending:
                raise ParentInterrupted(pending[0])
            code = process.wait(timeout=timeout)
            result.update(status='PASS' if code == 0 else 'FAILED', exit_code=code)
        except subprocess.TimeoutExpired:
            result.update(status='TIMEOUT', exit_code=124)
        except ParentInterrupted as error:
            result.update(status='INTERRUPTED', exit_code=128 + error.signum, signal=error.signum)
        except KeyboardInterrupt:
            result.update(status='INTERRUPTED', exit_code=130, signal=int(signal.SIGINT))
        except Exception:
            result['exception'] = traceback.format_exc()
        finally:
            # A second external interrupt must not abort the bounded recovery.
            for sig in handlers:
                signal.signal(sig, signal.SIG_IGN)
            try:
                if process is not None:
                    result['cleanup'] = cleanup_child(process)
                    if result['cleanup']['status'] != 'REAPED':
                        result.update(status='CLEANUP_FAILED', exit_code=1)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
    result['elapsed_s'] = time.monotonic() - start
    (folder / 'execution.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


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
            summary['exit_code'] = result['exit_code']
            break
    else:
        summary['status'] = 'PASS_DIAGNOSTIC_ONLY'
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary['status'] == 'PASS_DIAGNOSTIC_ONLY' else summary.get('exit_code', 1)


if __name__ == '__main__':
    sys.exit(main())
