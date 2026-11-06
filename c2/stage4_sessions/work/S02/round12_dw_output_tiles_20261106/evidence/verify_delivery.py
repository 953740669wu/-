"""Final source/ABI-scope/local-evidence verification, no numerical reruns."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__=='__main__':
    proof=json.loads((ROOT/'evidence/PROTECTED_INPUTS.json').read_text());old=Path(proof['r11_root'])
    assert sha(old/'GEMM_READY.json')==proof['r11_ready_sha256']
    assert all(sha(old/k)==v for k,v in proof['r11_files'].items())
    assert all(sha(ROOT/k)==proof['r11_files'][k] for k in proof['copied_files'])
    assert sha(ROOT/'baseline/kml_ops.py')=='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert len(source)==26 and all(sha(ROOT/k)==v for k,v in source.items())
    for name in source:
        raw=(ROOT/name).read_bytes()
        if name.endswith(('.py','.sh','.env')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9))
    a=ast.parse((ROOT/'baseline/kml_ops.py').read_text());b=ast.parse((ROOT/'candidate/kml_ops.py').read_text())
    aa={n.name:ast.dump(n) for n in a.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    bb={n.name:ast.dump(n) for n in b.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    assert set(aa)==set(bb) and all(aa[k]==bb[k] for k in aa if k!='gemm')
    f=next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name=='gemm')
    oldf=next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name=='gemm')
    changed=[n for n in f.body if isinstance(n,ast.If) and '(512, 2048, 13312)' in ast.unparse(n.test)]
    assert len(changed)==1
    original_body=[n for n in f.body if n is not changed[0]]
    assert ast.dump(ast.Module(body=original_body,type_ignores=[]))==ast.dump(ast.Module(body=oldf.body,type_ignores=[]))
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('clone','contiguous','copy_','to','float') for n in ast.walk(changed[0]))
    native=json.loads((ROOT/'evidence/native_screen.json').read_text())
    assert native['scope']=='LOCAL_FAKE_CBLAS_NATIVE_MATMUL_NOT_KML' and len(native['metrics'])==30
    assert all(x['passed'] and x['max_abs']==0 and x['l2_relative']==0 for x in native['metrics'])
    assert native['abi'][0]['native_calls']==2 and native['abi'][0]['canaries'] and native['abi'][0]['inputs_unchanged']
    assert 'Ran 5 tests' in (ROOT/'evidence/native_screen_first.log').read_text() and '\nOK' in (ROOT/'evidence/native_screen_first.log').read_text()
    assert 'Ran 4 tests' in (ROOT/'evidence/runtime_contract_final.log').read_text() and '\nOK' in (ROOT/'evidence/runtime_contract_final.log').read_text()
    identities=json.loads((ROOT/'evidence/IMPORT_IDENTITY.json').read_text())['imports']
    for item in identities:assert sha(Path(item['path']))==item['sha256'] and item['path']==item['gemm_code_filename'] and not item['imported_native_lib']
    for row in json.loads((ROOT/'evidence/shell_syntax.json').read_text()):assert row['exit']==0 and row['sha256']==sha(ROOT/row['path'])
    target=json.loads((ROOT/'evidence/TARGET_FROM_R11.json').read_text())
    for asset in target['bindings'].values():assert sha(Path(asset['path']))==asset['sha256']
    epoch=json.loads((ROOT/'REFERENCE_EPOCH25.json').read_text());assert len(epoch['steps'])==25
    assert sha(Path(epoch['steps_asset']['path']))==epoch['steps_asset']['sha256']
    cases=[];run_tag=datetime.now(timezone.utc).strftime('%H%M%S%f');cpus=','.join(map(str,range(36)))
    for label,script,extra in [('target_wrong_platform','screen_target.py',[]),('full_wrong_path','train_dw_ab.py',['--phase','strict','--descriptor',str(ROOT/'REFERENCE_FIRST5.json'),'--descriptor-sha256','unused'])]:
        output=ROOT/'evidence'/('refusal_'+run_tag+'_'+label)
        proc=subprocess.run([sys.executable,'-B',str(ROOT/script),'--expected-cpus',cpus,'--cpu-contract',str(ROOT/'REFERENCE_FIRST5.json'),'--output-dir',str(output)]+extra,capture_output=True,text=True)
        path=output/('screen_result.json' if script.startswith('screen') else 'result.json');value=json.loads(path.read_text())
        assert proc.returncode==2 and 'runtime' not in value
        cases.append(dict(label=label,scope='EXPECTED_PATH_REFUSAL_NOT_NUMERIC_FAILURE',exit=2,error=value['error'],path=str(path)))
    coordinator=ROOT.parent.parent/'COORDINATION/JOB2049454_GEMM_REVIEW_20261106.json'
    assert json.loads(coordinator.read_text())['decision']=='R11_ENGINEERING_GEMM_EVIDENCE_VERIFIED'
    result=dict(status='PASS_LOCAL_SCREEN_FIXED_CANDIDATE_ONLY',timestamp=datetime.now(timezone.utc).isoformat(),python=sys.executable,
        tests=dict(candidate_math_ABI=5,runtime_contract=4,total=9),frozen_comparator_metrics=30,max_abs=0.,max_relative=0.,
        baseline_sha256=sha(ROOT/'baseline/kml_ops.py'),candidate_sha256=sha(ROOT/'candidate/kml_ops.py'),actual_import_checks=identities,
        protected_r11_files=len(proof['r11_files']),reused_files=len(proof['copied_files']),R11_bindings_verified=len(target['bindings']),
        coordinator_review_sha256=sha(coordinator),new_source_entries=len(source),Python39_AST=True,LF=True,bash_syntax=True,
        unchanged_functions_except_gemm=True,no_large_operand_copies_in_dispatch=True,negative_cli=cases,
        local_backend='FAKE_CBLAS_NATIVE_TORCH_MATMUL; NOT ACTUAL KML',actual_KML_target='NOT_RUN',full_encoder_strict='NOT_RUN',same_node_AB='NOT_RUN',new_jobs=0,
        acceptance='local mathematical/ABI/bounds filter only; unchanged K does not prove KML numerical equivalence or speedup')
    (ROOT/'evidence/local_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
