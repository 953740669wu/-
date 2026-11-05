"""Safety requirements against the frozen original; failures are expected witnesses."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

WORK = Path(__file__).resolve().parents[1]
SOURCE = WORK.parent / 'S00/baseline/c2/opt/run_node16.sh'


class LegacySafety(unittest.TestCase):
    def check_rejected(self, change, rounds=3):
        script = SOURCE.read_text(encoding='utf-8')
        summary = script.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        with tempfile.TemporaryDirectory(dir=WORK / 'tests') as directory:
            root = Path(directory)
            for r in range(1, rounds + 1):
                for d in range(4):
                    data = {b: dict(pretrain_frames_per_s=1, decoder_frames_per_s=1, peak_mem_GB=1)
                            for b in ('16_adjacent', '32_skip4')}
                    (root / f'r{r}_d{d}.json').write_text(json.dumps(data))
            change(root)
            output = io.StringIO()
            with patch.object(sys, 'argv', ['summary', directory, str(rounds)]), contextlib.redirect_stdout(output):
                exec(compile(summary, str(SOURCE), 'exec'), {})
            self.assertNotIn('PASS', output.getvalue(), output.getvalue())

    def test_missing_rank_cannot_pass(self):
        self.check_rejected(lambda root: [p.unlink() for p in root.glob('*_d3.json')])

    def test_stale_results_cannot_pass(self):
        self.check_rejected(lambda root: [os.utime(p, (946684800, 946684800)) for p in root.glob('*.json')])

    def test_failed_rank_with_result_cannot_pass(self):
        self.check_rejected(lambda root: (root / 'r1_d3.exit_code').write_text('7'))

    def test_partial_workload_cannot_pass(self):
        def remove(root):
            for p in root.glob('*_d3.json'):
                data = json.loads(p.read_text())
                del data['32_skip4']['decoder_frames_per_s']
                p.write_text(json.dumps(data))
        self.check_rejected(remove)

    def test_one_round_cannot_pass_stability_gate(self):
        self.check_rejected(lambda root: None, rounds=1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
