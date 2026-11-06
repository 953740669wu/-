"""LOCAL_FIXTURE: report accounting, no DDP/model/data execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from summarize_ddp import IDENTITY, accounting, analyze, paired_steps


class ReportChecks(unittest.TestCase):
    def test_failed_gate_keeps_executed_updates(self):
        ranks = [dict(completed_updates=1, reference_updates=1, strict_gates_passed=0),
                 dict(completed_updates=1, reference_updates=0, strict_gates_passed=0)]
        value = accounting(ranks, [[], []], dict(status='FAIL'))
        self.assertEqual(value['rank_optimizer_updates_reported'], [1, 1])
        self.assertEqual(value['physical_updates_including_reference_reported'], 3)
        self.assertIsNone(value['global_updates_parent_verified'])
        self.assertEqual(value['fully_logged_step_counts'], [0, 0])
        self.assertEqual(value['post_gate_updates_stage'], 'NOT_RUN')

    def test_missing_rank_remains_unknown(self):
        value = accounting([dict(completed_updates=1, reference_updates=0), {}], [[], []], {})
        self.assertIsNone(value['physical_rank_updates_reported'])
        self.assertIsNone(value['physical_updates_including_reference_reported'])

    def test_complete_accounting_not_reference_as_new_frames(self):
        ranks = [dict(completed_updates=25, reference_updates=5, strict_gates_passed=5),
                 dict(completed_updates=25, reference_updates=0, strict_gates_passed=5)]
        value = accounting(ranks, [[{}]*25, [{}]*25], dict(global_updates=25))
        self.assertEqual(value['physical_rank_updates_reported'], 50)
        self.assertEqual(value['reference_updates_reported'], 5)
        self.assertEqual(value['physical_updates_including_reference_reported'], 55)

    def test_duplicate_overlap_and_state_mismatch_rejected(self):
        common = dict(step=1, global_batch=64, local_batch=32, global_indices=list(range(64)),
            global_frame_ids_sha256=hashlib.sha256(json.dumps([dict(unit='u', pair_index=i) for i in range(64)], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            global_mask_sha256='a'*64, global_counts=[100, 16384], losses=dict(total=3., voltage=1., coarse=2.),
            state_identity=dict(model_sha256='same', adamw_sha256='same'))
        a = dict(common, local_indices=list(range(32)), frame_ids=[dict(unit='u', pair_index=i) for i in range(32)], local_masked=40, train_step_seconds=1.)
        b = dict(common, local_indices=list(range(32,64)), frame_ids=[dict(unit='u', pair_index=i) for i in range(32,64)], local_masked=60, train_step_seconds=2.)
        value = paired_steps([[a], [b]])
        self.assertEqual(value['matched_state_steps'], 1)
        b['local_indices'] = list(range(32))
        b['state_identity'] = dict(model_sha256='different')
        value = paired_steps([[a], [b]])
        self.assertTrue(value['issues'])
        self.assertEqual(value['matched_state_steps'], 0)

    def test_read_missing_logs_and_old_protocol_never_complete(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            identity = {k: 'LOCAL_FIXTURE' for k in IDENTITY}
            identity['job_id'] = 'fixture_job'
            files = dict(manifest=dict(identity, config=dict(protocol='REAL_CORPUS_PILOT_V1')),
                         participants=dict(pids=[101, 102]), summary=dict(status='FAIL'))
            for rank in (0, 1):
                files[f'rank{rank}'] = dict(identity, rank=rank, pid=101+rank, status='FAIL',
                    completed_updates=1, reference_updates=1-rank, strict_gates_passed=0,
                    steps=[], recovery=dict(status='NOT_RUN'))
            for name, value in files.items():
                (root/(name+'.json')).write_text(json.dumps(value), encoding='utf-8')
            value = analyze(root, 'fixture_job')
            self.assertTrue(any('protocol' in x for x in value['issues']))
            self.assertTrue(value['missing_files'])
            self.assertEqual(value['accounting']['physical_updates_including_reference_reported'], 3)
            self.assertEqual(value['accounting']['post_gate_updates_stage'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main(verbosity=2)
