"""Verify only new observation changes and exact immutable inputs."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data_gate import engineering_data


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__=='__main__':
    protected=json.loads((ROOT/'evidence/PROTECTED_INPUTS.json').read_text());old=Path(protected['r9_root'])
    assert all(sha(old/k)==v for k,v in protected['r9_files'].items())
    for target,original in protected['copied_paths'].items():assert sha(ROOT/target)==protected['r9_files'][original]
    r10=ROOT.parent/'round10_linear_reuse_20261106T034306Z'
    assert sha(r10/'R10_READY.json')==protected['R10_READY_sha256'] and sha(r10/'candidate/kml_ops.py')==protected['R10_candidate_sha256']
    iface=json.loads((ROOT/'INTERFACE_READY.json').read_text())['interface']
    assert sha(ROOT/'INTERFACE.json')==iface['sha256']=='1477124f8b772226c76f8f50cee16c5d34ac34f7d8748d327c4402f82d074f76'
    assert sha(ROOT/'data_gate/INTERFACE.json')=='8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669'
    descriptor=ROOT.parent.parent/'S00/round11_gemm_breakdown_20261106/ENGINEERING_DESCRIPTOR.json'
    assert sha(descriptor)=='b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
    engineering_data.validate_description(json.loads(descriptor.read_text()))
    assert engineering_data.ROOT==ROOT/'data_gate' and 'torch' not in sys.modules and 'numpy' not in sys.modules
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert all(sha(ROOT/k)==v for k,v in source.items())
    ast_files=[]
    for name in source:
        raw=(ROOT/name).read_bytes()
        if name.endswith(('.py','.sh','.env')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9));ast_files.append(name)
    obs_tree=ast.parse((ROOT/'gemm_observer.py').read_text())
    forbidden={'clone','copy_','numpy','tolist','item','manual_seed','set_num_threads','set_num_interop_threads'}
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in forbidden for n in ast.walk(obs_tree))
    assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) and ('torch' in ast.unparse(n)) for n in ast.walk(obs_tree))
    entry=(ROOT/'train_gemm5.py').read_text();assert 'profile_probe' not in entry and 'torch.profiler' not in entry
    assert 'step<5' in entry and 'planned=5' in entry and 'step+1>=3' in entry and 'observer.sample(step+1)' in entry
    assert 'training.validate_update' in entry and 'training.verify_restore' in entry and 'accepted.compare' in entry
    assert 'source_identity()' in entry and 'time.monotonic()-started>=720' in entry
    assert "real_data.sha(kml_ops.__file__)" in entry and "real_data.sha(gemm_observer.__file__)" in entry
    assert '256' in (ROOT/'gemm_observer.py').read_text() and 'EXPECTED_CALLS=149' in (ROOT/'gemm_observer.py').read_text()
    for row in json.loads((ROOT/'evidence/shell_syntax.json').read_text()):assert row['exit']==0 and row['sha256']==sha(ROOT/row['path'])
    log=(ROOT/'evidence/observer_final.log').read_text();assert 'Ran 9 tests' in log and '\nOK' in log
    cases=[]
    formal=json.loads(descriptor.read_text());formal['protocol']='REAL_CORPUS_PILOT_V1'
    wrong=ROOT/'evidence/FORMAL_MODE_REJECTION.json';wrong.write_text(json.dumps(formal))
    run_tag=datetime.now(timezone.utc).strftime('%H%M%S%f')
    for label,extra in [('missing',[]),('formal',['--descriptor',str(wrong),'--descriptor-sha256',sha(wrong)])]:
        output=ROOT/'evidence'/('reject_'+sha(ROOT/'train_gemm5.py')[:10]+'_'+run_tag+'_'+label)
        assert not output.exists()
        proc=subprocess.run([sys.executable,'-B',str(ROOT/'train_gemm5.py'),'--output-dir',str(output)]+extra,capture_output=True,text=True)
        value=json.loads((output/'result.json').read_text());assert proc.returncode==2 and value['status']=='DATA_NOT_READY' and 'cpu36' not in value
        cases.append(dict(label=label,exit=2,status=value['status'],error=value['error'],before_framework=True,path=str(output/'result.json')))
    output=ROOT/'evidence/batch32_unused'
    proc=subprocess.run([sys.executable,'-B',str(ROOT/'train_gemm5.py'),'--batch-size','32','--output-dir',str(output)],capture_output=True,text=True)
    assert proc.returncode==2 and not output.exists();cases.append(dict(label='batch32',exit=2,before_framework=True))
    result=dict(status='PASS_LOCAL_PREPARED_FAKE_CBLAS_ONLY',timestamp=datetime.now(timezone.utc).isoformat(),python=sys.executable,
        new_observation_tests=9,log='evidence/observer_final.log',copied_immutable_files=len(protected['copied_paths']),
        protected_r9_entries=len(protected['r9_files']),R10_unchanged=True,R10_disposition='CLOSED_NOT_SELECTED_LOW_BENEFIT',
        protocol='ENGINEERING_REAL_CORPUS_GEMM5_V1',R11_interface_sha256=iface['sha256'],
        original_data_interface_sha256=sha(ROOT/'data_gate/INTERFACE.json'),descriptor_sha256=sha(descriptor),
        data_compatibility='PASS_METADATA_ONLY_NO_NPZ_READ',baseline_sha256=sha(ROOT/'baseline/kml_ops.py'),
        observer_sha256=sha(ROOT/'gemm_observer.py'),source_entries=len(source),python39_ast=ast_files,
        LF=True,bash_syntax_only=True,no_tensor_value_copy_or_dump_in_observer=True,negative_cli_checks=cases,
        actual_KML_observation='NOT_RUN_BY_S02',full_encoder_runs=0,new_jobs=0,
        acceptance='preparation only; actual first5 loss/CPU/KML/record pairing/restore validation belongs to the unique reviewed S00 job')
    (ROOT/'evidence/local_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
