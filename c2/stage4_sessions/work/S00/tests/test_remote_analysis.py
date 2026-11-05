"""Check historical completeness rules against the saved S00 evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK))
from analyze_remote_results import analyze_round, build_tables


class RemoteAnalysisChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads((WORK / 'evidence/remote_details.json').read_text(encoding='utf-8'))

    def test_missing_domain_invalidates_all_four_workloads(self):
        files = self.evidence['reports']['node16_sync_kmlfp32']['files']
        for belt in ('16_adjacent', '32_skip4'):
            for part in ('pre', 'dec'):
                row = analyze_round(files, 2, 16, belt, part)
                self.assertEqual(row['missing_domains'], [4])
                self.assertFalse(row['payload_complete'])
                self.assertIsNone(row['complete_node_sum_fps'])
                self.assertIsNone(row['conservative_fps'])

    def test_inconsistent_step_rate_is_rejected(self):
        files = copy.deepcopy(self.evidence['reports']['node16_b32_membind']['files'])
        files[0]['data']['16_adjacent']['pretrain_frames_per_s'] *= 2
        row = analyze_round(files, 1, 16, '16_adjacent', 'pre')
        self.assertFalse(row['payload_complete'])
        self.assertTrue(any('step/rate' in reason for reason in row['issues']))

    def test_three_round_requirement_and_slow_domain_metric(self):
        _, _, stability = build_tables(self.evidence)
        hbm = next(s for s in stability if s['tag'] == 'node16_b32_hbm' and s['belt'] == '16_adjacent' and s['part'] == 'pre')
        self.assertEqual(hbm['complete_payload_rounds'], 2)
        self.assertFalse(hbm['three_round_payload_spread_pass'])
        files = self.evidence['reports']['node16_b32_membind']['files']
        row = analyze_round(files, 2, 16, '32_skip4', 'pre')
        self.assertGreater(row['complete_node_sum_fps'], 20)
        self.assertLess(row['conservative_fps'], 3)

    def test_input_images_match_32_belt_but_not_16(self):
        context = json.loads((WORK / 'evidence/remote_context.json').read_text(encoding='utf-8'))
        for data in context['provenance'].values():
            actual = data['demo_images']['payload_sha256']
            self.assertEqual(actual, data['sources']['32_skip4']['images']['payload_sha256'])
            self.assertNotEqual(actual, data['sources']['16_adjacent']['images']['payload_sha256'])

    def test_current_launcher_keeps_the_original_summarizer(self):
        def summary(text):
            return text.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        old = (WORK / 'baseline/c2/opt/run_node16.sh').read_text(encoding='utf-8')
        for name in ('run_node16.sh', 'run_node16_latest.sh'):
            current = (WORK / ('evidence/remote_sources/' + name)).read_text(encoding='utf-8')
            self.assertEqual(summary(old), summary(current), name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
