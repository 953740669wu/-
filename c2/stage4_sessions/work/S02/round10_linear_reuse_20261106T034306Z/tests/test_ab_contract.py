"""LOCAL_FIXTURE: reject stale/cross-host gate and preserve strict comparisons."""
import copy
import ast
from pathlib import Path
import sys
import unittest
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import train_linear_ab as ab
import check_equivalence as accepted


class ContractTests(unittest.TestCase):
    def test_perf_candidate_keeps_original_kml_shape_counter(self):
        left=next(n for n in ast.walk(ast.parse((ROOT/'diagnostic_common.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='counted')
        right=next(n for n in ast.walk(ast.parse((ROOT/'train_linear_ab.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='counted')
        class Rename(ast.NodeTransformer):
            def visit_Name(self,node):
                if node.id=='runtime':node.id='record'
                return node
        self.assertEqual(ast.dump(left),ast.dump(Rename().visit(right)))

    def test_strict_receipt_binding(self):
        receipt=dict(status='PASS_STRICT_ENCODER5',phase='strict',completed_updates=5,source_manifest_sha256='s',
            descriptor_sha256='d',host='h',job_id='new',cpu36=dict(receipt=dict(selected=list(range(36)))))
        ab.check_receipt(receipt,'s','d','h','new',list(range(36)))
        for key,value in [('status','FAIL'),('completed_updates',4),('host','other'),('job_id','old'),('source_manifest_sha256','drift')]:
            bad=copy.deepcopy(receipt);bad[key]=value
            with self.assertRaises(ValueError):ab.check_receipt(bad,'s','d','h','new',list(range(36)))
        with self.assertRaises(ValueError):ab.check_receipt(receipt,'s','d','h','new',list(range(1,37)))

    def test_model_grad_delta_parameter_adamw_gate(self):
        torch.manual_seed(3);a=torch.nn.Linear(4,3);b=copy.deepcopy(a)
        initial={n:p.detach().clone() for n,p in a.named_parameters()};x=torch.randn(2,4)
        opts=[torch.optim.AdamW(m.parameters(),lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=.01) for m in (a,b)]
        for m,opt in zip((a,b),opts):m(x).square().mean().backward();opt.step()
        metrics=[];ab.compare_models(torch,accepted,a,b,opts,initial,metrics,'test.')
        self.assertTrue(metrics and all(m['passed'] for m in metrics))
        b.weight.grad=None
        with self.assertRaises(AssertionError):ab.compare_models(torch,accepted,a,b,opts,initial,[],'missing_grad.')
        b.weight.grad=a.weight.grad.clone();opts[1].state[b.weight]['exp_avg'].add_(1.)
        with self.assertRaises(AssertionError):ab.compare_models(torch,accepted,a,b,opts,initial,[],'state_drift.')


if __name__=='__main__':unittest.main(verbosity=2)
