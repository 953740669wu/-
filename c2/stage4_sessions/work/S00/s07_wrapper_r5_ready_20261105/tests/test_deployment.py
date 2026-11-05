"""Deployment contracts and synthetic evidence only; never submit or import Torch."""
import io
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import subprocess
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare
import trace_inventory
import run_s07_diag_job as job
import collect_evidence
import submit_once


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'evidence')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_exact_new_inner_and_manifest(self):
        shutil.copyfile(ROOT / prepare.ARCHIVE, self.root / prepare.ARCHIVE)
        prepare.unpack(self.root)
        self.assertEqual(len(list(p for p in (self.root / 'payload').rglob('*') if p.is_file())), 13)
        self.assertEqual(len(json.loads((self.root / 'payload/SOURCE_MANIFEST.json').read_bytes())['delivery_files']), 12)

    def test_old_or_changed_bytes_rejected_before_extraction(self):
        (self.root / prepare.ARCHIVE).write_bytes(b'old R2 bytes')
        with self.assertRaises(ValueError): prepare.unpack(self.root)
        self.assertFalse((self.root / 'payload').exists())

    def test_prepare_writes_new_identity_and_thirteen_source_entries(self):
        shutil.copyfile(ROOT / prepare.ARCHIVE, self.root / prepare.ARCHIVE)
        with mock.patch.object(prepare, 'BASE', self.root.parent), mock.patch.object(prepare, 'PREFIX', self.root.name):
            prepare.main(self.root)
        pre = json.loads((self.root / 'pre_submit_checks.json').read_bytes())
        self.assertEqual((pre['package_name'], pre['package_sha256']), (prepare.ARCHIVE, prepare.INNER_SHA))
        self.assertEqual((len(pre['payload_files']), pre['manifest_entries']), (13, 12))
        self.assertFalse((self.root / 'job_id.txt').exists())

    def test_manifest_changed_or_missing_member_rejected(self):
        with zipfile.ZipFile(ROOT / prepare.ARCHIVE) as original:
            manifest = json.loads(original.read('SOURCE_MANIFEST.json'))
            for kind in ('changed', 'missing'):
                with self.subTest(kind=kind):
                    data = io.BytesIO()
                    with zipfile.ZipFile(data, 'w') as z:
                        for name in original.namelist():
                            if kind == 'missing' and name == 'candidate/comm_probe.py': continue
                            z.writestr(name, b'changed' if kind == 'changed' and name == 'candidate/comm_probe.py' else original.read(name))
                    with zipfile.ZipFile(data) as altered:
                        with self.assertRaises(ValueError): prepare.check_members(altered, manifest)

    def test_checks_are_16_6_6_16_and_share_one_budget(self):
        self.assertEqual(job.CHECKS, [('readiness_tests', 'test_readiness.py', 16, 30),
                                    ('diagnostic_tests', 'test_diagnostics.py', 6, 30),
                                    ('job_identity_tests', 'test_job_identity.py', 6, 45),
                                    ('probe_tests', 'test_probe.py', 16, 45)])
        self.assertEqual(job.CONSUMER_SECONDS, 270)
        self.assertEqual(sum(x[2] for x in job.CHECKS), 44)
        self.assertEqual(hashlib.sha256((ROOT / 'scheduler_handoff.py').read_bytes()).hexdigest(), 'f907cbf8286f7bc9035c9e58f986c3b342b2a6f6f5a1c60f97834915f2a7065c')
        self.assertEqual(hashlib.sha256((ROOT / 'bounded_round_step.py').read_bytes()).hexdigest(), 'b9fa564e89edcdaaf9e597f6511e84fb8b845cddd6c065ae489ba61d1f2dc697')

    def fixture(self):
        case = self.root / 'payload/checks_current_job/normal'; case.mkdir(parents=True)
        (case / 'manifest.json').write_text(json.dumps(dict(job_id='new-job', run_id='normal')))
        (case / 'summary.json').write_text(json.dumps(dict(supervisor=dict(pids=[11, 12], all_reaped=True))))
        def write(name, pid, rows):
            with (case / name).open('w') as f:
                for index, row in enumerate(rows, 1):
                    f.write(json.dumps(dict(time_ns=index, monotonic_ns=index, pid=pid, **row)) + '\n')
        for rank in (0, 1):
            write('rank' + str(rank) + '.events.jsonl', 11 + rank,
                  [dict(event='worker_ready', rank=rank, job_id='new-job', run_id='normal'),
                   dict(event='torch_import_begin'), dict(event='torch_import_end'), dict(event='worker_exit', exit_code=0)])
        write('supervisor.events.jsonl', 10, [dict(event='supervisor_begin'),
            dict(event='spawned', rank=0, child_pid=11), dict(event='spawned', rank=1, child_pid=12),
            dict(event='cleanup_begin'), dict(event='child_reaped', child_pid=11),
            dict(event='child_reaped', child_pid=12), dict(event='supervisor_end')])
        return case

    def test_three_streams_valid_and_original_bytes_retained(self):
        case = self.fixture(); paths = list(case.glob('*.jsonl'))
        before = {p.name: p.read_bytes() for p in paths}
        receipt = trace_inventory.inspect(self.root)
        self.assertTrue(receipt['complete'])
        self.assertEqual(set(receipt['cases']['normal']['files']), set(before))
        self.assertEqual(before, {p.name: p.read_bytes() for p in paths})

    def test_missing_stream_is_incomplete(self):
        case = self.fixture(); (case / 'rank0.events.jsonl').unlink()
        self.assertFalse(trace_inventory.inspect(self.root)['complete'])

    def test_truncated_or_missing_event_end_is_incomplete(self):
        case = self.fixture(); path = case / 'rank0.events.jsonl'
        path.write_bytes(path.read_bytes().rstrip(b'\n'))
        self.assertFalse(trace_inventory.inspect(self.root)['complete'])
        path.write_text(json.dumps(dict(event='torch_import_begin', time_ns=1, monotonic_ns=1, pid=11)) + '\n')
        receipt = trace_inventory.inspect(self.root)
        self.assertFalse(receipt['complete'])
        self.assertNotIn('hang', json.dumps(receipt).lower())

    def test_trace_write_error_is_incomplete(self):
        case = self.fixture(); (case / 'rank1.log').write_text('TRACE_WRITE_ERROR fsync failed\n')
        self.assertFalse(trace_inventory.inspect(self.root)['complete'])

    def test_wrong_identity_or_missing_supervisor_row_is_incomplete(self):
        case = self.fixture(); path = case / 'rank1.events.jsonl'
        path.write_text(path.read_text().replace('new-job', 'old-job'))
        self.assertFalse(trace_inventory.inspect(self.root)['complete'])

    def test_missing_supervisor_reap_is_incomplete(self):
        case = self.fixture(); path = case / 'supervisor.events.jsonl'
        path.write_text(''.join(line for line in path.read_text().splitlines(True) if 'child_reaped' not in line))
        self.assertFalse(trace_inventory.inspect(self.root)['complete'])

    def test_unreached_cases_are_not_tested(self):
        self.fixture(); receipt = trace_inventory.inspect(self.root)
        self.assertEqual(receipt['not_run'], ['crash', 'collective-timeout', 'watchdog'])
        self.assertEqual(trace_inventory.inspect(self.root / 'missing')['status'], 'NOT_RUN')

    def test_terminal_collector_retains_incomplete_raw_streams(self):
        case = self.fixture(); damaged = case / 'rank0.events.jsonl'
        damaged.write_bytes(damaged.read_bytes() + b'{partial')
        raw = {p.name: p.read_bytes() for p in case.glob('*.jsonl')}
        (self.root / 'job_id.txt').write_text('new-job\n')
        (self.root / 'pre_submit_checks.json').write_text(json.dumps(dict(payload_files={}, wrapper_files={})))
        terminal = dict(jobId='new-job', state='FAILED', jobExitCode=1,
            resGroups=[dict(nodeResUsages=[dict(pids='-')])],
            startTime='2026-11-05T00:00:00Z', endTime='2026-11-05T00:00:01Z')
        result = subprocess.CompletedProcess([], 0, json.dumps(dict(data=dict(successData=[terminal]))).encode(), b'')
        with mock.patch.object(collect_evidence, 'BASE', self.root.parent), \
                mock.patch.object(collect_evidence, 'PREFIX', self.root.name), \
                mock.patch.object(collect_evidence.subprocess, 'run', return_value=result), \
                mock.patch('sys.stdout', new=io.StringIO()):
            collect_evidence.collect(self.root)
        with zipfile.ZipFile(self.root / 'JOB_new-job_full_evidence.zip') as z:
            for name, data in raw.items():
                self.assertEqual(z.read('payload/checks_current_job/normal/' + name), data)
            self.assertFalse(json.loads(z.read('DIAGNOSTIC_INVENTORY.json'))['complete'])

    def test_mock_submission_is_once_and_publishes_after_running(self):
        shutil.copyfile(ROOT / prepare.ARCHIVE, self.root / prepare.ARCHIVE)
        (self.root / 'pre_submit_checks.json').write_text('{}')
        results = [subprocess.CompletedProcess([], 0, b'{"data":{"jobId":"new-job"}}', b''),
                   subprocess.CompletedProcess([], 0, b'{"data":{"successData":[{"jobId":"new-job","state":"RUNNING"}]}}', b'')]
        with mock.patch.object(submit_once, 'BASE', self.root.parent), \
                mock.patch.object(submit_once, 'PREFIX', self.root.name), \
                mock.patch.object(submit_once.subprocess, 'run', side_effect=results) as run, \
                mock.patch.object(submit_once, 'publish') as publish, \
                mock.patch('sys.stdout', new=io.StringIO()):
            submit_once.submit(self.root)
            with self.assertRaises(FileExistsError): submit_once.submit(self.root)
        self.assertEqual(sum(call.args[0][0] == 'dsub' for call in run.call_args_list), 1)
        publish.assert_called_once_with(self.root, 'new-job')
        command = run.call_args_list[0].args[0]
        self.assertIn('cpu=76,mem=24576MB', command)
        self.assertEqual(command[command.index('-T')+1], '300')


if __name__ == '__main__': unittest.main(verbosity=2)
