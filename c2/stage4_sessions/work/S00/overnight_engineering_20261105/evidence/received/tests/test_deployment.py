"""Portable deployment controls; all scheduler/process operations are mocked."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare as p
import review_gate as g
import submit_once as s
import owned_processes as o
import collect_evidence as c
import run_job as r


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'evidence')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_review_all_exact_bindings_and_resources(self):
        bindings={k:'a'*64 for k in g.BINDING_KEYS}
        review=dict(decision='PASS_FOR_ENGINEERING_PILOT',review_complete=True,bindings=bindings,resources=p.RESOURCES)
        g.validate(review,bindings)
        for key in g.BINDING_KEYS:
            wrong=dict(bindings);wrong[key]='b'*64
            with self.assertRaises(ValueError):g.validate(review,wrong)
        review['review_complete']=False
        with self.assertRaises(ValueError):g.validate(review,bindings)

    def test_fail_blocked_or_resource_expansion_not_approval(self):
        bindings={k:'a'*64 for k in g.BINDING_KEYS}
        for decision in ['FAIL','BLOCKED','PASS']:
            with self.assertRaises(ValueError):g.validate(dict(decision=decision,review_complete=True,bindings=bindings,resources=p.RESOURCES),bindings)
        bad=dict(p.RESOURCES,job_seconds=901)
        with self.assertRaises(ValueError):g.validate(dict(decision='PASS_FOR_ENGINEERING_PILOT',review_complete=True,bindings=bindings,resources=bad),bindings)

    def test_resource_command_and_pinned_review_argument(self):
        cmd=s.command(self.root,'a'*64)
        self.assertIn('cpu=38,mem=24576MB',cmd);self.assertIn('mem=24576MB',cmd)
        self.assertIn('numa[count=1,distribution=pack]',cmd)
        self.assertEqual(cmd[cmd.index('-T')+1],'900');self.assertEqual(cmd[-1],'a'*64)

    def test_submit_failure_and_timeout_never_repeated(self):
        for timeout in [False,True]:
            with self.subTest(timeout=timeout):
                root=self.root/str(timeout);root.mkdir()
                effect=subprocess.TimeoutExpired('dsub',10,output=b'partial',stderr=b'err') if timeout else None
                with mock.patch.object(s,'check_root'),mock.patch.object(s,'verify_prepared'), \
                     mock.patch.object(s,'check_review',return_value='a'*64), \
                     mock.patch.object(s.subprocess,'run',side_effect=effect,return_value=subprocess.CompletedProcess([],7,b'failure',b'denied')) as run:
                    with self.assertRaises((RuntimeError,subprocess.TimeoutExpired)):s.submit(root)
                    with self.assertRaises(FileExistsError):s.submit(root)
                self.assertEqual(run.call_count,1)
                self.assertTrue((root/'submission.stdout').exists())

    def test_incomplete_review_never_creates_submission_marker(self):
        with mock.patch.object(s,'check_root'),mock.patch.object(s,'verify_prepared'), \
             mock.patch.object(s,'check_review',side_effect=ValueError('BLOCKED')), \
             mock.patch.object(s.subprocess,'run') as run:
            with self.assertRaises(ValueError):s.submit(self.root)
        self.assertFalse((self.root/'submit_once.marker').exists());run.assert_not_called()

    def test_prepared_source_drift_rejected(self):
        for name in ('ENGINEERING_DESCRIPTOR.json','INTERFACE.json','code.zip','source.py'):(self.root/name).write_bytes(name.encode())
        pins=dict(descriptor_sha256=p.sha(self.root/'ENGINEERING_DESCRIPTOR.json'),interface_sha256=p.sha(self.root/'INTERFACE.json'),code_archive='code.zip',code_package_sha256=p.sha(self.root/'code.zip'))
        p.save(self.root/'PINNED_INPUTS.json',pins)
        p.save(self.root/'ARTIFACT_SHA256.json',{'source.py':p.sha(self.root/'source.py')})
        p.save(self.root/'pre_submit_checks.json',dict(payload_files={}))
        p.verify_prepared(self.root);(self.root/'source.py').write_bytes(b'drift')
        with self.assertRaises(ValueError):p.verify_prepared(self.root)

    def test_failed_gate_never_starts_training_but_cleans(self):
        libc=mock.Mock();libc.prctl.return_value=0
        with mock.patch.object(r,'check_root'),mock.patch.object(r.sys,'platform','linux'), \
             mock.patch.dict(r.os.environ,CCS_JOB_ID='42',S00_REVIEW_SHA='a'*64), \
             mock.patch.object(r.ctypes,'CDLL',return_value=libc), \
             mock.patch.object(r.signal,'SIGALRM',14,create=True),mock.patch.object(r.signal,'ITIMER_REAL',0,create=True), \
             mock.patch.object(r.signal,'setitimer',create=True),mock.patch.object(r.signal,'signal'), \
             mock.patch.object(r,'check_review'),mock.patch.object(r,'verify_prepared',return_value={}), \
             mock.patch.object(r,'run_phase',side_effect=ValueError('bad allocation')) as run, \
             mock.patch.object(r,'cleanup',return_value=dict(all_reaped=True)) as clean:
            self.assertEqual(r.main(self.root),2)
        self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[2],'gate');self.assertEqual(clean.call_count,1)
        self.assertEqual(json.loads((self.root/'job_evidence/SUMMARY.json').read_text())['status'],'FAIL_STOP_NO_RETRY')

    def test_actual_frozen_engineering_entry_environment_wiring(self):
        import os
        import zipfile
        delivered=Path(__file__).resolve().parents[1];pins=p.pinned(delivered)
        with zipfile.ZipFile(delivered/pins['code_archive']) as z:entry=z.read(pins['entrypoint']).decode()
        for name in pins['entry_environment']:self.assertIn('${'+name,entry)
        libc=mock.Mock();libc.prctl.return_value=0
        def phase(root,owner,label,argv,deadline,**kw):
            if label=='training':
                self.assertEqual(argv[-1],str(root/'payload'/pins['entrypoint']))
                self.assertEqual(os.environ['S02_ENGINEERING_DESCRIPTOR'],str(root/'ENGINEERING_DESCRIPTOR.json'))
                self.assertEqual(os.environ['S02_ENGINEERING_DESCRIPTOR_SHA256'],pins['descriptor_sha256'])
                self.assertNotIn('S02_REAL_DESCRIPTOR',os.environ)
                out=root/'payload/outputs/engineering_42';out.mkdir(parents=True)
                p.save(out/'result.json',dict(protocol='ENGINEERING_REAL_CORPUS_PILOT_V1',engineering_only=True,
                     status='ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE',completed_updates=2))
            return dict(returncode=0)
        with mock.patch.object(r,'check_root'),mock.patch.object(r.sys,'platform','linux'), \
             mock.patch.dict(r.os.environ,{'CCS_JOB_ID':'42','S00_REVIEW_SHA':'a'*64},clear=True), \
             mock.patch.object(r.ctypes,'CDLL',return_value=libc), \
             mock.patch.object(r.signal,'SIGALRM',14,create=True),mock.patch.object(r.signal,'ITIMER_REAL',0,create=True), \
             mock.patch.object(r.signal,'setitimer',create=True),mock.patch.object(r.signal,'signal'), \
             mock.patch.object(r,'check_review'),mock.patch.object(r,'verify_prepared',return_value=pins), \
             mock.patch.object(r,'run_phase',side_effect=phase) as run, \
             mock.patch.object(r,'cleanup',return_value=dict(all_reaped=True)):
            self.assertEqual(r.main(self.root),0)
        self.assertEqual(run.call_count,2)

    def test_descendants_after_setsid_and_reparenting(self):
        owner=o.Owned(10);rows={11:dict(ppid=10,start=1,state='S',session=11),12:dict(ppid=11,start=2,state='S',session=12)}
        owner.update(rows);rows.pop(11);rows[12]['ppid']=10;owner.update(rows)
        self.assertEqual(owner.live(rows),[12]);rows[12]['start']=999;rows[12]['ppid']=1
        self.assertEqual(owner.live(rows),[])

    def test_cleanup_only_shared30_seconds_and_owned_pids(self):
        owner=o.Owned(10);rows={11:dict(ppid=10,start=1,state='S',session=11),99:dict(ppid=1,start=2,state='S',session=99)}
        now=[0.0]
        with mock.patch.object(o,'process_table',return_value=rows),mock.patch.object(o,'reap',return_value=[]), \
             mock.patch.object(o.time,'monotonic',side_effect=lambda:now[0]), \
             mock.patch.object(o.time,'sleep',side_effect=lambda x:now.__setitem__(0,now[0]+x)), \
             mock.patch.object(o.signal,'SIGKILL',9,create=True),mock.patch.object(o.os,'kill') as kill:
            receipt=o.cleanup(owner,30)
        self.assertLessEqual(now[0],30.001)
        self.assertEqual([x.args[0] for x in kill.call_args_list],[11,11])
        self.assertFalse(receipt['all_reaped'])

    def test_terminal_failure_missing_result_still_archived(self):
        (self.root/'job_id.txt').write_text('42')
        p.save(self.root/'EXPOSURE_LEDGER_INITIAL.json',dict(units=[dict(unit='reserved')]))
        app=self.root/'payload/outputs/run/checkpoints';app.mkdir(parents=True)
        (app/'final.pt').write_bytes(b'opaque checkpoint stays remote')
        raw=json.dumps(dict(data=dict(successData=[dict(jobId='42',state='FAILED',resGroups=[dict(nodeResUsages=[dict(pids='-')])])]))).encode()
        with mock.patch.object(c,'check_root'),mock.patch.object(c,'verify_prepared'), \
             mock.patch.object(c.subprocess,'run',return_value=subprocess.CompletedProcess([],0,raw,b'')):
            receipt=c.collect(self.root)
        import zipfile
        with zipfile.ZipFile(receipt['bundle']) as z:
            index=json.loads(z.read('COLLECTION_S00.json'))
            self.assertNotIn('payload/outputs/run/checkpoints/final.pt',z.namelist())
        self.assertEqual(index['state'],'FAILED');self.assertIn('exactly_one_application_result',index['missing'])
        self.assertEqual(index['files']['payload/outputs/run/checkpoints/final.pt']['sha256'],p.sha(app/'final.pt'))

    def test_missing_runtime_exposure_is_not_fabricated_consumed(self):
        p.save(self.root/'EXPOSURE_LEDGER_INITIAL.json',dict(units=[dict(unit='reserved')]))
        (self.root/'job_evidence').mkdir();(self.root/'job_evidence/training.json').write_text('{}')
        result=c.exposure(self.root)
        self.assertEqual(result['actual_optimizer_consumption'],'UNKNOWN')
        self.assertTrue(result['future_test_exclusion_review_required'])


if __name__=='__main__':unittest.main(verbosity=2)
