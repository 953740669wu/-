"""Native substitute only; the frozen comparator/thresholds are unchanged."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from check_equivalence import compare
OUTPUT=ROOT/'evidence'
BACKEND='native'
RUNTIME=None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class LinearTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if BACKEND=='native':torch.set_num_threads(36)
        assert torch.get_num_threads()==36
        cls.ref=load('s02_frozen',ROOT/'baseline/kml_ops.py');cls.cand=load('s02_candidate',ROOT/'candidate/kml_ops.py')
        assert (cls.ref._lib is None)==(BACKEND=='native') and (cls.cand._lib is None)==(BACKEND=='native'),'backend mismatch'
        assert cls.ref.LINEAR_DTYPE==cls.cand.LINEAR_DTYPE==torch.float32
        if RUNTIME is not None:
            for module in (cls.ref,cls.cand):
                original=module.gemm
                def counted(*args,_original=original,**kw):
                    RUNTIME['kml_gemm_calls']+=1
                    return _original(*args,**kw)
                module.gemm=counted
        cls.metrics=[]

    def pair(self,x,w,b,gy,requires=(True,True,True)):
        outputs=[];witness=[]
        for module in (self.ref,self.cand):
            values=[v.detach().clone(memory_format=torch.preserve_format).requires_grad_(need) if v is not None else None
                    for v,need in zip((x,w,b),requires)]
            originals=[v.detach().clone() if v is not None else None for v in values];calls=[];original=module.gemm
            def observed(a,bb,*args,**kw):
                aa=a.clone();bbb=bb.clone();out=original(a,bb,*args,**kw)
                self.assertTrue(torch.equal(a,aa) and torch.equal(bb,bbb),'GEMM mutated operand')
                self.assertNotEqual(out.untyped_storage().data_ptr(),a.untyped_storage().data_ptr())
                self.assertNotEqual(out.untyped_storage().data_ptr(),bb.untyped_storage().data_ptr())
                calls.append((tuple(a.shape),tuple(bb.shape),args,kw.get('ta',False),kw.get('tb',False),kw.get('beta',0.)))
                return out
            module.gemm=observed
            try:
                out=module._LinearFn.apply(*values);out.backward(gy)
                for value,before in zip(values,originals):
                    if value is not None:self.assertTrue(torch.equal(value.detach(),before))
                outputs.append([out.detach()]+[v.grad if v is not None else None for v in values]);witness.append(calls)
            finally:module.gemm=original
        self.assertEqual(witness[0],witness[1],'GEMM shape/transpose/beta drift')
        for index,(a,b) in enumerate(zip(*outputs)):compare(torch,f'linear.{index}',a,b,'tensor',self.metrics)

    def test_feature_shapes_strides_bias_and_grad_flags(self):
        torch.manual_seed(36)
        for n,i,o in [(416,512,1536),(416,512,512),(416,512,2048),(416,2048,512),(13312,65,512),(13312,512,1)]:
            x=torch.randn(n,i)/10;w=torch.randn(o,i)/10;b=torch.randn(o)/10;gy=torch.randn(n,o)/10
            with self.subTest(shape=(n,i,o)):self.pair(x,w,b,gy)
        x=torch.randn(6,4,8).transpose(0,1);w=torch.randn(12,8);b=torch.randn(12)
        gradients=[torch.randn(4,6,12),torch.randn(6,4,12).transpose(0,1),
                   torch.randn(4,6,24)[...,::2],torch.ones(1,1,12).expand(4,6,12)]
        for gy in gradients:self.pair(x,w,b,gy)
        self.pair(x,w,None,gradients[0],(True,True,False))
        self.pair(x,w,b,gradients[0],(False,True,True))
        self.pair(x,w,b,gradients[0],(True,False,True))
        self.pair(x,w,b,gradients[0],(True,True,False))
        self.pair(torch.randn(10,8),w,b,torch.randn(10,13)[:,:12])

    def test_actual_b64_layout_and_bias_reduction(self):
        torch.manual_seed(9);rows=[]
        contiguous=torch.randn(64,208,512)
        for name,gy in [('contiguous',contiguous),('sequence_batch_swap',contiguous.transpose(0,1)),
                        ('feature_slice',torch.randn(64,208,1024)[...,::2]),
                        ('padded_rows',torch.randn(13312,513)[:,:512])]:
            flattened=gy.reshape(-1,gy.shape[-1]);g=flattened.to(torch.float32).contiguous()
            expected=gy.reshape(-1,gy.shape[-1]).sum(0);got=flattened.sum(0)
            compare(torch,'actual_layout.'+name,expected,got,'tensor',self.metrics)
            self.assertTrue(torch.equal(expected,got))
            rows.append(dict(layout=name,shape=list(gy.shape),stride=list(gy.stride()),
                             reshape_shares_storage=flattened.untyped_storage().data_ptr()==gy.untyped_storage().data_ptr(),
                             reshape_contiguous=flattened.is_contiguous(),g_shares_flattened=g.data_ptr()==flattened.data_ptr()))
        (OUTPUT/'layout_fixture.json').write_text(json.dumps(dict(scope='CONTROLLED_LAYOUT_FIXTURE_NOT_OBSERVED_C2_STRIDES',layouts=rows),indent=2)+'\n')

    def test_repeated_calls_do_not_alias_or_mutate_earlier_outputs(self):
        x=torch.randn(8,16,requires_grad=True);w=torch.randn(32,16,requires_grad=True);b=torch.randn(32,requires_grad=True)
        first=self.cand._LinearFn.apply(x,w,b);snapshot=first.detach().clone()
        second=self.cand._LinearFn.apply(x,w,b)
        self.assertNotEqual(first.untyped_storage().data_ptr(),second.untyped_storage().data_ptr())
        second.sum().backward();self.assertTrue(torch.equal(first.detach(),snapshot))
        first.sum().backward();self.assertTrue(torch.equal(first.detach(),snapshot))

    def test_five_continuous_adamw_states(self):
        torch.manual_seed(2026);x=torch.randn(128,32);target=torch.randn(128,64)
        initial=[torch.randn(64,32)/10,torch.randn(64)/10];results=[]
        for module in (self.ref,self.cand):
            params=[torch.nn.Parameter(v.clone()) for v in initial]
            opt=torch.optim.AdamW(params,lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=.01);steps=[]
            for step in range(1,6):
                xx=x.clone().requires_grad_();opt.zero_grad(set_to_none=True)
                y=module._LinearFn.apply(xx,*params);loss=torch.nn.functional.mse_loss(y,target)
                loss.backward();opt.step()
                self.assertTrue(all(opt.state[p]['step'].item()==step for p in params))
                steps.append(dict(loss=loss.detach().clone(),output=y.detach().clone(),input_grad=xx.grad.clone(),
                    params=[p.detach().clone() for p in params],grads=[p.grad.clone() for p in params],
                    state=copy.deepcopy(opt.state_dict())))
            results.append(steps)
        for step,(a,b) in enumerate(zip(*results),1):
            for k in ('loss','output','input_grad'):compare(torch,f'step{step}.{k}',a[k],b[k],'tensor',self.metrics)
            for k in ('params','grads'):
                for n,(aa,bb) in enumerate(zip(a[k],b[k])):compare(torch,f'step{step}.{k}{n}',aa,bb,'tensor',self.metrics)
            for p,state in a['state']['state'].items():
                for key,value in state.items():compare(torch,f'step{step}.state{p}.{key}',value,b['state']['state'][p][key],
                                                        'exact' if key=='step' else 'state',self.metrics)

    @classmethod
    def tearDownClass(cls):
        import hashlib
        (OUTPUT/'linear_metrics.json').write_text(json.dumps(dict(scope='NATIVE_SUBSTITUTE_NOT_KML' if BACKEND=='native' else 'ACTUAL_KML_LINEAR_ONLY_NOT_FULL_ENCODER',
            imports=[dict(path=str(Path(m.__file__).resolve()),sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()) for m in (cls.ref,cls.cand)],
            actual_kml=BACKEND=='kml',metrics=cls.metrics),indent=2)+'\n')


if __name__=='__main__':unittest.main(verbosity=2)
