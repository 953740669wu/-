"""LOCAL_FIXTURE only: no corpus, model, checkpoint or cluster access."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import summarize


def fixture():
    flags = dict(protocol=summarize.PROTOCOL, engineering_only=True,
                 formal_split_status='UNKNOWN', validation_status='NOT_RUN_NO_FORMAL_SPLIT',
                 subject_mapping_status='UNKNOWN')
    records = []
    for step in (1, 2):
        records.append(dict(step=step, batch_size=1, frame_indices=[step-1],
            frame_ids=[dict(case='caseA', unit='unitA', pair_index=step-1,
                belt='16_adjacent', subject_id=None, npz_sha256='e'*64, sidecar_sha256='f'*64)],
            masked_elements=100, mask_sha256=str(step)*64,
            losses=dict(total=3.0, voltage=1.0, coarse=2.0),
            loader_seconds=0.1, step_seconds=float(step), diagnostic_seconds=0.2,
            rss_before=dict(rss_bytes=100, peak_rss_bytes=200),
            rss_after=dict(rss_bytes=150, peak_rss_bytes=250),
            rss_peak_scope='process_lifetime', kml_calls=20, adamw_step=step, cursor=step))
    result = dict(flags, evidence_kind='LOCAL_FIXTURE', status=summarize.SUCCESS, completed_updates=2, planned_updates=2,
        consumed_frames=2, stop_reason='epoch_complete',
        data_identity=dict(interface_sha256=summarize.INTERFACE_SHA,
            corpus=dict(manifest=dict(sha256=summarize.MANIFEST_SHA))),
        source=dict(manifest_sha256='a'*64, files={'train_engineering.py': 'b'*64}),
        source_and_data_after='PASS_SAME_FROZEN_IDENTITIES',
        config=dict(threads=36), steps=copy.deepcopy(records),
        runtime=dict(backend='kml', torch_threads=36, kml_gemm_calls=40,
            kml_resolved='/lib/libkblas.so', libraries=[dict(path='/lib/libkblas.so', sha256='c'*64)]),
        cpu36=dict(errors=[], checkpoints=[dict(name='publish')]),
        checkpoint=dict(path='/remote/final.pt', bytes=123, sha256='d'*64),
        recovery=dict(status='PASS_NO_EXTRA_UPDATE', extra_updates=0),
        exposure_ledger=dict(path='/remote/EXPOSURE_LEDGER.json'),
        timing=dict(wall_seconds=10, data_loading_seconds=1, batch_materialization_seconds=0.2,
            training_step_seconds=3, diagnostic_seconds=0.4,
            checkpoint_and_recovery_seconds=2, unattributed_seconds=3.4))
    ledger = dict(protocol=summarize.PROTOCOL, engineering_only=True,
        formal_split_status='UNKNOWN', subject_mapping_status='UNKNOWN', units=[dict(
            case='caseA', unit='unitA', npz_sha256='e'*64, sidecar_sha256='f'*64,
            selection_status='SELECTED_RESERVED', usage_status='CONSUMED_CONFIRMED')])
    return result, records, ledger


class SummaryChecks(unittest.TestCase):
    def run_fixture(self, mutate=None):
        result, records, ledger = fixture()
        if mutate:
            mutate(result, records, ledger)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root/'result.json').write_text(json.dumps(result), encoding='utf-8')
            (root/'steps.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
            (root/'EXPOSURE_LEDGER.json').write_text(json.dumps(ledger), encoding='utf-8')
            (root/'exit_code.txt').write_text('0', encoding='utf-8')
            return summarize.analyze(root)

    def test_complete_observations_never_quality_pass(self):
        value = self.run_fixture()
        self.assertEqual(value['issues'], [])
        self.assertEqual(value['observations']['step_seconds']['median'], 1.5)
        self.assertEqual(value['observations']['observed_frame_count'], 2)
        self.assertEqual(value['observations']['rss_scope'], 'process_lifetime')
        self.assertNotIn('PASS', value['summary_status'])

    def test_missing_fields_remain_unknown(self):
        def mutate(r, steps, ledger):
            del r['timing']['wall_seconds']
            del steps[0]['diagnostic_seconds']
            del steps[0]['losses']['coarse']
        value = self.run_fixture(mutate)
        self.assertIsNone(value['timing']['wall_seconds'])
        self.assertTrue(any('coarse' in s for s in value['issues']))
        self.assertTrue(any('diagnostic_seconds' in s for s in value['issues']))

    def test_failure_and_missing_step_preserved(self):
        def mutate(r, steps, ledger):
            r['status'] = 'INCOMPLETE'
            r['error'] = 'budget reached'
            steps.pop(0)
        value = self.run_fixture(mutate)
        self.assertEqual(value['run_status'], 'INCOMPLETE')
        self.assertEqual(value['error'], 'budget reached')
        self.assertTrue(any('sequence' in s for s in value['issues']))

    def test_source_mismatch_duplicate_and_nonfinite(self):
        def mutate(r, steps, ledger):
            r['data_identity']['corpus']['manifest']['sha256'] = '0'*64
            steps[1]['frame_ids'] = copy.deepcopy(steps[0]['frame_ids'])
            steps[1]['losses']['voltage'] = float('nan')
        value = self.run_fixture(mutate)
        self.assertTrue(any('manifest' in s for s in value['issues']))
        self.assertTrue(any('duplicate' in s for s in value['issues']))
        self.assertTrue(any('voltage' in s for s in value['issues']))

    def test_missing_files_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root/'exit_code.txt').write_text('137', encoding='utf-8')
            value = summarize.analyze(root)
            self.assertEqual(value['exit_code'], 137)
            self.assertTrue(any('result.json' in s for s in value['issues']))
            self.assertTrue(any('137' in s for s in value['issues']))

    def test_malformed_jsonl_does_not_hide_other_steps(self):
        result, records, ledger = fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            (root/'steps.jsonl').write_text(json.dumps(records[0])+'\nBAD\n'+json.dumps(records[1]), encoding='utf-8')
            value = summarize.analyze(root)
            self.assertEqual(value['observations']['logged_steps'], 2)
            self.assertTrue(any('line 2' in s for s in value['issues']))

    def test_ledger_mismatch_and_unconfirmed_exposure(self):
        def mutate(r, steps, ledger):
            ledger['units'][0]['npz_sha256'] = '0'*64
            ledger['units'][0]['usage_status'] = 'POSSIBLY_USED_IN_INTERRUPTED_UPDATE'
        value = self.run_fixture(mutate)
        self.assertTrue(any('frame/ledger' in s for s in value['issues']))
        self.assertEqual(value['exposure']['usage_counts'], {'POSSIBLY_USED_IN_INTERRUPTED_UPDATE': 1})

    def test_wrong_nested_types_report_gaps(self):
        def mutate(r, steps, ledger):
            r['data_identity']['corpus'] = []
            steps[0]['losses'] = []
            ledger['units'] = [None]
        value = self.run_fixture(mutate)
        self.assertTrue(value['issues'])
        self.assertIn('UNKNOWN', summarize.markdown(value))


if __name__ == '__main__':
    unittest.main(verbosity=2)
