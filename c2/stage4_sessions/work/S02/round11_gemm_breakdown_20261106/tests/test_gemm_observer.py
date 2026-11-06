"""LOCAL_FAKE_CBLAS_ONLY: real tensor interface, no actual KML/model run."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import gemm_observer as observer


def fixture():
    spec=importlib.util.spec_from_file_location('fake_cblas_baseline',ROOT/'baseline/kml_ops.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module._lib is None,'fixture requires environment without KML'
    calls=[]
    def native(*args):
        calls.append(args);_,ta,tb,m,n,k,alpha,ap,lda,bp,ldb,beta,cp,ldc=args
        def view(ptr,rows,cols):return torch.frombuffer((ctypes.c_float*(rows*cols)).from_address(ptr),dtype=torch.float32).reshape(rows,cols)
        a=view(ap,k if ta==112 else m,lda);b=view(bp,n if tb==112 else k,ldb);c=view(cp,m,ldc)
        value=(a.t() if ta==112 else a)@(b.t() if tb==112 else b)
        if beta==0:c.copy_(value)
        else:c.mul_(beta).add_(value)
        return None
    module._lib=object();module._sgemm=native
    return module,calls


def saved(module):
    return (module.gemm,module._sgemm,module._LinearFn.__dict__['forward'],module._LinearFn.__dict__['backward'])


class ObserverTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'evidence').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'evidence');self.path=Path(self.temp.name)
        self.module,self.calls=fixture();self.before=saved(self.module)
        self.obs=observer.Observer(self.module,self.path)

    def tearDown(self):
        self.assertEqual(saved(self.module),self.before);self.temp.cleanup()

    def test_once_same_arguments_outputs_gradients_and_rng(self):
        torch.manual_seed(0);random.seed(0);np.random.seed(0)
        x=torch.randn(2,3,8,requires_grad=True);w=torch.randn(12,8,requires_grad=True);b=torch.randn(12,requires_grad=True)
        values=[v.detach().clone().requires_grad_() for v in (x,w,b)]
        expected=self.module._LinearFn.apply(*values);expected.square().mean().backward()
        initial_calls=len(self.calls);rng=torch.get_rng_state().clone();prng=random.getstate();nrng=np.random.get_state()
        with patch.object(observer,'EXPECTED_CALLS',3):
            with self.obs.sample(3):
                got=self.module._LinearFn.apply(x,w,b);got.square().mean().backward()
        self.assertEqual(len(self.calls)-initial_calls,3)
        self.assertTrue(torch.equal(expected,got))
        for a,bb in zip(values,(x,w,b)):self.assertTrue(torch.equal(a.grad,bb.grad))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()));self.assertEqual(prng,random.getstate())
        after=np.random.get_state();self.assertEqual(nrng[0],after[0]);self.assertTrue(np.array_equal(nrng[1],after[1]));self.assertEqual(nrng[2:],after[2:])
        d=json.loads((self.path/'gemm_step_3.json').read_text());rows=d['calls']
        self.assertEqual([r['role'] for r in rows],['forward','dX','dW'])
        self.assertEqual([(r['m'],r['n'],r['k']) for r in rows],[(6,12,8),(6,8,12),(12,8,6)])
        for r in rows:
            self.assertEqual(r['native_calls'],1);self.assertGreaterEqual(r['outer_minus_ctypes_ns'],0)
            self.assertLessEqual(r['gemm_start_ns'],r['ctypes_start_ns']);self.assertLessEqual(r['ctypes_end_ns'],r['gemm_end_ns'])
            self.assertFalse(r['output']['aliases_a_storage'] or r['output']['aliases_b_storage'])
        self.assertEqual(self.calls[:3][0][0:7],self.calls[3:][0][0:7])

    def test_positional_keyword_forms_and_unknown_role(self):
        a=torch.randn(3,4);b=torch.randn(5,4);out=torch.ones(3,5);args_seen=[];original=self.module.gemm
        def spy(*args,**kwargs):args_seen.append((args,kwargs));return original(*args,**kwargs)
        self.module.gemm=spy;before=saved(self.module)
        with patch.object(observer,'EXPECTED_CALLS',1):
            with self.obs.sample(3):result=self.module.gemm(a,b,False,True,out,1.,False)
        self.assertIs(result,out);self.assertEqual(saved(self.module),before)
        self.assertIs(args_seen[0][0][0],a);self.assertIs(args_seen[0][0][1],b)
        self.assertEqual(args_seen[0][0][2:],(False,True,out,1.,False));self.assertEqual(args_seen[0][1],{})
        self.assertEqual(json.loads((self.path/'gemm_step_3.json').read_text())['calls'][0]['role'],'UNKNOWN')
        self.module.gemm=self.before[0]

    def test_exception_restores_all_hooks(self):
        def fail(*args):raise RuntimeError('controlled native failure')
        self.module._sgemm=fail;before=saved(self.module)
        with self.assertRaisesRegex(RuntimeError,'controlled'):
            with self.obs.sample(3):self.module.gemm(torch.ones(2,3),torch.ones(3,4))
        self.assertEqual(saved(self.module),before);self.module._sgemm=self.before[1]
        self.assertEqual(self.obs.samples[0]['status'],'FAILED')

    def test_thread_contexts_do_not_cross(self):
        barrier=threading.Barrier(2);a=torch.ones(2,3);b=torch.ones(3,4)
        def work():barrier.wait();return self.module.gemm(a,b)
        with patch.object(observer,'EXPECTED_CALLS',2):
            with self.obs.sample(3):
                with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:work(),range(2)))
        rows=json.loads((self.path/'gemm_step_3.json').read_text())['calls']
        self.assertEqual(len({r['thread_id'] for r in rows}),2);self.assertEqual([r['call_index'] for r in rows],[1,2])
        self.assertTrue(all(r['parent_call_index'] is None and r['native_calls']==1 for r in rows))
        self.assertTrue(all(torch.equal(v,torch.full((2,4),3.)) for v in values))

    def test_missing_duplicate_or_unscoped_native_rejected(self):
        original=self.module.gemm
        self.module.gemm=lambda a,b:torch.zeros(a.shape[0],b.shape[1])
        with self.assertRaisesRegex(observer.ObservationError,'exactly one'):
            with self.obs.sample(3):self.module.gemm(torch.ones(2,3),torch.ones(3,4))
        self.module.gemm=original
        with self.assertRaisesRegex(observer.ObservationError,'same-thread'):
            with self.obs.sample(4):self.module._sgemm()
        native=self.module._sgemm
        def duplicate(*args):native(*args);self.module._sgemm(*args)
        self.module._sgemm=duplicate
        with self.assertRaisesRegex(observer.ObservationError,'multiple'):
            with self.obs.sample(5):self.module.gemm(torch.ones(2,3),torch.ones(3,4))
        self.module._sgemm=native

    def test_limits_count_mismatch_and_byte_limit(self):
        a=torch.ones(2,3);b=torch.ones(3,4)
        with self.assertRaisesRegex(observer.ObservationError,'expected149'):
            with self.obs.sample(3):self.module.gemm(a,b)
        with patch.object(observer,'MAX_RECORDS',1),patch.object(observer,'EXPECTED_CALLS',2):
            before=len(self.calls)
            with self.assertRaises(observer.ObservationLimit):
                with self.obs.sample(4):self.module.gemm(a,b);self.module.gemm(a,b)
            self.assertEqual(len(self.calls)-before,1)
        with patch.object(observer,'FILE_BYTES',10),patch.object(observer,'EXPECTED_CALLS',1):
            with self.assertRaises(observer.ObservationLimit):
                with self.obs.sample(5):self.module.gemm(a,b)
        self.assertFalse((self.path/'gemm_step_5.json').exists())
        with self.assertRaises(observer.ObservationError):
            with self.obs.sample(1):pass

    def test_unsupported_refuses_without_call_or_fallback(self):
        for name,value in [('_lib',None),('_sgemm',None),('LINEAR_DTYPE',torch.bfloat16)]:
            with patch.object(self.module,name,value):
                with self.assertRaises(observer.UnsupportedObservation):observer.Observer(self.module,self.path)
        with self.assertRaises(observer.UnsupportedObservation):
            with self.obs.sample(3):self.module.gemm(torch.ones(2,3),torch.ones(3,4),acc32=True)
        self.assertFalse(self.calls)

    def test_five_adamw_updates_only_last_three_recorded(self):
        from engineering_training import exact
        from contextlib import nullcontext
        torch.manual_seed(4);initial=[torch.randn(12,8),torch.randn(12)];x=torch.randn(6,8)
        snapshots=[]
        for enabled in (False,True):
            params=[torch.nn.Parameter(v.clone()) for v in initial]
            opt=torch.optim.AdamW(params,lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=.01)
            for step in range(1,6):
                values=x.clone().requires_grad_();opt.zero_grad(set_to_none=True)
                with patch.object(observer,'EXPECTED_CALLS',3):
                    with self.obs.sample(step) if enabled and step>=3 else nullcontext():
                        output=self.module._LinearFn.apply(values,*params);output.square().mean().backward();opt.step()
                self.assertEqual(saved(self.module),self.before)
            snapshots.append(([p.detach().clone() for p in params],opt.state_dict()))
        self.assertTrue(exact(torch,snapshots[0],snapshots[1]))
        self.assertEqual([r['step'] for r in self.obs.samples],[3,4,5]);self.assertEqual(len(list(self.path.glob('gemm_step_*.json'))),3)

    def test_nested_calls_keep_parent_intervals(self):
        original=self.module.gemm;native=self.module._sgemm;inside=False
        def nested(*args):
            nonlocal inside
            if not inside:
                inside=True
                try:self.module.gemm(torch.ones(1,2),torch.ones(2,1))
                finally:inside=False
            return native(*args)
        self.module._sgemm=nested
        with patch.object(observer,'EXPECTED_CALLS',2):
            with self.obs.sample(3):self.module.gemm(torch.ones(2,3),torch.ones(3,4))
        rows=json.loads((self.path/'gemm_step_3.json').read_text())['calls']
        self.assertEqual([r['parent_call_index'] for r in rows],[None,1]);self.module._sgemm=native


if __name__=='__main__':
    torch.set_num_threads(36)
    print('LOCAL_FAKE_CBLAS_ONLY; NO KML/FULL ENCODER/CLUSTER',flush=True)
    unittest.main(verbosity=2)
