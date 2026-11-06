import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
from train_ddp import validate_reports, read_reports, validate_training_allocation


class ResultIdentityChecks(unittest.TestCase):
    def setUp(self):
        self.spec = dict(job_id='current', run_id='run', ready_token='nonce',
                         config_sha256='config', reference_ready_sha256='reference',
                         source_manifest_sha256='source', descriptor_sha256='data')
        self.reports = [dict(self.spec, status='PASS', rank=r, pid=100+r,
                             world_size=2, completed_updates=25, strict_gates_passed=5,
                             local_consumed_frames=800, global_cursor=1600,
                             reference_updates=5 if r == 0 else 0,
                             recovery=dict(status='PASS_NO_EXTRA_UPDATE', extra_updates=0,
                                           model_exact=True, optimizer_exact=True, rng_exact=True,
                                           mask_rng_exact=True, cursor_exact=True, identity_exact=True),
                             steps=[dict(step=s,global_indices=list(range((s-1)*64,s*64)),
                                         local_indices=list(range((s-1)*64+r*32,(s-1)*64+(r+1)*32)),
                                         global_mask_sha256='mask',state_identity={'step':s}) for s in range(1,26)])
                        for r in range(2)]

    def test_complete_exact_pair(self):
        validate_reports(self.reports, self.spec, [100, 101])

    def test_missing_stale_incomplete_and_wrong_identity_rejected(self):
        with self.assertRaises(ValueError):
            validate_reports(self.reports[:1], self.spec, [100, 101])
        for key, bad in [('job_id', 'old'), ('ready_token', 'old'), ('pid', 999),
                         ('config_sha256', 'old'), ('reference_ready_sha256', 'old'),
                         ('source_manifest_sha256', 'old'), ('descriptor_sha256', 'old'),
                         ('rank', 1), ('world_size', 1), ('completed_updates', 24),
                         ('strict_gates_passed', 4), ('local_consumed_frames', 799),
                         ('global_cursor', 1599), ('reference_updates', 6),
                         ('status', 'FAIL'), ('recovery', dict(status='PASS_NO_EXTRA_UPDATE', extra_updates=1))]:
            with self.subTest(key=key):
                rows = copy.deepcopy(self.reports)
                rows[0][key] = bad
                with self.assertRaises(ValueError):
                    validate_reports(rows, self.spec, [100, 101])

    def test_file_reader_rejects_missing_empty_partial(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence') as folder:
            directory = Path(folder)
            for rank in range(2):
                (directory / f'rank{rank}.json').write_text(json.dumps(self.reports[rank]))
            for rank in range(2):
                for invalid in (None, '', '{"status":'):
                    path = directory / f'rank{rank}.json'
                    path.unlink()
                    if invalid is not None:
                        path.write_text(invalid)
                    with self.assertRaises((FileNotFoundError, json.JSONDecodeError)):
                        read_reports(directory, self.spec, [100, 101])
                    path.write_text(json.dumps(self.reports[rank]))

    def test_training_rejects_smaller_allocation(self):
        row = dict(allocated=list(range(38)), selected=list(range(36)), reserved=[36, 37])
        validate_training_allocation(dict(ranks=[row, row]))
        bad = dict(row, allocated=list(range(36)))
        with self.assertRaises(ValueError):
            validate_training_allocation(dict(ranks=[row, bad]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
