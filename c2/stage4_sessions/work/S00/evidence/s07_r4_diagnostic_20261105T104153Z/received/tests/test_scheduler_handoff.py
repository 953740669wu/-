"""Portable standard-library controls; no SSH, scheduler submission or Torch."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scheduler_handoff as h


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'evidence')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = dict(job_id='new-job', host='compute-test', allowed=list(range(76)))
        self.req = h.create_request(self.root, self.ctx)
        self.job = dict(jobId='new-job', state='RUNNING', exclusive=True, jobWallClockLimit=300,
            resGroups=[dict(resReq=dict(cpu=76, mem=24576), resLimit=dict(mem=24576),
                nodeResUsages=[dict(execNode='compute-test', hwThreads='0-75')])])

    def publish_fixture(self, job=None, **changes):
        raw = json.dumps(dict(data=dict(successData=[job or self.job]))).encode()
        h.atomic_write(self.root / 'scheduler_allocation.json', raw)
        header = dict(job_id=self.ctx['job_id'], nonce=self.req['nonce'], generated_at=time.time(),
                      request_sha256=h.digest(h.encode(self.req)), raw_sha256=h.digest(raw))
        header.update(changes)
        h.atomic_write(self.root / 'scheduler_ready.json', h.encode(header))

    def check(self):
        return h.await_handoff(self.root, self.req, self.ctx, 76, 24576, 300, timeout=0.03)

    def test_normal_atomic_receipt(self):
        self.publish_fixture()
        receipt = self.check()
        self.assertEqual(receipt['job_id'], 'new-job')
        self.assertEqual(receipt['allowed'], list(range(76)))

    def test_missing_timeout(self):
        with self.assertRaises(TimeoutError): self.check()

    def test_partial_temporary_file_is_not_committed(self):
        (self.root / '.scheduler_ready.json.partial').write_bytes(b'{')
        with self.assertRaises(TimeoutError): self.check()

    def test_raw_without_commit_times_out(self):
        (self.root / 'scheduler_allocation.json').write_bytes(b'{}')
        with self.assertRaises(TimeoutError): self.check()

    def test_incomplete_committed_file_rejected(self):
        (self.root / 'scheduler_ready.json').write_bytes(b'{')
        with self.assertRaises(ValueError): self.check()

    def test_corrupt_raw_rejected(self):
        self.publish_fixture()
        (self.root / 'scheduler_allocation.json').write_bytes(b'{')
        with self.assertRaises(ValueError): self.check()

    def test_old_or_future_receipt_rejected(self):
        for age in (-60, 60):
            with self.subTest(age=age):
                for p in self.root.glob('scheduler_*json'):
                    if p.name != 'scheduler_request.json': p.unlink()
                self.publish_fixture(generated_at=time.time() + age)
                with self.assertRaises(ValueError): self.check()

    def test_other_request_nonce_rejected(self):
        self.publish_fixture(nonce='old-request')
        with self.assertRaises(ValueError): self.check()

    def test_request_digest_mismatch_rejected(self):
        self.publish_fixture(request_sha256='0' * 64)
        with self.assertRaises(ValueError): self.check()

    def test_missing_raw_after_commit_rejected(self):
        self.publish_fixture(); (self.root / 'scheduler_allocation.json').unlink()
        with self.assertRaises(OSError): self.check()

    def test_blank_live_identity_rejected(self):
        with self.assertRaises(ValueError):
            h.create_request(self.root, dict(self.ctx, job_id='  '))

    def test_old_job_rejected(self):
        job = copy.deepcopy(self.job); job['jobId'] = 'old-job'
        self.publish_fixture(job)
        with self.assertRaises(ValueError): self.check()

    def test_other_host_rejected(self):
        job = copy.deepcopy(self.job); job['resGroups'][0]['nodeResUsages'][0]['execNode'] = 'other'
        self.publish_fixture(job)
        with self.assertRaises(ValueError): self.check()

    def test_other_cpu_authority_rejected(self):
        job = copy.deepcopy(self.job); job['resGroups'][0]['nodeResUsages'][0]['hwThreads'] = '1-76'
        self.publish_fixture(job)
        with self.assertRaises(ValueError): self.check()

    def test_empty_raw_rejected(self):
        self.publish_fixture(); (self.root / 'scheduler_allocation.json').write_bytes(b'')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_resource_limits_rejected(self):
        job = copy.deepcopy(self.job); job['resGroups'][0]['resLimit']['mem'] = 49152
        self.publish_fixture(job)
        with self.assertRaises(ValueError): self.check()

    def test_nonrunning_or_nonexclusive_rejected(self):
        for key, value in [('state', 'SUCCEEDED'), ('exclusive', False)]:
            with self.subTest(key=key):
                for p in self.root.glob('scheduler_*json'):
                    if p.name != 'scheduler_request.json': p.unlink()
                job = copy.deepcopy(self.job); job[key] = value; self.publish_fixture(job)
                with self.assertRaises(ValueError): self.check()

    def test_live_context_mismatch_rejected(self):
        self.publish_fixture(); self.ctx = dict(self.ctx, job_id='different-live-job')
        with self.assertRaises(ValueError): self.check()

    def test_atomic_publish_preserves_exact_bytes(self):
        raw = b'{"original":  1}\n'; p = self.root / 'raw.json'
        h.atomic_write(p, raw)
        self.assertEqual(p.read_bytes(), raw)
        with self.assertRaises(FileExistsError): h.atomic_write(p, b'replace')

    def test_native_identity_is_required_and_not_overwritten(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): h.live_context()
        with mock.patch.dict(os.environ, {'CCS_JOB_ID': 'native-job'}, clear=True), \
                mock.patch.object(h.os, 'sched_getaffinity', return_value={2, 1}, create=True), \
                mock.patch.object(h.socket, 'gethostname', return_value='native-host'):
            self.assertEqual(h.live_context(), dict(job_id='native-job', host='native-host', allowed=[1, 2]))
            self.publish_fixture()
            self.check()
            self.assertEqual(os.environ['CCS_JOB_ID'], 'native-job')

    def test_wrong_cpu_memory_wall_or_multiple_nodes_rejected(self):
        for field in ('cpu', 'mem', 'wall', 'nodes'):
            with self.subTest(field=field):
                for p in self.root.glob('scheduler_*json'):
                    if p.name != 'scheduler_request.json': p.unlink()
                job = copy.deepcopy(self.job)
                group = job['resGroups'][0]
                if field in ('cpu', 'mem'): group['resReq'][field] += 1
                if field == 'wall': job['jobWallClockLimit'] += 1
                if field == 'nodes': group['nodeResUsages'].append(copy.deepcopy(group['nodeResUsages'][0]))
                self.publish_fixture(job)
                with self.assertRaises(ValueError): self.check()

    def test_publisher_preserves_raw_and_exact_bounded_command(self):
        raw = json.dumps(dict(data=dict(successData=[self.job]))).encode()
        with mock.patch.object(h.shutil, 'which', return_value='/scheduler/djob'), \
                mock.patch.object(h.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, raw, b'')) as run:
            h.publish(self.root, 'new-job')
        run.assert_called_once_with(['/scheduler/djob', '-J', '-l', 'new-job'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual((self.root / 'scheduler_allocation.json').read_bytes(), raw)
        self.check()

    def test_query_failure_keeps_original_without_ready(self):
        with mock.patch.object(h.shutil, 'which', return_value='/scheduler/djob'), \
                mock.patch.object(h.subprocess, 'run', return_value=subprocess.CompletedProcess([], 7, b'original error', b'denied')):
            with self.assertRaises(RuntimeError): h.publish(self.root, 'new-job')
        self.assertEqual((self.root / 'scheduler_allocation.json').read_bytes(), b'original error')
        self.assertEqual(json.loads((self.root / 'scheduler_query_receipt.json').read_bytes())['exit_code'], 7)
        self.assertFalse((self.root / 'scheduler_ready.json').exists())

    def test_query_timeout_keeps_partial_output_without_ready(self):
        with mock.patch.object(h.shutil, 'which', return_value='/scheduler/djob'), \
                mock.patch.object(h.subprocess, 'run', side_effect=subprocess.TimeoutExpired('djob', 5, output=b'partial', stderr=b'timeout')):
            with self.assertRaises(subprocess.TimeoutExpired): h.publish(self.root, 'new-job')
        self.assertEqual((self.root / 'scheduler_allocation.json').read_bytes(), b'partial')
        receipt = json.loads((self.root / 'scheduler_query_receipt.json').read_bytes())
        self.assertTrue(receipt['timed_out'])
        self.assertEqual(receipt['timeout_seconds'], 5)
        self.assertFalse((self.root / 'scheduler_ready.json').exists())

    def test_publisher_rejects_old_job_before_query(self):
        with mock.patch.object(h.subprocess, 'run') as run:
            with self.assertRaises(ValueError): h.publish(self.root, 'old-job')
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
