"""Memory gate policy only; mocked result is never a scientific PASS."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memory_gate


class MemoryGateTests(unittest.TestCase):
    def setUp(self):
        self.frozen = dict(sha256='frozen-file', identity={'initial': 'frozen-weights'})
        self.sources = {'candidate/full_batch_step.py': 'this-source'}
        self.data = dict(status='PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY', mode='checkpoint_strict',
            comparison_failures=0, failures=[], metrics=[dict(passed=True)] * 1063,
            config=dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
                        reference_checkpoint=False, candidate_checkpoint=True,
                        history='fresh', precision='fp32', threads=36),
            case_file_sha256=self.frozen['sha256'], case_identity=self.frozen['identity'],
            source_sha256=self.sources, runtime=dict(backend='kml', kml_gemm_calls=1),
            kml_calls_by_side=dict(reference=1, candidate=1),
            cpu36=dict(errors=[], receipt={}, checkpoints=[dict(name=name) for name in
                ['before_framework', 'after_framework', 'after_backend', 'before_reference',
                 'after_reference', 'after_candidate', 'publish']]))

    def test_candidate_pass_gate_and_all_checkpoints(self):
        with patch.object(memory_gate.cpu36_guard, 'validate_checkpoint') as check:
            memory_gate.validate(self.data, self.frozen, self.sources)
        self.assertEqual(check.call_count, 7)

    def test_r5_fail_control_or_wrong_source_cannot_unlock_memory(self):
        for key, value in [('status', 'FAIL_ORIGINAL_CRITERIA'), ('mode', 'strict'),
                           ('source_sha256', {'candidate/full_batch_step.py': 'old'}),
                           ('case_file_sha256', 'wrong')]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.data); data[key] = value
                with self.assertRaises(ValueError):
                    memory_gate.validate(data, self.frozen, self.sources)

    def test_missing_metrics_thread_or_actual_kml_evidence_rejected(self):
        for change in [dict(metrics=[]), dict(runtime=dict(backend='native')),
                       dict(kml_calls_by_side=dict(reference=1, candidate=0)),
                       dict(cpu36=dict(errors=['Torch1'], checkpoints=[], receipt={}))]:
            with self.subTest(change=change):
                data = copy.deepcopy(self.data); data.update(change)
                with self.assertRaises(ValueError):
                    memory_gate.validate(data, self.frozen, self.sources)


if __name__ == '__main__':
    unittest.main(verbosity=2)
