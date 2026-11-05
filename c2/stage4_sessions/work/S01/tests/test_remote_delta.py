"""Checks for the diagnostic changes found in the accepted remote snapshots."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'candidate'))
import runner


class RemoteDeltaChecks(unittest.TestCase):
    def test_snapshot_identity_and_summary_equivalence(self):
        evidence = WORK.parent / 'S00/evidence'
        archive = (WORK.parent / 'S00/baseline/c2/opt/run_node16.sh').read_text()
        expected = [('run_node16.sh', 'ea27c594dd61865dfbbd67e3bdda216fc8a63df4acb2cb363807be52d8f9ccaf'),
                    ('run_node16_latest.sh', '0da6c46de4e4f7ac9694ba966af9ee23a4b63227137fea72f9c99b7e62f73e41')]
        def summary(text):
            return text.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        for filename, digest in expected:
            path = evidence / 'remote_sources' / filename
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            self.assertEqual(summary(archive), summary(path.read_text()))

    def test_core_limit_applies_after_affinity_and_busy_filter(self):
        self.assertEqual(runner.select_cpus(list(range(38)), set(range(38)), set(), limit=36), list(range(36)))
        self.assertEqual(runner.select_cpus([0, 1, 2, 3], {1, 2, 3}, {1}, limit=1), [2])
        for value in (0, -1, True):
            with self.assertRaises(ValueError):
                runner.select_cpus([0], {0}, set(), limit=value)

    def test_unknown_sampler_is_explicitly_disabled_or_rejected(self):
        config = runner.diagnostic_config({})
        self.assertFalse(config['sample_foreign'])
        self.assertIn('source unavailable', config['sample_foreign_reason'])
        self.assertEqual(config['cores_per_domain'], 99)
        self.assertTrue(config['python_faulthandler'])
        with self.assertRaisesRegex(ValueError, 'source unavailable'):
            runner.diagnostic_config({'SAMPLE_FOREIGN': '1'})
        for value in ('invalid', '-1', '0'):
            with self.assertRaises(ValueError):
                runner.diagnostic_config({'CORES_PER_DOM': value})

    def test_fault_diagnostics_retained_with_real_exit_status(self):
        with tempfile.TemporaryDirectory(dir=WORK / 'tests') as directory:
            command = [sys.executable, '-c', 'print("Fatal Python error: Bus error",flush=True); raise SystemExit(7)']
            states = runner.supervise({0: command}, {0: os.environ.copy()}, directory, 3)
            self.assertEqual(states[0]['exit_code'], 7)
            self.assertEqual(states[0]['diagnostic_matches']['count'], 1)
            self.assertIn('Bus error', states[0]['diagnostic_matches']['tail'][0])

    def test_legacy_input_label_is_enforced(self):
        # Reuse a complete fixture, then change only its declared input protocol.
        sys.path.insert(0, str(WORK / 'tests'))
        from test_runner import RunnerChecks
        fixture = RunnerChecks()
        fixture.setUp()
        try:
            fixture.spec['input_protocol'] = 'LEGACY_TIMING_ONLY'
            for data in fixture.results.values():
                data['run']['input_protocol'] = 'LEGACY_TIMING_ONLY'
            fixture.write_fixture()
            self.assertEqual(runner.summarize(fixture.root)['status'], 'PASS')
            fixture.results[1, 1]['run']['input_protocol'] = 'SCIENTIFIC_TRAINING'
            fixture.write_fixture()
            self.assertEqual(runner.summarize(fixture.root)['status'], 'FAIL')
        finally:
            fixture.doCleanups()

    def test_shell_keeps_faulthandler_and_owner_path_is_read_only(self):
        text = (WORK / 'candidate/run_node16.sh').read_text()
        self.assertIn('PYTHONFAULTHANDLER=1', text)
        self.assertNotIn('S01_RUN=$H/', text)
        self.assertNotIn('$H/opt/sample_foreign.py', text)

    def test_legacy_file_identity_is_pinned_to_saved_evidence(self):
        identity = runner.read_json(WORK / 'candidate/legacy_inputs.json')
        evidence = runner.read_json(WORK.parent / 'S00/evidence/remote_details.json')
        self.assertEqual(identity['input_protocol'], 'LEGACY_TIMING_ONLY')
        self.assertEqual(identity['cases'], {case: row['sha256'] for case, row in evidence['inputs'].items()})
        with tempfile.TemporaryDirectory(dir=WORK / 'tests') as directory:
            paths = {}
            for case in identity['cases']:
                paths[case] = Path(directory) / f'{case}.npz'
                paths[case].write_bytes(b'SYNTHETIC FILE IDENTITY TEST ONLY')
            with self.assertRaises(ValueError):
                runner.verify_legacy_inputs(paths, identity)
            synthetic = dict(input_protocol='LEGACY_TIMING_ONLY', cases={case: runner.sha(path) for case, path in paths.items()})
            runner.verify_legacy_inputs(paths, synthetic)
            paths['s0322p0'].write_bytes(b'changed')
            with self.assertRaises(ValueError):
                runner.verify_legacy_inputs(paths, synthetic)


if __name__ == '__main__':
    unittest.main(verbosity=2)
