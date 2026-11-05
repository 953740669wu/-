"""Persist real-child protocol evidence. No Bash, torch, NUMA or C2 performance claims."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK / 'candidate'))
import runner

start = datetime.now(timezone.utc)
root = WORK / 'evidence' / ('SYNTHETIC_' + start.strftime('%Y%m%dT%H%M%S%fZ'))
root.mkdir()
outcomes = []
for mode in ['complete', 'failed_rank', 'timeout', 'missing_json', 'corrupt_json', 'stale', 'partial', 'config_mismatch']:
    directory = root / 'reports' / mode
    directory.mkdir(parents=True)
    spec = dict(run_id=mode, host=socket.gethostname(), domains=[0, 1], rounds=3,
                input_protocol='SYNTHETIC_RUNNER_PROTOCOL_ONLY',
                belts=['16_adjacent', '32_skip4'], parts=['pre', 'dec'], device='cpu',
                cases=['SYNTHETIC_CASE_A', 'SYNTHETIC_CASE_B'],
                config=dict(amp='fp32', batch=32, channels_last=False, compile=False, reps=5,
                            kml_conv=False, kml_blas='SYNTHETIC_LIBRARY', ckpt=False,
                            kml_linear=True, linear_dtype='fp32'))
    runner.atomic_json(directory / 'manifest.json', spec)
    elapsed_start = time.monotonic()
    for r in range(1, 4):
        sync = directory / f'sync_r{r}'
        sync.mkdir()
        commands, environments = {}, {}
        for d in spec['domains']:
            env = os.environ.copy()
            env.update(RUN_ID=mode, RUN_ROUND=str(r), SYNC_DIR=str(sync), SYNC_N='2', SYNC_RANKS='0,1',
                       INPUT_PROTOCOL=spec['input_protocol'], PYTHONFAULTHANDLER='1',
                       SYNC_RANK=str(d), SYNC_TIMEOUT='3', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1',
                       TIMING_OUT=f'{mode}/r{r}_d{d}.json', SYNTHETIC_MODE=mode,
                       SYNTHETIC_MANIFEST=str(directory / 'manifest.json'), SYNTHETIC_OUTPUT=str(root))
            commands[d] = [sys.executable, '-B', str(WORK / 'tests/synthetic_worker.py')]
            environments[d] = env
        states = runner.supervise(commands, environments, sync, 0.6 if mode == 'timeout' else 5)
        for d, state in states.items():
            runner.atomic_json(directory / f'r{r}_d{d}.status.json', state)
        if any(state['exit_code'] != 0 for state in states.values()):
            break
        intermediate = runner.summarize(directory, completed_rounds=r)
        runner.atomic_json(directory / f'round{r}_integrity.json', intermediate)
        if intermediate['status'] == 'FAIL':
            break
    result = runner.summarize(directory)
    runner.atomic_json(directory / 'summary.json', result)
    cli = subprocess.run([sys.executable, '-B', str(WORK / 'candidate/runner.py'), '--summarize', str(directory)],
                         capture_output=True, text=True, timeout=5)
    (directory / 'summary_cli.txt').write_text(cli.stdout + cli.stderr, encoding='utf-8')
    expected = 'PASS' if mode == 'complete' else 'FAIL'
    assert result['status'] == expected, (mode, result)
    assert cli.returncode == (0 if mode == 'complete' else 1), (mode, cli.returncode)
    outcomes.append(dict(mode=mode, expected=expected, actual=result['status'], cli_exit=cli.returncode,
                         elapsed_s=time.monotonic() - elapsed_start, directory=str(directory)))
index = dict(scope='SYNTHETIC_RUNNER_PROTOCOL_ONLY', started_utc=start.isoformat(),
             finished_utc=datetime.now(timezone.utc).isoformat(), scenarios=outcomes,
             bash_executed=False, cluster_executed=False, numerical_validation=False, node_hours=0)
runner.atomic_json(root / 'INDEX.json', index)
runner.atomic_json(WORK / 'evidence/local_exercise_index.json', index)
print(root)
for outcome in outcomes:
    print(outcome['mode'], outcome['actual'], 'CLI exit', outcome['cli_exit'])
