"""Entry/mean-contract checks only; no actual corpus or model execution."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import train_real
import real_data


class ContractTests(unittest.TestCase):
    def args(self,path=None,sha=None):
        return SimpleNamespace(descriptor=path,descriptor_sha256=sha,batch_size=64,
            expected_cpus=list(range(36)),cpu_contract=None,output_dir=ROOT/'evidence')

    def test_missing_data_stops_before_cpu_or_framework(self):
        with patch.object(train_real,'source_identity',return_value={}), \
             patch.object(train_real.cpu36_guard,'prepare') as prepare, \
             self.assertRaises(real_data.DataNotReady):
            train_real.main(self.args(),{})
        prepare.assert_not_called();self.assertNotIn('torch',sys.modules)

    def test_actual_s00_blocked_audit_cannot_start_training(self):
        path=ROOT.parents[1]/'S00/REALDATA_SOURCE_AUDIT.json'
        if not path.is_file():self.skipTest('local S00 audit is not bundled with a deployed payload')
        with patch.object(train_real,'source_identity',return_value={}), \
             patch.object(train_real.cpu36_guard,'prepare') as prepare, \
             self.assertRaisesRegex(real_data.DataNotReady,'MANIFEST_IDENTITY_DRIFT'):
            train_real.main(self.args(path,real_data.sha(path)),{})
        prepare.assert_not_called();self.assertNotIn('torch',sys.modules)

    def test_original_mean_expression_ast_is_preserved(self):
        old=ast.parse((ROOT/'reference/full_batch_step.py').read_text('utf-8'))
        new=ast.parse((ROOT/'pilot_training.py').read_text('utf-8'))
        original=next(n.value for n in ast.walk(old) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='loss' for t in n.targets))
        function=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='losses')
        assignments={t.id:n.value for n in function.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name)}
        actual=ast.BinOp(left=assignments['voltage'],op=ast.Add(),right=assignments['coarse'])
        class Normalize(ast.NodeTransformer):
            def visit_Name(self,node):
                return ast.copy_location(ast.Name(id={'model':'enc','image':'y0'}.get(node.id,node.id),ctx=node.ctx),node)
        self.assertEqual(ast.dump(original),ast.dump(Normalize().visit(actual)))


if __name__=='__main__':unittest.main(verbosity=2)
