"""LOCAL_FIXTURE: standard-library metadata only, never actual runtime evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import contracts as c

NS = 10**9


def identity():
    return dict(pid=101, ppid=100, pgid=101, session=101, start_ticks=900,
                parent_start_ticks=800, boot_id='fixture-boot', job='fixture-job',
                run='fixture-run', exe_sha256='a'*64)


def report():
    return dict(scope='LOCAL_FIXTURE', spec_sha256=c.SPEC_SHA, complete=True,
                status='LOCAL_FIXTURE_VALID', actual_autograd=False,
                actual_KML=False, actual_Linux_exit=False)


class ContractFixtures(unittest.TestCase):
    def test_01_sample_major_and_token_major_rows(self):
        ids = list(range(64)); first = ids[:32]
        batch = c.rows(ids, first, 'sample_token', 208, [64,208,512], 'a'*64)
        token = c.rows(ids, first, 'token_sample', 208, [208,64,512], 'a'*64)
        flattened = c.rows(ids, first, 'token_sample', 208, [13312,512], 'a'*64)
        self.assertEqual(batch, list(range(32*208)))
        self.assertEqual(token[:209], [t*64 for t in range(208)] + [1])
        self.assertEqual(token, flattened)
        self.assertNotEqual(token, list(range(32*208)))

    def test_02_ambiguous_missing_duplicate_or_wrong_order_rejected(self):
        ids = list(range(64))
        for order, provenance in [('unknown', 'a'*64), ('token_sample', '')]:
            with self.assertRaises(c.ContractError): c.rows(ids, ids[:32], order, 208, [13312,512], provenance)
        for shards in ([ids[:32], ids[:32]], [ids[:31], ids[32:]], [ids[32:], ids[:32]]):
            with self.assertRaises(c.ContractError): c.partition(ids, shards)
        c.partition(ids, [ids[:32], ids[32:]])

    def test_03_global_counts_local_zero_and_no_ddp_factors(self):
        self.assertEqual(c.scaling([0,6000], [8192,8192], [1,1,1]), [6000,16384])
        for mask, factors in [([0,0], [1,1,1]), ([0,7000], [1,1,1]), ([1,2], [2,1,2]), ([1,2], [1,2,1])]:
            with self.assertRaises(c.ContractError): c.scaling(mask, [8192,8192], factors)

    def test_04_one_full_and_one_sequence_path(self):
        paths = c.Paths(0)
        paths.begin('A_FULL_B64', 0)
        paths.record('forward', NS); paths.record('backward', 2*NS); paths.finish(3*NS)
        paths.begin('B_SEQUENTIAL_32_PLUS_32', 4*NS)
        for event in ('forward','backward','forward','backward'): paths.record(event, 5*NS)
        paths.finish(6*NS)
        self.assertEqual(paths.completed, ['A_FULL_B64','B_SEQUENTIAL_32_PLUS_32'])
        with self.assertRaises(c.ContractError): paths.begin('A_FULL_B64', 7*NS)

    def test_05_no_updates_extra_paths_or_compute_after_numeric_fail(self):
        paths = c.Paths(0); paths.begin('A_FULL_B64', 0)
        for event in ('optimizer_step','extra_gemm','autograd_grad','DDP'):
            with self.assertRaises(c.ContractError): paths.record(event, NS)
        paths.numeric_failure()
        with self.assertRaises(c.ContractError): paths.record('forward', NS)
        with self.assertRaises(c.ContractError): paths.begin('B_SEQUENTIAL_32_PLUS_32', NS)

    def test_06_shared_and_path_deadlines_are_not_reset(self):
        paths = c.Paths(10*NS); paths.begin('A_FULL_B64', 10*NS)
        with self.assertRaises(c.ContractError): paths.record('forward', 101*NS)
        paths = c.Paths(0)
        with self.assertRaises(c.ContractError): paths.begin('A_FULL_B64', 241*NS)

    def test_07_retention_and_output_caps(self):
        proof = c.retention_proof()
        self.assertLess(proof['retained_bytes_bound'], c.RETAIN_MAX)
        self.assertLess(proof['raw_reference_value_bytes'], c.RAW_MAX)
        self.assertEqual(proof['parameter_fp32_bytes'], 151983108)
        budget = c.Budget(); budget.reserve('retained', 'one', c.RETAIN_MAX)
        with self.assertRaises(c.ContractError): budget.reserve('retained','two',1)
        with self.assertRaises(c.ContractError): budget.reserve('raw','dump',c.RAW_MAX+1)
        with self.assertRaises(c.ContractError): budget.reserve('text','log',c.TEXT_MAX+1)
        with self.assertRaises(c.ContractError): budget.reserve('retained','one',0)

    def test_08_proc_stat_parentheses_and_creation_identity(self):
        fields = ['S','100','101','101'] + ['0']*15 + ['900']
        text = '101 (fixture (worker) name) ' + ' '.join(fields)
        self.assertEqual(c.parse_stat(text), dict(pid=101,ppid=100,pgid=101,session=101,start_ticks=900))
        with self.assertRaises(c.ContractError): c.parse_stat('101 (partial')

    def test_09_identity_drift_and_launcher_mismatch_rejected(self):
        expected = identity(); c.compute_identity(identity(), expected, 101, 100)
        for key, value in [('pid',102),('ppid',99),('start_ticks',901),('job','old'),
                           ('run','old'),('boot_id','other'),('pgid',100),('session',100),
                           ('parent_start_ticks',801),('exe_sha256','b'*64)]:
            changed = dict(expected); changed[key] = value
            with self.assertRaises(c.ContractError): c.compute_identity(changed, expected, 101, 100)

    def test_10_popen_reap_or_late_absence_never_proves_compute_exit(self):
        owned = {101:900}
        for event in ('POPEN_REAP','LATER_PID_ABSENT'):
            with self.assertRaises(c.ContractError):
                c.exit_evidence(owned, [dict(pid=101,start_ticks=900,event=event,at_ns=250*NS)], 0, True)
        events = [dict(pid=101,start_ticks=900,event=kind,at_ns=250*NS)
                  for kind in ('ACTUAL_EXIT','REAP')]
        c.exit_evidence(owned, events, 0, True)
        with self.assertRaises(c.ContractError): c.exit_evidence(owned, events, 0, False)
        events[0]['start_ticks'] = 901
        with self.assertRaises(c.ContractError): c.exit_evidence(owned, events, 0, True)

    def test_11_common_cleanup_deadline_and_unowned_pid(self):
        for pid, when in [(999,250*NS),(101,271*NS)]:
            events = [dict(pid=pid,start_ticks=900,event=k,at_ns=when) for k in ('ACTUAL_EXIT','REAP')]
            with self.assertRaises(c.ContractError): c.exit_evidence({101:900},events,0,True)

    def test_12_atomic_report_missing_partial_stale_and_claims_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence', prefix='fixture_') as tmp:
            path = Path(tmp)/'result.json'
            with self.assertRaises((OSError,c.ContractError)): c.read_report(path)
            c.write_report(path, report()); self.assertEqual(c.read_report(path)['scope'],'LOCAL_FIXTURE')
            with self.assertRaises(c.ContractError): c.write_report(path, report())
            partial = Path(tmp)/'partial.tmp'; partial.write_text('{')
            with self.assertRaises(c.ContractError): c.read_report(partial)
            for raw in ('', '{', '{"scope":"LOCAL_FIXTURE","scope":"OTHER"}'):
                broken = Path(tmp)/'broken.json'; broken.write_text(raw)
                with self.assertRaises(c.ContractError): c.read_report(broken)
        for key, value in [('scope','ACTUAL'),('complete',False),('spec_sha256','0'*64),('actual_KML',True)]:
            bad = report(); bad[key] = value
            with self.assertRaises(c.ContractError): c.validate_report(bad)

    def test_13_missing_pinned_observer_coverage_blocks(self):
        with self.assertRaisesRegex(c.ContractError, 'B01_UNBOUND_INSTALLED_NATIVE_VJP'):
            c.require_observer_coverage({'ddp_source','torch_init'})

    def test_14_no_torch_imported(self):
        self.assertNotIn('torch',sys.modules)
        self.assertNotIn('numpy',sys.modules)


if __name__ == '__main__':
    (ROOT/'evidence').mkdir(exist_ok=True)
    unittest.main(verbosity=2)
