"""Verify unchanged inputs, local fixture tests, bounded entry and CLI rejection."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import profile_contract
import real_data


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__=='__main__':
    original=json.loads((ROOT/'evidence/FROZEN_INPUTS.json').read_text());old=Path(original['old_root'])
    assert sha(old/'CODE_READY.json')==original['code_ready_sha256']
    assert sha(old/'SOURCE_SHA256.json')==original['old_source_manifest_sha256']
    assert all(sha(old/k)==v for k,v in original['old_files'].items())
    unchanged=[k for k,v in original['old_files'].items() if (ROOT/k).is_file()]
    assert len(unchanged)==16 and all(sha(ROOT/k)==original['old_files'][k] for k in unchanged)
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert all(sha(ROOT/k)==v for k,v in source.items())
    ast_files=[]
    for name in source:
        raw=(ROOT/name).read_bytes()
        if name.endswith(('.py','.sh','.env')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9));ast_files.append(name)
    entry=(ROOT/'train_profile5.py').read_text();tree=ast.parse(entry)
    assert 'step<5' in entry and 'planned=5' in entry and 'args.batch_size!=64' in entry
    assert 'time.monotonic()-started>=720' in entry
    assert "args.output_dir/'EXPOSURE_LEDGER.json'" in entry
    assert "Exposure(metadata['description']['runtime_exposure_ledger_path']" not in entry
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in
                   ('evaluate','set_num_threads','set_num_interop_threads','patch_attention','swap_convs') for n in ast.walk(tree))
    assert 'training.validate_update' in entry and 'cpu36_guard.prepare' in entry and 'training.verify_restore' in entry
    assert 'profile_contract.check_step_identity' in entry and 'accepted.compare' in entry and "'tensor',replay_metrics" in entry
    shell=(ROOT/'run_profile5.sh').read_text();assert '840 bash' in shell and '--kill-after=30s' in shell and '!= 2043445' in shell
    contract=json.loads((ROOT/'PROFILE_CONTRACT.json').read_text());assert contract['updates']['cpu_samples']==[3,4,5]
    assert contract['resources']==dict(allocated_cores=38,actual_physical_cores=36,reserved_cores=2,memory_MB=24576,
        memory_limit_MB=24576,exclusive=True,job_seconds=900,whole_entry_timeout=840,cleanup_seconds=30,closing_seconds=30,stop_new_update_after_seconds=720)
    test=subprocess.run([sys.executable,'-B',str(ROOT/'tests/test_profile5.py')],cwd=ROOT,capture_output=True,text=True)
    (ROOT/'evidence/profile_tests_final.log').write_text(test.stdout+test.stderr,encoding='utf-8')
    assert test.returncode==0,test.stderr
    protected=json.loads((ROOT/'evidence/BASELINE_TIMING.json').read_text())
    for k,a in protected['bindings'].items():
        p=Path(a['path']);assert p.stat().st_size==a['bytes'] and sha(p)==a['sha256'],k
    complete=ROOT.parent.parent/'S00/overnight_engineering_20261105/RUN_COMPLETE.json'
    c=json.loads(complete.read_text());assert c['job_id']=='2043445' and c['outcome']=='ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE'
    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())
    steps=[json.loads(line) for line in Path(c['steps']['path']).read_text().splitlines()]
    for row,ref in zip(steps[:5],reference['steps']):
        profile_contract.check_step_identity(row['step'],row['frame_indices'],profile_contract.identity(row['frame_ids']),row['mask_sha256'],reference)
        assert row['losses']==ref['losses'] and row['kml_calls']==ref['kml_calls']
    cases=[]
    formal=json.loads((old/'tests/ENGINEERING_DESCRIPTOR_METADATA_FIXTURE.json').read_text());formal['protocol']='REAL_CORPUS_PILOT_V1'
    formal_path=ROOT/'evidence/FORMAL_MODE_REJECTION_INPUT.json';formal_path.write_text(json.dumps(formal),encoding='utf-8')
    for label,extra in [('missing',[]),('formal_protocol',['--descriptor',str(formal_path),'--descriptor-sha256',sha(formal_path)])]:
        out=ROOT/'evidence'/('cli_'+sha(ROOT/'train_profile5.py')[:12]+'_'+label)
        run=subprocess.run([sys.executable,'-B',str(ROOT/'train_profile5.py'),'--output-dir',str(out)]+extra,capture_output=True,text=True)
        value=json.loads((out/'result.json').read_text())
        assert run.returncode==2 and value['status']=='DATA_NOT_READY' and 'cpu36' not in value
        cases.append(dict(label=label,exit=2,status=value['status'],error=value['error'],before_framework=True,result=str(out/'result.json')))
    run=subprocess.run([sys.executable,'-B',str(ROOT/'train_profile5.py'),'--batch-size','32','--output-dir',str(ROOT/'evidence/invalid_batch_unused')],capture_output=True,text=True)
    assert run.returncode==2 and not (ROOT/'evidence/invalid_batch_unused').exists()
    cases.append(dict(label='batch32_rejected',exit=2,before_framework=True))
    coordinator=ROOT.parent.parent/'COORDINATION/JOB2043445_ENGINEERING_REVIEW_20261106.json'
    review=json.loads(coordinator.read_text());assert review['decision']=='ENGINEERING_RUN_EVIDENCE_VERIFIED'
    result=dict(status='PASS_LOCAL_PREPARED_NOT_C2_PROFILED',timestamp=datetime.now(timezone.utc).isoformat(),python=sys.executable,
                native_fixture_tests=6,test_log='evidence/profile_tests_final.log',cli_rejections=cases,unchanged_frozen_files=unchanged,
                source_files=len(source),python39_ast=ast_files,shell_syntax=json.loads((ROOT/'evidence/shell_syntax.json').read_text()),
                baseline_bindings_verified=7,run_complete_sha256=sha(complete),coordinator_review_sha256=sha(coordinator),
                first5_reference='PASS_FROM_BOUND_ORIGINAL_STEPS',real_npz_read=False,full_encoder_runs=0,C2_KML_profile_runs=0,
                new_jobs=0,operator_hotspot_conclusion='UNKNOWN_NOT_PROFILED',execution_authorization='NOT_GRANTED_BY_THIS_PACKAGE')
    (ROOT/'evidence/local_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
