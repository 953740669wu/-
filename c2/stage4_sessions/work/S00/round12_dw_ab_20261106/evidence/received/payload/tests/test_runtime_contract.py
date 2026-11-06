"""LOCAL_FIXTURE: visible logical/native counts and strict-gate identity."""
import ast
import ctypes
import copy
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import runtime_counts as counters
import train_dw_ab as ab


class RuntimeTests(unittest.TestCase):
    def test_actual_native_counter_is_not_hidden_as149(self):
        args=(101,112,111,512,1024,13312,1.,1000,512,2000,2048,0.,3000,2048)
        native_type=ctypes.CFUNCTYPE(None,*([ctypes.c_int]*6+[ctypes.c_float,ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_float,ctypes.c_void_p,ctypes.c_int]))
        seen=[];native=native_type(lambda *a:seen.append(a));module=types.SimpleNamespace(_sgemm=native)
        state=counters.attach_native(module,True);module._sgemm(*args);module._sgemm(*args)
        self.assertEqual(state['native_calls'],2);self.assertEqual(state['target_tiles'],2);self.assertEqual(len(seen),2)
        self.assertEqual(state['captured_target'],[list(args),list(args)])
        counters.verify_step('baseline',149,12,149,12,0);counters.verify_step('candidate',149,12,161,0,24)
        with self.assertRaises(ValueError):counters.verify_step('candidate',149,12,149,12,0)
        with self.assertRaises(ValueError):counters.verify_step('candidate',149,11,160,0,22)
        with self.assertRaises(ValueError):counters.attach_native(types.SimpleNamespace(_sgemm=lambda *a:None))

    def test_strict_receipt_rejects_old_source_node_job_or_cpu(self):
        r=dict(status='PASS_STRICT_ENCODER5',phase='strict',completed_updates=5,source_manifest_sha256='s',descriptor_sha256='d',host='h',job_id='j',cpu36=dict(receipt=dict(selected=list(range(36)))))
        ab.check_receipt(r,'s','d','h','j',list(range(36)))
        for key,value in [('status','FAIL'),('completed_updates',4),('source_manifest_sha256','old'),('host','other'),('job_id','old')]:
            bad=copy.deepcopy(r);bad[key]=value
            with self.assertRaises(ValueError):ab.check_receipt(bad,'s','d','h','j',list(range(36)))
        with self.assertRaises(ValueError):ab.check_receipt(r,'s','d','h','j',list(range(1,37)))

    def test_perf_keeps_logical_shape_diagnostics(self):
        a=next(n for n in ast.walk(ast.parse((ROOT/'diagnostic_common.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='counted')
        b=next(n for n in ast.walk(ast.parse((ROOT/'train_dw_ab.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='counted')
        class Rename(ast.NodeTransformer):
            def visit_Name(self,n):
                if n.id=='runtime':n.id='record'
                return n
        self.assertEqual(ast.dump(a),ast.dump(Rename().visit(b)))

    def test_strict_5_then_epoch25_has_no_step_reduction(self):
        s=(ROOT/'train_dw_ab.py').read_text()
        self.assertIn("planned=5 if args.phase=='strict' else 25",s)
        self.assertIn('for step in range(1,planned+1):',s);self.assertIn("sampled=args.phase=='perf' and step>=6",s)
        self.assertIn('cursor=1600,optimizer_updates=25',s)
        self.assertIn("runtime['libraries']!=prior['runtime']['libraries']",s)
        self.assertIn('verify_step(role,actual_calls,target_delta',s)


if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
