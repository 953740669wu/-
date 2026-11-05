"""SYNTHETIC ONLY: exercise the protocol with actual child processes, without torch."""
import os
import faulthandler
from pathlib import Path
import sys
import time

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'candidate'))
import runner

spec = runner.read_json(os.environ['SYNTHETIC_MANIFEST'])
rank, mode = int(os.environ['SYNC_RANK']), os.environ['SYNTHETIC_MODE']
print(f'SYNTHETIC ONLY: mode={mode} rank={rank}', flush=True)
assert faulthandler.is_enabled(), 'synthetic supervisor must preserve PYTHONFAULTHANDLER=1'
if rank == 1 and mode == 'failed_rank':
    time.sleep(0.1)
    raise SystemExit(7)
if rank == 1 and mode == 'timeout':
    time.sleep(30)
out = dict(config=spec['config'].copy(), device='cpu', cases=spec['cases'], torch='SYNTHETIC_NO_TORCH')
for belt in spec['belts']:
    out[belt] = dict(peak_mem_GB=1)
    for part, prefix in runner.RATE.items():
        runner.barrier(f'{belt}_{part}')
        rate = 16 if part == 'pre' else 8
        out[belt][f'{prefix}_frames_per_s'] = rate
        out[belt][f'{prefix}_step_s_B32'] = 32 / rate
if rank == 1:
    if mode == 'missing_json':
        raise SystemExit(0)
    if mode == 'partial':
        del out['32_skip4']['decoder_frames_per_s']
    if mode == 'config_mismatch':
        out['config']['ckpt'] = True
runner.publish_result(out, os.environ['SYNTHETIC_OUTPUT'])
path = Path(os.environ['SYNTHETIC_OUTPUT']) / 'reports' / os.environ['TIMING_OUT']
if rank == 1 and mode == 'corrupt_json':
    path.write_text('{broken', encoding='utf-8')
if rank == 1 and mode == 'stale':
    data = runner.read_json(path)
    data['run']['run_id'] = 'old-run'
    runner.atomic_json(path, data)
    os.utime(path, (946684800, 946684800))
print('SYNTHETIC_WORKER_DONE', flush=True)
