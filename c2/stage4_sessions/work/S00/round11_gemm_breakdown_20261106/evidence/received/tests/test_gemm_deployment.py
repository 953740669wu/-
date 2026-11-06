"""LOCAL_FIXTURE: new GEMM collection semantics and review decisions only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gemm_outcome as g
import review_gate as review
from prepare import RESOURCES


class GemmDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'evidence');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'payload/outputs/gemm_42';self.run.mkdir(parents=True)

    def write(self,path,value):path.write_text(json.dumps(value),encoding='utf-8')

    def fixture(self):
        summaries=[];steps=[]
        for step in range(1,6):
            sample=None
            if step>=3:
                calls=[]
                for i in range(1,150):
                    start=1000*i
                    calls.append(dict(step=step,call_index=i,thread_id=42,parent_call_index=None,role='forward',linear_context='forward',
                        a=dict(shape=[2,4],stride=[4,1],dtype='torch.float32',contiguous=True),b=dict(shape=[3,4],stride=[4,1],dtype='torch.float32',contiguous=True),
                        ta=False,tb=True,beta=1.,m=2,n=3,k=4,output=dict(shape=[2,3],stride=[3,1],dtype='torch.float32',contiguous=True,aliases_a_storage=False,aliases_b_storage=False,is_given_out=True),
                        native_calls=1,ctypes_thread_id=42,sgemm=dict(layout=101,transa=111,transb=112,m=2,n=3,k=4,alpha=1.,lda=4,ldb=4,beta=1.,ldc=3),gemm_start_ns=start,gemm_end_ns=start+100,gemm_wall_ns=100,ctypes_start_ns=start+10,ctypes_end_ns=start+90,ctypes_wall_ns=80,outer_minus_ctypes_ns=20,
                        observer_before_ns=2,observer_after_ns=2,observer_sgemm_bookkeeping_ns=2,status='COMPLETE'))
                path=self.run/('gemm_step_'+str(step)+'.json');self.write(path,dict(protocol=g.PROTOCOL,step=step,status='COMPLETE',clock='time.perf_counter_ns monotonic',timing_scope='LOCAL_FIXTURE',records=149,calls=calls))
                sample=dict(step=step,status='COMPLETE',records=149,native_calls=149,path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());summaries.append(sample)
            steps.append(dict(step=step,adamw_step=step,batch_size=64,cursor=step*64,kml_calls=149,gemm_sample=sample,baseline_loss_metrics=[dict(name=n,passed=True) for n in ('total','voltage','coarse')]))
        app=dict(protocol=g.PROTOCOL,status=g.SUCCESS,engineering_only=True,planned_updates=5,completed_updates=5,consumed_frames=320,
            cpu36=dict(errors=[],checkpoints=[{}]*19),runtime=dict(kml_gemm_calls=843),source_and_data_after='PASS_SAME_FROZEN_IDENTITIES',checkpoint=dict(sha256='a'*64),
            recovery=dict(status='PASS_NO_EXTRA_UPDATE',extra_updates=0,parameters_exact=True,optimizer_exact=True,rng_exact=True,cursor_exact=True,identity_exact=True),
            gemm_observation=dict(baseline_kml_sha256=g.BASELINE,baseline_import=dict(sha256=g.BASELINE),detailed_steps=[3,4,5],samples=summaries))
        self.write(self.run/'result.json',app);self.write(self.run/'EXPOSURE_LEDGER.json',{})
        (self.run/'steps.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in steps),encoding='utf-8')

    def mutate(self,change):
        path=self.run/'gemm_step_3.json';body=json.loads(path.read_text());change(body['calls'][0]);self.write(path,body)
        app=json.loads((self.run/'result.json').read_text());sample=app['gemm_observation']['samples'][0];sample.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());self.write(self.run/'result.json',app)
        steps=[json.loads(s) for s in (self.run/'steps.jsonl').read_text().splitlines()];steps[2]['gemm_sample']=sample
        (self.run/'steps.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in steps))

    def test_complete_three_files_without_profile_traces(self):
        self.fixture();self.assertTrue(g.inspect(self.root,'42')['gemm5_complete'])

    def test_r9_profile_captures_cannot_be_reused(self):
        self.fixture();self.write(self.run/'trace_step_3.json',{})
        self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])

    def test_missing_or_unpaired_native_rejected_after_refreshing_sha(self):
        self.fixture();self.mutate(lambda row:row.update(native_calls=2));self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])

    def test_actual_dimensions_and_interval_mismatch_rejected(self):
        for change in [lambda row:row.update(m=999),lambda row:row.update(ctypes_end_ns=row['gemm_end_ns']+1),lambda row:row.update(ctypes_thread_id=43)]:
            self.fixture();self.mutate(change);self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])

    def test_actual_sgemm_parameters_must_match_outer_metadata(self):
        self.fixture();self.mutate(lambda row:row['sgemm'].update(lda=999))
        self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])

    def test_role_cannot_be_guessed_from_wrong_context(self):
        self.fixture();self.mutate(lambda row:row.update(linear_context='backward'));self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])

    def test_missing_or_oversized_detail_not_truncated(self):
        self.fixture();p=self.run/'gemm_step_4.json';p.unlink();self.assertFalse(g.inspect(self.root,'42')['gemm5_complete'])
        self.fixture();p.write_bytes(b'x'*(1048576+1));self.assertFalse(g.inspect(self.root,'42')['gemm5_complete']);self.assertEqual(p.stat().st_size,1048577)

    def test_failed_states_and_old_profile_success_never_pass(self):
        for status in ['GEMM_OBSERVATION_ERROR','GEMM_LIMIT_EXCEEDED','UNSUPPORTED_GEMM_OBSERVATION','INCOMPLETE','PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE']:
            self.write(self.run/'result.json',dict(protocol=g.PROTOCOL,status=status,error='original'))
            result=g.inspect(self.root,'42');self.assertEqual(result['application_status'],status);self.assertFalse(result['gemm5_complete'])

    def test_exact_new_review_binding_and_decision(self):
        bindings={k:'a'*64 for k in review.BINDING_KEYS};value=dict(decision='PASS_FOR_ENGINEERING_GEMM5',review_complete=True,bindings=bindings,resources=RESOURCES)
        review.validate(value,bindings)
        for key in review.BINDING_KEYS:
            bad=dict(bindings);bad[key]='b'*64
            with self.assertRaises(ValueError):review.validate(value,bad)
        value['decision']='PASS_FOR_ENGINEERING_PROFILE5'
        with self.assertRaises(ValueError):review.validate(value,bindings)


if __name__=='__main__':unittest.main(verbosity=2)
