"""Stdlib-only checks; these do not execute torch or establish numerical equivalence."""
import ast
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WORK = Path(__file__).resolve().parents[1]
ROOT = WORK.parents[3]


class CapturedAngles:
    def __init__(self, values):
        self.values = values

    def __mul__(self, _):
        return self

    __truediv__ = __mul__


class BaselineChecks(unittest.TestCase):
    def test_frozen_copies_are_byte_identical(self):
        rows = json.loads((WORK / 'evidence/baseline_manifest.json').read_text())
        self.assertGreaterEqual(len(rows), 15)
        for row in rows:
            src = ROOT / row['source']
            dst = WORK / row['copy']
            self.assertEqual(src.read_bytes(), dst.read_bytes(), row['source'])
            self.assertEqual(hashlib.sha256(dst.read_bytes()).hexdigest(), row['sha256'])

    def test_protocol_matches_forward_order(self):
        # Execute only the two protocol functions using tiny tensor/array capture stubs.
        class Torch:
            float32 = 'float32'
            tensor = staticmethod(lambda values, **_: CapturedAngles(values))
        class Numpy:
            array = staticmethod(lambda values: values)
        functions = []
        for file, name in [('s4_models.py', 'protocol_angles'), ('s3_forward.py', 'protocol')]:
            node = next(n for n in ast.parse((ROOT / file).read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == name)
            scope = dict(torch=Torch, np=Numpy, math=math)
            exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), scope)
            functions.append(scope[name])
        for size, skip, count in [(16, 1, 208), (32, 5, 928)]:
            angles = functions[0](size, skip).values
            drives, pairs = functions[1](size, skip)
            expected = [list(drives[d] + drives[m]) for d, m in pairs]
            self.assertEqual(angles, expected)
            self.assertEqual(len(angles), count)
        self.assertIn("'32_skip4': (32, 5)", (ROOT / 's4_models.py').read_text())

    def test_existing_summary_can_pass_missing_and_stale_domains(self):
        # A behavioral witness for S01, not a replacement summarizer.
        script = (ROOT / 'c2/opt/run_node16.sh').read_text()
        summary = script.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        with tempfile.TemporaryDirectory(dir=WORK / 'tests') as directory:
            data = {belt: dict(pretrain_frames_per_s=1, decoder_frames_per_s=1, peak_mem_GB=1)
                    for belt in ('16_adjacent', '32_skip4')}
            for round_id in range(1, 4):
                path = Path(directory) / f'r{round_id}_d0.json'
                path.write_text(json.dumps(data))  # one domain only, no log or exit status
                os.utime(path, (946684800, 946684800))  # stale: 2000-01-01 UTC
            output = io.StringIO()
            with patch.object(sys, 'argv', ['summary', directory, '3']), contextlib.redirect_stdout(output):
                exec(compile(summary, 'original_summary', 'exec'), {})
            self.assertEqual(output.getvalue().count('PASS'), 4)
            self.assertIn('domains  1', output.getvalue())
            (WORK / 'evidence/legacy_summary_witness.txt').write_text(
                'SYNTHETIC BUG WITNESS ONLY: 1/16 domains, stale JSON, no process or logs.\n'
                + output.getvalue(), encoding='utf-8')

    def test_isolated_launcher_paths(self):
        text = (WORK / 'candidate/run_node16_isolated.sh').read_text()
        self.assertIn('S00_RUN=${S00_RUN:?', text)
        self.assertIn('O=$S00_RUN/output', text)
        self.assertIn('PYTHONPATH=$H/sw/torch_kml:$S00_CODE', text)
        for unsafe in ('$H/opt/code', '$H/opt/s4', '$H/sw/hbm_alloc', '$H/sw/kml_shim'):
            self.assertNotIn(unsafe, text)
        self.assertIn('python3 $S00_CODE/s4_models.py', text)

    def test_explicit_configurations(self):
        configs = json.loads((WORK / 'baseline_configs.json').read_text())
        self.assertEqual(len(configs), 3)
        for config in configs.values():
            env = config['env']
            self.assertEqual(env['AMP'], 'fp32')
            self.assertEqual(env['DEVICE'], 'cpu')
            self.assertEqual(env['CKPT'], '0')
            self.assertEqual(env['REPS'], '5')
            self.assertEqual(env['ROUNDS'], '3')
            self.assertEqual(env['BELTS'], '16_adjacent,32_skip4')
            self.assertEqual(env['PARTS'], 'pre,dec')


if __name__ == '__main__':
    unittest.main(verbosity=2)
