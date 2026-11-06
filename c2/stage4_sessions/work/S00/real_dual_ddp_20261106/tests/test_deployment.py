"""New deployment boundaries: exact review and hostile/changed package rejection."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare import check_archive, RESOURCES, WORKLOAD
from review_gate import validate
from collect_evidence import remote_weight
import collect_evidence
from submit_once import documents


class DeploymentTests(unittest.TestCase):
    def review(self):
        bindings = {'reference_package_sha256': 'a'*64, 'training_package_sha256': 'b'*64,
                    'deployment_package_sha256': 'c'*64}
        return bindings, dict(decision='PASS_FOR_REAL_DUAL_DDP', review_complete=True,
                              bindings=bindings.copy(), resources=RESOURCES.copy(), workload=WORKLOAD.copy())

    def test_complete_bound_review(self):
        bindings, review = self.review()
        validate(review, bindings)

    def test_no_old_or_incomplete_approval(self):
        for decision, complete in [('PASS_FOR_S07_R7_ATOMIC', True), ('BLOCKED', False),
                                   ('PASS_FOR_REAL_DUAL_DDP', False)]:
            bindings, review = self.review()
            review.update(decision=decision, review_complete=complete)
            with self.assertRaises(ValueError): validate(review, bindings)

    def test_each_identity_and_budget_required(self):
        for section in ('bindings', 'resources', 'workload'):
            bindings, review = self.review()
            for key in list(review[section]):
                changed = dict(review, **{section: {k:v for k,v in review[section].items() if k != key}})
                with self.subTest(section=section, key=key):
                    with self.assertRaises(ValueError): validate(changed, bindings)

    def test_changed_sha_stops(self):
        bindings, review = self.review()
        review['bindings']['training_package_sha256'] = 'd'*64
        with self.assertRaises(ValueError): validate(review, bindings)

    def archive(self, names, contents):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)/'inner.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, content in zip(names, contents): z.writestr(name, content)
        return path

    def test_exact_archive(self):
        body = b'print(1)\n'
        digest = hashlib.sha256(body).hexdigest()
        path = self.archive(['entry.py'], [body])
        self.assertEqual(check_archive(path, {'entry.py':digest}), {'entry.py':digest})

    def test_reject_missing_extra_and_changed(self):
        digest = hashlib.sha256(b'old').hexdigest()
        for names, contents in [([], []), (['entry.py','extra'], [b'old', b'x']), (['entry.py'], [b'new'])]:
            with self.subTest(names=names):
                with self.assertRaises(ValueError): check_archive(self.archive(names, contents), {'entry.py':digest})

    def test_reject_unsafe_or_duplicate_members(self):
        for names in [['../escape'], ['/absolute'], ['C:/escape'], ['dir\\escape'], ['entry.py','entry.py']]:
            with self.subTest(names=names):
                path = self.archive(names, [b'x']*len(names))
                with self.assertRaises(ValueError): check_archive(path, {name:hashlib.sha256(b'x').hexdigest() for name in names})

    def test_partial_weights_stay_remote_but_reports_do_not(self):
        for name in ('rank0.checkpoint.pt','rank1.checkpoint.pt.tmp','data.npz','model.pth.tmp'):
            with self.subTest(name=name): self.assertTrue(remote_weight(Path(name)))
        for name in ('rank0.checkpoint_index.json','.rank1.json.unique.tmp','rank0.events.jsonl'):
            with self.subTest(name=name): self.assertFalse(remote_weight(Path(name)))

    def test_real_queue_can_contain_multiple_json_documents(self):
        raw = '  {"data": [{"jobId": "1"}]}\n\n{"data": [{"jobId": "2"}]}\n'
        self.assertEqual([x['data'][0]['jobId'] for x in documents(raw)], ['1','2'])
        with self.assertRaises(ValueError): list(documents(raw+'truncated'))

    def test_failed_run_keeps_empty_corrupt_and_hidden_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'job_id.txt').write_text('123\n')
            output = root/'training_output'
            output.mkdir()
            records = {'rank0.json':b'', 'rank1.json':b'{"status":',
                       '.rank0.json.unique.tmp':b'{', 'rank0.checkpoint.pt.tmp':b'partial weight'}
            for name, raw in records.items(): (output/name).write_bytes(raw)
            row = dict(jobId='123',state='FAILED',jobExitCode=1,
                       resGroups=[dict(nodeResUsages=[dict(pids='-')])])
            query = subprocess.CompletedProcess([],0,json.dumps({'data':{'successData':[row]}}).encode(),b'')
            with patch.object(collect_evidence,'check_root'), patch.object(collect_evidence,'verify_prepared',side_effect=ValueError('drift')), \
                    patch.object(collect_evidence.subprocess,'run',return_value=query):
                collect_evidence.collect(root)
            with zipfile.ZipFile(root/'JOB_123_full_evidence.zip') as z:
                for name in list(records)[:3]: self.assertEqual(z.read('training_output/'+name),records[name])
                self.assertNotIn('training_output/rank0.checkpoint.pt.tmp',z.namelist())
                index = json.loads(z.read('COLLECTION_S00.json'))
                self.assertIn('drift',index['source_status'])
                self.assertEqual(index['remote_only'],['training_output/rank0.checkpoint.pt.tmp'])
                self.assertEqual(index['files']['training_output/rank0.checkpoint.pt.tmp']['sha256'],
                                 hashlib.sha256(b'partial weight').hexdigest())


if __name__ == '__main__': unittest.main()
