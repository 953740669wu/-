"""Real Torch checks execute only if already installed; no installation/fallback."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import socket
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import supervisor


@unittest.skipUnless(importlib.util.find_spec('torch'), 'NOT_RUN: local Torch unavailable')
class TorchTrainingChecks(unittest.TestCase):
    def command(self, folder, rank, mode, init_method=None):
        command = [sys.executable, '-B', str(ROOT / 'tests/torch_checks_worker.py'),
                   '--output', str(folder), '--rank', str(rank), '--mode', mode]
        if init_method is not None:
            command += ['--init-method', init_method]
        return command

    def test_actual_graph_rng_and_input_gradient_math(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            done = subprocess.run(self.command(Path(folder), 0, 'math'), capture_output=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))

    def test_actual_small_two_rank_gloo_ddp(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            folder = Path(folder)
            start = time.monotonic_ns()
            # Windows FileStore stalled locally; retain that failure. Linux uses the training file scheme.
            init_method = (folder / 'tiny_store').as_uri()
            if os.name == 'nt':
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                init_method = f'tcp://127.0.0.1:{port}'
            result = supervisor.supervise([self.command(folder, rank, 'ddp', init_method) for rank in range(2)],
                                           folder, start + 25 * 10**9, start + 28 * 10**9,
                                           os.environ.copy())
            (folder / 'result.json').write_text(json.dumps(result, indent=2))
            shutil.copytree(folder, ROOT / 'evidence' / ('tiny_ddp_' + str(start)))
            self.assertEqual(result['reason'], 'complete')
            self.assertEqual(result['exit_codes'], [0, 0])
            self.assertTrue(result['all_reaped'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
