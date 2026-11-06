"""Fail-fast LOCAL_FAKE_CBLAS screening. No real KML or full Encoder."""
import copy
import ctypes
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from check_equivalence import compare
M,N,K,TILE=512,2048,13312,1024


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert m._lib is None,'local fixture must not load KML'
    return m


def view(pointer,rows,cols,ld):
    span=(rows-1)*ld+cols
    buffer=(ctypes.c_float*span).from_address(pointer)
    return torch.frombuffer(buffer,dtype=torch.float32).as_strided((rows,cols),(ld,1))


def attach(module,mode='math'):
    calls=[]
    def native(*args):
        calls.append(args);layout,ta,tb,m,n,k,alpha,ap,lda,bp,ldb,beta,cp,ldc=args
        assert layout==101 and alpha==1. and beta in (0.,1.)
        c=view(cp,m,n,ldc)
        if mode=='pattern':
            # ABI-only output with unique row/column values; do not read giant inputs.
            offset=(cp-native.output_pointer)//4
            values=torch.arange(m,dtype=torch.float32)[:,None]*N+torch.arange(n,dtype=torch.float32)[None,:]+offset+1
        else:
            a=view(ap,k if ta==112 else m,m if ta==112 else k,lda)
            b=view(bp,n if tb==112 else k,k if tb==112 else n,ldb)
            values=(a.t() if ta==112 else a)@(b.t() if tb==112 else b)
        if beta==0:c.copy_(values)
        else:c.mul_(beta).add_(values)
    native.output_pointer=0
    module._lib=object();module._sgemm=native
    return calls,native


class TileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(36);torch.manual_seed(2026)
        cls.ref=load('r12_ref',ROOT/'baseline/kml_ops.py');cls.cand=load('r12_candidate',ROOT/'candidate/kml_ops.py')
        cls.a=torch.randn(K,M)*.01;cls.b=torch.randn(K,N)*.01;cls.metrics=[];cls.call_proof=[]

    def test_01_target_abi_offsets_leading_dimensions_bounds(self):
        calls,native=attach(self.cand,'pattern');guard=256
        backing=torch.full((M*N+2*guard,),-123456.,dtype=torch.float32);c=backing[guard:guard+M*N].view(M,N)
        native.output_pointer=c.data_ptr();a_before=self.a.clone();b_before=self.b.clone();original_empty=torch.empty
        def output(*shape,**kw):
            self.assertEqual(shape,(M,N));self.assertFalse(kw);return c
        with patch.object(self.cand.torch,'empty',side_effect=output):got=self.cand.gemm(self.a,self.b,ta=True)
        self.assertIs(got,c);self.assertEqual(len(calls),2)
        for j,args in zip((0,TILE),calls):
            expected=(101,112,111,M,TILE,K,1.,self.a.data_ptr(),M,self.b.data_ptr()+j*4,N,0.,c.data_ptr()+j*4,N)
            self.assertEqual(args,expected);self.assertLess((K-1)*N+j+TILE-1,self.b.numel())
            self.assertLess((M-1)*N+j+TILE-1,c.numel())
        self.assertTrue(torch.equal(c,torch.arange(M*N,dtype=torch.float32).reshape(M,N)+1))
        self.assertTrue((backing[:guard]==-123456.).all() and (backing[-guard:]==-123456.).all())
        self.assertTrue(torch.equal(self.a,a_before) and torch.equal(self.b,b_before))
        self.assertNotEqual(c.untyped_storage().data_ptr(),self.a.untyped_storage().data_ptr())
        self.assertNotEqual(c.untyped_storage().data_ptr(),self.b.untyped_storage().data_ptr())
        self.call_proof.append(dict(scope='FAKE_ABI_TARGET_NO_GEMM_MATH',tile_width=1024,full_k=K,
            native_calls=2,B_offsets_bytes=[0,4096],C_offsets_bytes=[0,4096],lda=M,ldb=N,ldc=N,canaries=True,inputs_unchanged=True))

    def test_02_fallback_alias_alignment(self):
        calls,native=attach(self.cand,'pattern');out=torch.empty(M,N);native.output_pointer=out.data_ptr()
        self.cand.gemm(self.a,self.b,ta=True,out=out);self.assertEqual(len(calls),1)
        calls.clear();self.cand.gemm(self.a,self.b,ta=True,out=out,beta=1.);self.assertEqual(len(calls),1)
        calls.clear();self.cand.gemm(self.a,self.b,ta=True,beta=1.);self.assertEqual(len(calls),1)
        calls.clear();self.cand.gemm(self.a[:,:256].contiguous(),self.b,ta=True);self.assertEqual(len(calls),1)
        with self.assertRaises(AssertionError):self.cand.gemm(self.a.t(),self.b,ta=True)
        calls.clear();alias=self.a.reshape(-1)[:M*N].view(M,N)
        with patch.object(self.cand.torch,'empty',return_value=alias):
            with self.assertRaises(AssertionError):self.cand.gemm(self.a,self.b,ta=True)
        self.assertFalse(calls)
        class Misaligned:
            def __getattr__(this,key):return getattr(self.a,key)
            def data_ptr(this):return self.a.data_ptr()+2
        with self.assertRaises(AssertionError):self.cand.gemm(Misaligned(),self.b,ta=True)
        self.assertFalse(calls)

    def test_03_full_target_native_substitute_output(self):
        values=[]
        for module in (self.ref,self.cand):
            calls,_=attach(module);values.append(module.gemm(self.a,self.b,ta=True))
            self.assertEqual(len(calls),1 if module is self.ref else 2)
        compare(torch,'target.output',values[0],values[1],'tensor',self.metrics)

    def test_04_target_linear_gradients_and_bias(self):
        torch.manual_seed(2026);x=torch.randn(K,N)*.05;w=torch.randn(M,N)*.01;b=torch.randn(M)*.01;gy=torch.randn(K,M)*.001
        results=[]
        for module in (self.ref,self.cand):
            calls,_=attach(module);xx=x.clone().requires_grad_();ww=w.clone().requires_grad_();bb=b.clone().requires_grad_()
            out=module._LinearFn.apply(xx,ww,bb);out.backward(gy)
            results.append((out.detach(),xx.grad,ww.grad,bb.grad))
            self.assertEqual(len(calls),3 if module is self.ref else 4)
        for name,a,b in zip(('linear.output','linear.input_grad','linear.weight_grad','linear.bias_grad'),*results):
            compare(torch,name,a,b,'tensor',self.metrics)

    def test_05_five_continuous_adamw(self):
        torch.manual_seed(2026);initial=torch.randn(M,N)*.01;results=[]
        for module in (self.ref,self.cand):
            attach(module);p=torch.nn.Parameter(initial.clone());opt=torch.optim.AdamW([p],lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=.01);steps=[]
            for step in range(1,6):
                opt.zero_grad(set_to_none=True);p.grad=module.gemm(self.a*(1+step/100),self.b,ta=True);opt.step()
                self.assertEqual(opt.state[p]['step'].item(),step)
                steps.append(dict(grad=p.grad.clone(),param=p.detach().clone(),delta=p.detach()-initial,state=copy.deepcopy(opt.state[p])))
            results.append(steps)
        for step,(a,b) in enumerate(zip(*results),1):
            for name in ('grad','param','delta'):compare(torch,f'step{step}.{name}',a[name],b[name],'tensor',self.metrics)
            for name in a['state']:compare(torch,f'step{step}.state.{name}',a['state'][name],b['state'][name],
                                           'exact' if name=='step' else 'state',self.metrics)

    @classmethod
    def tearDownClass(cls):
        (ROOT/'evidence/native_screen.json').write_text(json.dumps(dict(scope='LOCAL_FAKE_CBLAS_NATIVE_MATMUL_NOT_KML',
            metrics=cls.metrics,abi=cls.call_proof),indent=2)+'\n')


if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
