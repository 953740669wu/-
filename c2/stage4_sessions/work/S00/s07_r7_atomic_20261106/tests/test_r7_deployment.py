"""LOCAL_FIXTURE: new R7 delivery, diagnostic semantics, ownership and release."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import subprocess
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare
import run_s07_diag_job as job
import stack_inventory as stacks
import review_gate as review
from owned_processes import Owned
import bounded_round_step
import collect_evidence

class R7DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'evidence');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_frozen_r7_exact16_files15_delivery_and_observer(self):
        source=Path(__file__).resolve().parents[1]/prepare.ARCHIVE;shutil.copyfile(source,self.root/prepare.ARCHIVE)
        prepare.unpack(self.root);files=[p for p in (self.root/'payload').rglob('*') if p.is_file()]
        self.assertEqual(len(files),16);manifest=json.loads((self.root/'payload/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['delivery_files']),15);self.assertEqual(prepare.sha(self.root/'payload/candidate/stack_observer.py'),prepare.OBSERVER_SHA)

    def test_old_inner_rejected_without_payload(self):
        (self.root/prepare.ARCHIVE).write_bytes(b'old package')
        with self.assertRaises(ValueError):prepare.unpack(self.root)
        self.assertFalse((self.root/'payload').exists())

    def test_review_expected_resolves_the_current_real_inner_archive(self):
        source=Path(__file__).resolve().parents[1]
        for name in [prepare.ARCHIVE,'SOURCE_MANIFEST.json','OBSERVATION_CONTRACT.md','S07_INTERFACE_READY.json','TASK_CARD.md']:shutil.copyfile(source/name,self.root/name)
        (self.root/review.DEPLOYMENT).write_bytes(b'LOCAL_FIXTURE_OUTER_BYTES')
        (self.root/'ARTIFACT_SHA256.json').write_text('{}')
        self.assertEqual(review.expected(self.root)['inner_package_sha256'],prepare.INNER_SHA)

    def test_88_checks_share_original_consumer(self):
        self.assertEqual([row[2] for row in job.CHECKS],[17,27,16,6,6,16]);self.assertEqual(sum(row[2] for row in job.CHECKS),88)
        self.assertEqual((job.CONSUMER_SECONDS,job.CLEANUP_SECONDS,job.CLOSING_SECONDS),(270,15,15))

    def fixture(self):
        d=self.root/'payload/checks_current_job/watchdog';d.mkdir(parents=True,exist_ok=True)
        selected=[list(range(36)),list(range(38,74))]
        def guard(rank):return dict(calling_affinity=selected[rank],snapshot=dict(complete=True,errors=[],vanished=[],threads=[dict(affinity=selected[rank])]))
        self.dump(d/'manifest.json',dict(allocation=dict(ranks=[dict(selected=s) for s in selected])))
        (d/'supervisor.events.jsonl').write_text(json.dumps(dict(event='supervisor_begin',pid=10))+'\n'+json.dumps(dict(event='proc_helper_started',pid=10,helper_pid=13))+'\n',encoding='utf-8')
        self.dump(d/'participants.json',dict(deadline_ns=30_000_000_000,pids=[11,12],job_id='42',run_id='watchdog',ready_token='x'))
        self.dump(d/'summary.json',dict(supervisor=dict(stack_observation=dict(target_ns=25_000_000_000,sample_stop_ns=27_000_000_000,helper_pid=13,reaped=True,status='EXITED',returncode=0))))
        for rank in (0,1):
            (d/f'rank{rank}.python_stack.txt').write_text('Timeout (0:00:25)!\nThread 0x1:\n  File "x.py", line 10 in init_process_group\n',encoding='utf-8')
            self.dump(d/f'rank{rank}.stack_status.json',dict(status='ARMED',rank=rank,pid=11+rank,job_id='42',run_id='watchdog',target_ns=25_000_000_000,armed_at_ns=1,before_timer_cpu=guard(rank),after_timer_cpu=guard(rank)))
            self.dump(d/f'rank{rank}.installed_python.json',dict(status='RECORDED',files=[dict(module=m,path='/installed/'+m,bytes=10,mtime_ns=1,sha256='a'*64) for m in ('torch.distributed.distributed_c10d','torch.distributed.rendezvous')]))
        self.dump(d/'proc_identity.json',dict(identity=dict(job_id='42',run_id='watchdog',ready_token='x'),targets=[dict(pid=11,ppid=10,sid=11,start_ticks=1),dict(pid=12,ppid=10,sid=12,start_ticks=2)],captured_ns=1))
        self.dump(d/'proc_summary.json',dict(status='RECORDED_AVAILABLE_FIELDS_ONLY',helper_pid=13,target_ns=25_000_000_000,sample_stop_ns=27_000_000_000,sample_started_ns=25_000_000_001,finished_ns=25_000_000_100,ranks=[dict(rank=i,pid=11+i,status='RECORDED',target=dict(identity=dict(pid=11+i,ppid=10,sid=11+i,start_ticks=1+i),affinity=selected[i]),identity_after=dict(identity=dict(pid=11+i,ppid=10,sid=11+i,start_ticks=1+i),affinity=selected[i]),helper_cpu=guard(i)) for i in (0,1)]))
        (d/'proc_fields.jsonl').write_text(''.join(json.dumps(dict(rank=rank,pid=11+rank,field=field,status='OK',text='available'))+'\n' for rank in (0,1) for field in ('wchan','syscall','stack','mountinfo')),encoding='utf-8');(d/'proc_helper.log').write_bytes(b'')
        return d

    def dump(self,path,value):path.write_text(json.dumps(value),encoding='utf-8')

    def test_nonempty_stacks_and_actual_fields_can_be_complete_without_communication_pass(self):
        self.fixture();result=stacks.inspect(self.root);self.assertTrue(result['complete']);self.assertNotIn('communication_passed',result)

    def test_armed_empty_dump_never_proves_stack_written(self):
        d=self.fixture();(d/'rank0.python_stack.txt').write_bytes(b'');self.assertFalse(stacks.inspect(self.root)['complete'])

    def test_exited_helper_with_permission_error_is_incomplete(self):
        d=self.fixture();(d/'proc_fields.jsonl').write_text(json.dumps(dict(rank=0,pid=11,field='stack',status='ERROR',error='PermissionError'))+'\n',encoding='utf-8')
        self.assertFalse(stacks.inspect(self.root)['complete'])

    def test_missing_watchdog_or_wrong_shared_target_is_incomplete(self):
        self.assertFalse(stacks.inspect(self.root)['complete']);d=self.fixture();p=d/'rank1.stack_status.json';row=json.loads(p.read_text());row['target_ns']+=1;self.dump(p,row);self.assertFalse(stacks.inspect(self.root)['complete'])

    def test_owned_helper_across_sessions_and_pid_reuse(self):
        own=Owned(1);rows={2:dict(ppid=1,state='S',session=2,start=10),3:dict(ppid=2,state='S',session=3,start=20),4:dict(ppid=3,state='S',session=4,start=30)};own.update(rows)
        self.assertEqual(own.live(rows),[2,3,4]);rows[4]['start']=31;self.assertEqual(own.live(rows),[2,3]);self.assertEqual(own.identities[4],30)

    def test_review_requires_exact_sha_resources_and_original_criteria(self):
        bindings={k:'a'*64 for k in review.BINDING_KEYS};value=dict(decision='PASS_FOR_S07_R7_ATOMIC',review_complete=True,bindings=bindings,resources=review.RESOURCES,workload=review.WORKLOAD)
        review.validate(value,bindings)
        for key in bindings:
            wrong=dict(bindings);wrong[key]='b'*64
            with self.assertRaises(ValueError):review.validate(value,wrong)
        bad=copy.deepcopy(value);bad['workload']['pg_timeout_seconds']=10
        with self.assertRaises(ValueError):review.validate(bad,bindings)

    def test_late_step_cannot_reset_shared_cleanup_deadline(self):
        (self.root/'job_evidence').mkdir()
        with mock.patch.object(bounded_round_step.time,'monotonic',side_effect=[99.,200.]),mock.patch.object(bounded_round_step,'run_phase',return_value=dict(returncode=0)) as phase,mock.patch.object(bounded_round_step,'cleanup',return_value=dict(all_reaped=True)) as clean:
            bounded_round_step.run_step(self.root,'owned','fixture',['python'],100.,30.)
        self.assertEqual(phase.call_args.args[-1],100.);self.assertEqual(clean.call_args.args[-1],115.)

    def test_terminal_collection_preserves_empty_partial_and_uncleared_pid_evidence(self):
        self.fixture();directory=self.root/'payload/checks_current_job/watchdog';(directory/'rank0.python_stack.txt').write_bytes(b'');(directory/'ready_rank0.json.tmp').write_bytes(b'{partial')
        (self.root/'job_id.txt').write_text('42\n');self.dump(self.root/'pre_submit_checks.json',dict(payload_files={}));self.dump(self.root/'ARTIFACT_SHA256.json',{})
        row=dict(jobId='42',state='FAILED',jobExitCode=1,startTime='2026-11-06T00:00:00Z',endTime='2026-11-06T00:01:00Z',resGroups=[dict(nodeResUsages=[dict(pids='99')])])
        response=subprocess.CompletedProcess([],0,json.dumps(dict(data=dict(successData=[row]))).encode(),b'')
        with mock.patch.object(collect_evidence,'check_root'),mock.patch.object(collect_evidence.subprocess,'run',return_value=response):receipt=collect_evidence.collect(self.root)
        with zipfile.ZipFile(receipt['bundle']) as z:
            self.assertEqual(z.read('payload/checks_current_job/watchdog/ready_rank0.json.tmp'),b'{partial');self.assertEqual(z.read('payload/checks_current_job/watchdog/rank0.python_stack.txt'),b'')
            index=json.loads(z.read('COLLECTION_S00.json'));self.assertFalse(index['scheduler_pids_cleared']);self.assertFalse(index['stack_observation']['complete'])

if __name__=='__main__':unittest.main(verbosity=2)
