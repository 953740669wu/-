#!/bin/bash
# Protocol validation only: no torch, NPZ, KML, HBM or training required.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 -B - <<'PY'
import datetime, hashlib, json, os, pathlib, platform, subprocess, sys

root = pathlib.Path.cwd()
if sys.platform != 'linux':
    raise SystemExit('NOT_RUN: actual Linux required; Windows/MSYS is not Linux acceptance')
directory = root / 'evidence' / ('LINUX_PROTOCOL_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
directory.mkdir(parents=True)
record = dict(scope='LINUX_PROCESS_PROTOCOL_ONLY', host=platform.node(), python=sys.executable,
              python_version=sys.version, platform=platform.platform(), steps=[],
              model_execution='NOT_RUN', cluster_performance='NOT_RUN', status='IN_PROGRESS')
def save():
    (directory / 'RESULT.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
save()
try:
    manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text())
    for relative, digest in manifest.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest, relative
    commands = [
        ['bash', '-n', str(root / 'candidate/run_node16.sh')],
        ['bash', '-n', str(root / 'run_linux_checks.sh')],
        ['bash', '-n', str(root / 'runtime_preflight.sh')],
        [sys.executable, '-B', str(root / 'tests/test_runner.py'),
         'RunnerChecks.test_posix_descendant_cleanup',
         'RunnerChecks.test_real_subprocess_failure_cancels_only_owned_peer',
         'RunnerChecks.test_real_subprocess_timeout_and_success',
         'RunnerChecks.test_spawn_error_is_recorded_and_peer_stopped'],
        [sys.executable, '-B', str(root / 'exercise_local.py')],
    ]
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for number, command in enumerate(commands, 1):
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=45)
        log = directory / f'step{number}.txt'
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        record['steps'].append(dict(command=command, exit_code=result.returncode, log=str(log)))
        save()
        if result.returncode:
            raise RuntimeError(f'step {number} failed; see {log}')
    index = json.loads((root / 'evidence/local_exercise_index.json').read_text())
    assert index['scope'] == 'SYNTHETIC_RUNNER_PROTOCOL_ONLY'
    assert len(index['scenarios']) == 8 and all(x['actual'] == x['expected'] for x in index['scenarios'])
    record.update(status='PASS', synthetic_index=str(root / 'evidence/local_exercise_index.json'))
except Exception as exc:
    record.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
finally:
    record['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
print(directory / 'RESULT.json')
raise SystemExit(0 if record['status'] == 'PASS' else 1)
PY
