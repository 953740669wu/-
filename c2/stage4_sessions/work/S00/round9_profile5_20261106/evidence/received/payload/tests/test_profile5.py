"""LOCAL_FIXTURE: profiler arithmetic, sampling, event/file bounds and isolation."""
import copy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import engineering_training as baseline
import profile_probe as probe
from test_engineering_native import TinyEncoder


class ProbeTests(unittest.TestCase):
    def test_five_updates_exact_arithmetic_rng_and_adamw(self):
        torch.manual_seed(0);np.random.seed(0);random.seed(0)
        model=TinyEncoder();other=copy.deepcopy(model)
        opt=baseline.optimizer(torch,model);ref_opt=baseline.optimizer(torch,other)
        part=dict(v=np.arange(10*208,dtype=np.float32).reshape(10,208)/1000,
                  y0=np.ones((10,1,64,64),np.float32))
        angles=torch.zeros(208,4);records=[]
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            session=probe.Probe(torch,Path(tmp));rng=baseline.rng_state(torch)
            for step in range(1,6):
                indices=[2*(step-1),2*step-1];values=baseline.batch(torch,part,indices,angles)
                cloned=[x.clone() for x in values];mask=torch.rand(2,208)<.5
                reference=baseline.train_step(torch,other,ref_opt,cloned,mask)
                got,record=session.run(step,model,opt,values,mask);records.append(record)
                self.assertTrue(baseline.exact(torch,reference,got))
                self.assertTrue(baseline.exact(torch,model.state_dict(),other.state_dict()))
                self.assertTrue(baseline.exact(torch,opt.state_dict(),ref_opt.state_dict()))
                baseline.validate_update(torch,model,opt,values,step)
            self.assertEqual([x['sampled'] for x in records],[False,False,True,True,True])
            self.assertEqual(len(list(Path(tmp).glob('trace_step_*.json'))),3)
            for record in records[2:]:
                self.assertEqual(set(record['phase_seconds']),set(probe.PHASES))
                self.assertLessEqual(record['trace']['bytes'],probe.TRACE_BYTES)
                self.assertLessEqual(record['events'],probe.MAX_EVENTS)
            # RNG effect comes solely from the five identical caller-generated masks.
            after=baseline.rng_state(torch);baseline.restore_rng(torch,rng)
            for _ in range(5):torch.rand(2,208)
            self.assertTrue(baseline.exact(torch,after,baseline.rng_state(torch)))
            from check_equivalence import compare
            progress=dict(epoch_order=list(range(10)),cursor=10,optimizer_updates=5,planned_updates=5)
            identity=dict(source='LOCAL_FIXTURE',data='NO_REAL_DATA',config=dict(profile_updates=5))
            normalization=dict(image_scale=1.,fit_partition='train')
            checkpoint=baseline.save_checkpoint(torch,Path(tmp)/'checkpoints/final.pt',model,opt,identity,progress,normalization)
            recovered=baseline.verify_restore(torch,checkpoint,model,opt,TinyEncoder,identity,progress,normalization,
                baseline.batch(torch,part,[0,1],angles),compare)
            self.assertEqual(recovered['status'],'PASS_NO_EXTRA_UPDATE');self.assertEqual(recovered['extra_updates'],0)

    def test_unsupported_profiler_fails_without_backend_fallback(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            with patch.object(torch.profiler,'supported_activities',return_value=set()):
                with self.assertRaises(probe.UnsupportedProfiler):probe.Probe(torch,Path(tmp))

    def test_trace_count_and_size_bounds(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            p=Path(tmp)/'too_large.json'
            with self.assertRaises(probe.ProfileLimit):probe.write_bounded(p,{'text':'x'*100},10)
            self.assertFalse(p.exists())
            with self.assertRaises(probe.ProfileLimit):probe.check_event_count(probe.MAX_EVENTS+1)
            self.assertEqual(probe.check_event_count(probe.MAX_EVENTS),None)

    def test_missing_cpu_events_and_out_of_order_stop(self):
        import types
        model=TinyEncoder();opt=baseline.optimizer(torch,model)
        values=(torch.ones(2,208),torch.ones(2,1,64,64),torch.zeros(2,208,4),torch.zeros(2,208))
        mask=torch.ones(2,208,dtype=torch.bool)
        fake=types.SimpleNamespace(__enter__=lambda:None,__exit__=lambda *args:None,events=lambda:[])
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            session=probe.Probe(torch,Path(tmp))
            with self.assertRaises(probe.ProfileLimit):session.run(2,model,opt,values,mask)
            session.run(1,model,opt,values,mask);session.run(2,model,opt,values,mask)
            with patch.object(torch.profiler,'profile',return_value=fake):
                with self.assertRaises(probe.UnsupportedProfiler):session.run(3,model,opt,values,mask)
            self.assertEqual(opt.state[next(model.parameters())]['step'].item(),3)
            self.assertFalse(list(Path(tmp).glob('trace_step_*.json')))

    def test_kml_marker_delegates_exactly_and_is_bounded(self):
        import types
        calls=[];module=types.SimpleNamespace(gemm=lambda a,b:calls.append((a,b)) or a+b)
        original=module.gemm
        with probe.mark_kml(torch,module) as state:
            self.assertEqual(module.gemm(3,4),7);self.assertEqual(state['calls'],1)
        self.assertIs(module.gemm,original);self.assertEqual(calls,[(3,4)])
        with patch.object(probe,'MAX_KML_MARKERS',1):
            with self.assertRaises(probe.ProfileLimit):
                with probe.mark_kml(torch,module):module.gemm(1,2);module.gemm(3,4)
        self.assertIs(module.gemm,original)

    def test_fixed_data_identity_and_frame_mask_drift_rejected(self):
        reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())
        import profile_contract
        description=dict(corpus=copy.deepcopy(reference['corpus']),train=copy.deepcopy(reference['units']))
        profile_contract.check_data(description,reference)
        description['train'][0]['npz_sha256']='0'*64
        with self.assertRaises(ValueError):profile_contract.check_data(description,reference)
        row=copy.deepcopy(reference['steps'][0]);profile_contract.check_step_identity(1,row['frame_indices'],row['frame_ids_sha256'],row['mask_sha256'],reference)
        with self.assertRaises(ValueError):profile_contract.check_step_identity(1,row['frame_indices'],'0'*64,row['mask_sha256'],reference)
        with self.assertRaises(ValueError):profile_contract.check_step_identity(6,[],None,None,reference)


if __name__=='__main__':
    torch.set_num_threads(36);assert torch.get_num_threads()==36
    print('LOCAL_FIXTURE_SMALL_NATIVE_TORCH36; NOT C2/KML/FULL ENCODER',flush=True)
    unittest.main(verbosity=2)
