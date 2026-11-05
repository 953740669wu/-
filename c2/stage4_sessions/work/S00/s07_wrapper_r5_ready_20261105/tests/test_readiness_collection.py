"""Synthetic post-terminal artifacts only; no workers, framework or scheduler job."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import readiness_inventory
import collect_evidence


class ReadinessCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'evidence')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, root=None):
        root = root or self.root
        case = root / 'payload/checks_current_job/normal'; case.mkdir(parents=True)
        identity = dict(run_id='normal', job_id='new-job', ready_token='a' * 32)
        (root / 'job_id.txt').write_text('new-job\n')
        (case / 'manifest.json').write_text(json.dumps(dict(identity, pg_timeout=5, deadline=30)))
        (case / 'summary.json').write_text(json.dumps(dict(supervisor=dict(pids=[11, 12], all_reaped=True))))
        (case / 'participants.json').write_text(json.dumps(dict(identity, pids=[11, 12], deadline_ns=31_000_000_000)))
        self.write(case / 'supervisor.events.jsonl', 10, [dict(event='supervisor_begin', deadline_seconds=30, monotonic_ns=1_000_000_000),
            dict(event='spawned', rank=0, child_pid=11, monotonic_ns=1_100_000_000),
            dict(event='spawned', rank=1, child_pid=12, monotonic_ns=1_200_000_000)])
        for rank in (0, 1):
            (case / ('ready_rank' + str(rank) + '.json')).write_text(json.dumps(dict(identity, rank=rank, pid=11+rank)))
            # rank1 can observe rank0's file before rank0 logs ready_published.
            own_ready = 4_000_000_000 if rank == 0 else 2_000_000_000
            self.write(case / ('rank' + str(rank) + '.events.jsonl'), 11+rank,
                [dict(event='checkpoint_end', stage='after_framework', monotonic_ns=1_400_000_000),
                 dict(event='preparation_complete', rank=rank, monotonic_ns=1_500_000_000),
                 dict(event='ready_published', rank=rank, **identity, monotonic_ns=own_ready),
                 dict(event='both_ready', rank=rank, pids=[11, 12], monotonic_ns=own_ready+100_000_000),
                 dict(event='init_process_group_begin', rank=rank, monotonic_ns=own_ready+200_000_000)])
        return case

    def write(self, path, pid, rows):
        path.write_text(''.join(json.dumps(dict(row, pid=pid, time_ns=row['monotonic_ns']))+'\n' for row in rows))

    def inspect(self, root=None): return readiness_inventory.inspect(root or self.root)

    def test_valid_participants_and_ready_are_read_only(self):
        case = self.fixture(); before = {p.name:p.read_bytes() for p in case.iterdir()}
        result = self.inspect()
        self.assertTrue(result['complete'], result)
        self.assertEqual(result['cases']['normal']['verified_context']['deadline_ns'],31_000_000_000)
        self.assertEqual(before, {p.name:p.read_bytes() for p in case.iterdir()})
        self.assertEqual(set(result['cases']['normal']['files']), {'participants.json','ready_rank0.json','ready_rank1.json'})

    def test_cross_rank_ready_log_order_is_not_publication_order(self):
        self.fixture(); self.assertTrue(self.inspect()['complete'])

    def test_bad_ready_identity_types_and_partial_json(self):
        for index, change in enumerate([dict(run_id='old'), dict(job_id='old'), dict(ready_token='old'),
                dict(rank=0), dict(rank=True), dict(pid=99), dict(pid=12.0), None]):
            with self.subTest(change=change):
                root=self.root/str(index);case=self.fixture(root);p=case/'ready_rank1.json'
                if change is None:p.write_bytes(b'{partial')
                else:
                    d=json.loads(p.read_bytes());d.update(change);p.write_text(json.dumps(d))
                self.assertFalse(self.inspect(root)['complete'])

    def test_wrong_participant_pids_or_deadline_rejected(self):
        for index, change in enumerate([dict(pids=[12,11]),dict(pids=[11,11]),dict(deadline_ns=31e9),
                                       dict(deadline_ns=41_000_000_000),dict(ready_token='old')]):
            root=self.root/str(index);case=self.fixture(root);p=case/'participants.json'
            d=json.loads(p.read_bytes());d.update(change);p.write_text(json.dumps(d))
            self.assertFalse(self.inspect(root)['complete'])

    def test_parent_spawn_pids_must_match(self):
        case=self.fixture();p=case/'supervisor.events.jsonl';p.write_text(p.read_text().replace('"child_pid": 12','"child_pid": 99'))
        self.assertFalse(self.inspect()['complete'])

    def test_init_attempt_at_deadline_is_flagged(self):
        case=self.fixture();p=case/'rank1.events.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
        rows[-1]['monotonic_ns']=31_000_000_000;self.write(p,12,rows)
        self.assertFalse(self.inspect()['complete'])

    def test_missing_own_preparation_or_both_ready_is_flagged(self):
        for index,event in enumerate(['preparation_complete','ready_published','both_ready']):
            root=self.root/str(index);case=self.fixture(root);p=case/'rank0.events.jsonl'
            p.write_text(''.join(x for x in p.read_text().splitlines(True) if '"event": "'+event+'"' not in x))
            self.assertFalse(self.inspect(root)['complete'])

    def test_missing_participants_still_indexes_ready_and_temporary_files(self):
        case=self.fixture();(case/'participants.json').unlink();(case/'participants.json.tmp').write_bytes(b'{partial')
        result=self.inspect();self.assertFalse(result['complete'])
        self.assertIn('ready_rank0.json',result['cases']['normal']['files'])
        self.assertIn('participants.json.tmp',result['cases']['normal']['temporary_files'])

    def test_temporary_bytes_preserved_even_if_json_is_invalid(self):
        case=self.fixture();p=case/'ready_rank1.json.tmp';p.write_bytes(b'{partial')
        result=self.inspect();self.assertFalse(result['complete']);self.assertEqual(p.read_bytes(),b'{partial')

    def test_terminal_collector_keeps_all_readiness_files_and_residuals(self):
        case=self.fixture();(case/'ready_rank1.json.tmp').write_bytes(b'{partial')
        originals={p.name:p.read_bytes() for p in case.glob('*') if p.name.startswith(('participants','ready_rank'))}
        (self.root/'pre_submit_checks.json').write_text(json.dumps(dict(payload_files={},wrapper_files={})))
        terminal=dict(jobId='new-job',state='FAILED',jobExitCode=1,resGroups=[dict(nodeResUsages=[dict(pids='-')])],
                      startTime='2026-11-05T00:00:00Z',endTime='2026-11-05T00:00:01Z')
        answer=subprocess.CompletedProcess([],0,json.dumps(dict(data=dict(successData=[terminal]))).encode(),b'')
        with mock.patch.object(collect_evidence,'BASE',self.root.parent),mock.patch.object(collect_evidence,'PREFIX',self.root.name),\
             mock.patch.object(collect_evidence.subprocess,'run',return_value=answer),mock.patch('sys.stdout',new=io.StringIO()):
            collect_evidence.collect(self.root)
        with zipfile.ZipFile(self.root/'JOB_new-job_full_evidence.zip') as z:
            for name,data in originals.items():self.assertEqual(z.read('payload/checks_current_job/normal/'+name),data)
            self.assertFalse(json.loads(z.read('READINESS_INVENTORY.json'))['complete'])


if __name__ == '__main__': unittest.main(verbosity=2)
