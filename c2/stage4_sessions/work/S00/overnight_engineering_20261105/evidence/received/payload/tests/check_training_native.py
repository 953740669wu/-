"""Small synthetic native Torch36 only; no real corpus or full encoder run."""
import copy
from pathlib import Path
import random
import sys
import tempfile
import unittest
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import pilot_training as training
from check_equivalence import compare


class TinyEncoder(torch.nn.Module):
    def __init__(self):
        super().__init__();self.val=torch.nn.Linear(1,4);self.head_v=torch.nn.Linear(4,1);self.head_coarse=torch.nn.Linear(4,256)
    def forward(self,v,a,b,mask):return self.val(v.unsqueeze(-1)).tanh()


class NativeTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(0);np.random.seed(0);random.seed(0)
        self.model=TinyEncoder();self.opt=training.optimizer(torch,self.model)
        self.part=dict(v=np.arange(5*208,dtype=np.float32).reshape(5,208)/1000,
            y0=np.ones((5,1,64,64),np.float32),frame_ids=list(range(5)))
        self.angles=torch.zeros(208,4)

    def test_different_batches_tail_and_continuous_adamw(self):
        identity=id(self.opt);seen=[];masks=[]
        for step,indices in enumerate(([0,1],[2,3],[4]),1):
            values=training.batch(torch,self.part,indices,self.angles)
            mask=torch.rand(len(indices),208)<0.5;masks.append(mask.clone());seen.extend(indices)
            loss=training.train_step(torch,self.model,self.opt,values,mask)
            training.validate_update(torch,self.model,self.opt,values,step)
            self.assertEqual(id(self.opt),identity)
            self.assertTrue(torch.equal(loss['total'],loss['voltage']+loss['coarse']))
        self.assertEqual(seen,list(range(5)));self.assertFalse(torch.equal(masks[0],masks[1]))

    def test_mean_step_matches_original_expression_and_states(self):
        reference=copy.deepcopy(self.model);opt=training.optimizer(torch,reference)
        values=training.batch(torch,self.part,[0,1],self.angles)
        cloned=[x.clone().requires_grad_() if i<2 else x.clone() for i,x in enumerate(values)]
        mask=torch.rand(2,208)<0.5
        got=training.train_step(torch,self.model,self.opt,values,mask)
        v,image,a,b=cloned;h=reference(v,a,b,mask);F=torch.nn.functional
        loss=F.mse_loss(reference.head_v(h)[...,0][mask],v[mask])+F.mse_loss(reference.head_coarse(h.mean(1)),F.adaptive_avg_pool2d(image,16).flatten(1))
        opt.zero_grad();loss.backward();opt.step()
        self.assertTrue(torch.equal(loss,got['total']))
        self.assertTrue(training.exact(torch,self.model.state_dict(),reference.state_dict()))
        self.assertTrue(training.exact(torch,self.opt.state_dict(),opt.state_dict()))

    def test_formal_val_masks_rng_and_parameters_are_unchanged(self):
        before=copy.deepcopy(self.model.state_dict());rng=training.rng_state(torch)
        left=training.evaluate(torch,self.model,self.part,2,self.angles)
        right=training.evaluate(torch,self.model,self.part,2,self.angles)
        self.assertEqual(left,right);self.assertTrue(training.exact(torch,rng,training.rng_state(torch)))
        self.assertTrue(training.exact(torch,before,self.model.state_dict()));self.assertFalse(self.opt.state)
        self.assertEqual(training.evaluate(torch,self.model,None,2,self.angles)['status'],'VAL_NOT_RUN_NO_FORMAL_VAL')

    def test_checkpoint_restores_all_state_cursor_and_rng_without_update(self):
        values=training.batch(torch,self.part,[0,1],self.angles)
        training.train_step(torch,self.model,self.opt,values,torch.rand(2,208)<0.5)
        progress=dict(epoch_order=[2,0,4,1,3],cursor=2,optimizer_updates=1)
        identity=dict(source='LOCAL_TEST_ONLY',data='NO_REAL_DATA',config=dict(precision='fp32'))
        normalization=dict(image_scale=1.,fit_partition='train')
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as temporary:
            path=Path(temporary).resolve();path.relative_to(ROOT)
            checkpoint=training.save_checkpoint(torch,path/'final.pt',self.model,self.opt,identity,progress,normalization)
            before=copy.deepcopy(self.opt.state_dict())
            result=training.verify_restore(torch,checkpoint,self.model,self.opt,TinyEncoder,identity,progress,
                normalization,training.batch(torch,self.part,[0,1],self.angles),compare)
            self.assertEqual(result['extra_updates'],0);self.assertEqual(result['status'],'PASS_NO_EXTRA_UPDATE')
            self.assertTrue(training.exact(torch,before,self.opt.state_dict()))
            with self.assertRaises(ValueError):
                training.verify_restore(torch,checkpoint,self.model,self.opt,TinyEncoder,dict(identity,data='wrong'),progress,
                    normalization,values,compare)


if __name__=='__main__':
    torch.set_num_threads(36);assert torch.get_num_threads()==36
    print('LOCAL_SYNTHETIC_SMALL_NATIVE_TORCH36_ONLY; NO REAL DATA/FULL MODEL/C2',flush=True)
    unittest.main(verbosity=2)
