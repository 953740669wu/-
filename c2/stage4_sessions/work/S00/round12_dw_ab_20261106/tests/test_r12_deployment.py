"""LOCAL_FIXTURE only: chain completeness/fail-stop and exact release binding."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import r12_outcome as outcome
import review_gate
from prepare import RESOURCES

class ChainTests(unittest.TestCase):
    def fixture(self):
        common=dict(source_manifest_sha256='a'*64,host='fixture',job_id='42',cpu36=dict(receipt=dict(selected=list(range(36))),errors=[]),runtime=dict(backend='kml',libraries=[dict(path='KML',sha256='b'*64)],libraries_after=[dict(path='KML',sha256='b'*64)]),imports={r:dict(sha256=s) for r,s in outcome.IMPORTS.items()})
        target=dict(copy.deepcopy(common),protocol=outcome.TARGET_PROTOCOL,phase='target_screen',status=outcome.TARGET_SUCCESS,metrics=[dict(name='actual_KML_target.output',passed=True)],native=dict(baseline=dict(native_calls=1,target_full=1,target_tiles=0,original_type='_FuncPtr'),candidate=dict(native_calls=2,target_full=0,target_tiles=2,original_type='_FuncPtr')))
        phases={'target':target}
        for phase in ('strict','perf_baseline','perf_candidate'):
            strict=phase=='strict';count=5 if strict else 25;roles=['baseline','candidate'] if strict else [phase[5:]]
            steps=[]
            for i in range(1,count+1):
                for role in roles:
                    steps.append(dict(role=role,step=i,adamw_step=i,batch_size=64,frame_indices=list(range((i-1)*64,i*64)),frame_ids=[str(n) for n in range((i-1)*64,i*64)],mask_sha256=str(i),sampled=not strict and i>=6,losses=dict(total=1.,voltage=.8,coarse=.2),kml_calls=149,native_sgemm_calls=149 if role=='baseline' else 161,target_logical_gemm=12,target_native_full=12 if role=='baseline' else 0,target_native_tiles=0 if role=='baseline' else 24,dispatch_hits=0 if role=='baseline' else 12))
            phases[phase]=dict(copy.deepcopy(common),protocol=outcome.PROTOCOL,phase='strict' if strict else 'perf',variant=None if strict else phase[5:],engineering_only=True,status=outcome.STRICT_SUCCESS if strict else outcome.PERF_SUCCESS,descriptor_sha256='c'*64,planned_updates=count,completed_updates=count,consumed_frames=count*64,optimizer_updates_total=len(steps),steps=steps,metrics=[dict(name='fixture_numeric',passed=True)],initialization={r:dict(initial_weights_sha256='d'*64,parameters=37995777,train_seed=0) for r in roles},normalization=dict(scope='train'),recovery=dict(status='PASS_NO_EXTRA_UPDATE',extra_updates=0,parameters_exact=True,optimizer_exact=True,rng_exact=True,cursor_exact=True,identity_exact=True),checkpoint=dict(sha256='e'*64))
        return phases

    def test_complete_exact60_updates_and_original_native_counts(self):
        result=outcome.validate(self.fixture());self.assertTrue(result['complete']);self.assertEqual(result['full_model_updates'],60)

    def test_target_fail_preserved_no_later_stage(self):
        p=self.fixture();p['target']['status']='FAIL_CLOSE_FIXED_CANDIDATE';p={k:v for k,v in p.items() if k=='target'}
        result=outcome.validate(p);self.assertFalse(result['complete']);self.assertEqual(result['failure_stage'],'target');self.assertFalse(result['errors'])

    def test_later_execution_after_gate_failure_rejected(self):
        p=self.fixture();p['strict']['status']='FAIL_STOP_NO_RETRY';self.assertTrue(outcome.validate(p)['errors'])

    def test_missing_phase_or_shortened25_never_complete(self):
        p=self.fixture();del p['perf_candidate'];self.assertFalse(outcome.validate(p)['complete'])
        p=self.fixture();p['perf_baseline']['completed_updates']=5;self.assertFalse(outcome.validate(p)['complete'])

    def test_candidate_native161_and_dispatch24_required(self):
        for field,bad in [('native_sgemm_calls',149),('target_native_tiles',12),('dispatch_hits',0)]:
            p=self.fixture();p['perf_candidate']['steps'][0][field]=bad;self.assertFalse(outcome.validate(p)['complete'])

    def test_job_cpu_source_library_import_mismatch(self):
        for change in [lambda p:p['strict'].update(job_id='43'),lambda p:p['perf_candidate']['cpu36']['receipt'].update(selected=list(range(38))),lambda p:p['perf_baseline'].update(source_manifest_sha256='f'*64),lambda p:p['strict']['runtime'].update(libraries_after=[]),lambda p:p['perf_candidate']['imports']['candidate'].update(sha256=outcome.IMPORTS['baseline'])]:
            p=self.fixture();change(p);self.assertFalse(outcome.validate(p)['complete'])

    def test_original_numeric_failure_or_restore_failure_blocks_completion(self):
        p=self.fixture();p['strict']['metrics'][0]['passed']=False;self.assertFalse(outcome.validate(p)['complete'])
        p=self.fixture();p['perf_candidate']['recovery']['extra_updates']=1;self.assertFalse(outcome.validate(p)['complete'])

    def test_frame_mask_init_pair_identity_required(self):
        for change in [lambda p:p['perf_candidate']['steps'][0]['frame_indices'].reverse(),lambda p:p['perf_candidate']['steps'][0].update(mask_sha256='wrong'),lambda p:p['perf_candidate']['initialization']['candidate'].update(initial_weights_sha256='wrong')]:
            p=self.fixture();change(p);self.assertFalse(outcome.validate(p)['complete'])

    def test_new_review_all_sha_and_workload_bindings_required(self):
        bindings={k:'a'*64 for k in review_gate.BINDING_KEYS};r=dict(decision='PASS_FOR_ENGINEERING_R12_AB',review_complete=True,bindings=bindings,resources=RESOURCES,workload=review_gate.WORKLOAD)
        review_gate.validate(r,bindings)
        for key in review_gate.BINDING_KEYS:
            bad=dict(bindings);bad[key]='b'*64
            with self.assertRaises(ValueError):review_gate.validate(r,bad)
        r['workload']=dict(review_gate.WORKLOAD,max_full_encoder_updates=61)
        with self.assertRaises(ValueError):review_gate.validate(r,bindings)

if __name__=='__main__':unittest.main(verbosity=2)
