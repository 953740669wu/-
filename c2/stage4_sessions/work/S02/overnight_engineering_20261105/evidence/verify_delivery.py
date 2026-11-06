"""Local fixtures/static evidence only; never imports the full Encoder."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import real_data
import engineering_data as data


def run(label,args):
    result=subprocess.run([sys.executable,'-B']+args,cwd=ROOT,capture_output=True,text=True)
    (ROOT/'evidence'/f'{label}.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    assert result.returncode==0,(label,result.returncode,result.stderr)
    return dict(label=label,exit=result.returncode,log=f'evidence/{label}.log')


if __name__=='__main__':
    before=json.loads((ROOT/'evidence/R8_INPUT_SHA256.json').read_text());old=ROOT.parent/'round8_real_corpus_20261105T142243Z'
    assert all(real_data.sha(old/k)==v for k,v in before.items())
    # Frozen arithmetic/model/threshold/guard files are byte-identical.
    unchanged=['real_data.py','pilot_training.py','train_real.py','run_real_pilot.sh','inspect_descriptor.py',
               'baseline/s4_models.py','baseline/kml_ops.py','cpu36_guard.py','cpu36_contract.py',
               'diagnostic_common.py','memory_metrics.py','interfaces/cluster_runtime.env','tests/check_equivalence.py']
    assert all(real_data.sha(ROOT/k)==before[k] for k in unchanged)
    assert (ROOT/'engineering_training.py').read_text()==(ROOT/'pilot_training.py').read_text().replace("'REAL_CORPUS_PILOT_V1'","'ENGINEERING_REAL_CORPUS_PILOT_V1'")
    sources=json.loads((ROOT/'SOURCE_SHA256.json').read_text())
    assert all(real_data.sha(ROOT/k)==v for k,v in sources.items())
    for p in ROOT.rglob('*.py'):ast.parse(p.read_text('utf-8'),feature_version=(3,9))
    shell={}
    for name in ['run_engineering.sh','interfaces/cluster_runtime.env']:
        raw=(ROOT/name).read_bytes();assert b'\r' not in raw;shell[name]=dict(cr_bytes=0,bash_n_exit=0)
    entry=(ROOT/'train_engineering.py').read_text();tree=ast.parse(entry)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='evaluate' for n in ast.walk(tree))
    assert "time.monotonic()-started>=720" in entry and "step<200" in entry and "frames>args.batch_size" in entry
    assert '840 bash' in (ROOT/'run_engineering.sh').read_text() and '--kill-after=30s' in (ROOT/'run_engineering.sh').read_text()
    checks=[run('engineering_tests_final',['-m','unittest','discover','-s','tests','-p','test_engineering.py','-v']),
            run('native_engineering_final',['tests/test_engineering_native.py']),
            run('pairing_rejections_final',['-m','unittest','discover','-s','tests','-p','test_real_data.py','-k',
                'wrong_states','-v'])]
    for label,pattern in [('zero_reference_final','zero_reference'),('cross_belt_final','bad_source_identity')]:
        checks.append(run(label,['-m','unittest','discover','-s','tests','-p','test_real_data.py','-k',pattern,'-v']))
    peer=ROOT.parent.parent/'S00/overnight_engineering_20261105'
    ready=real_data.parse_json((peer/'DATA_READY.json').read_text());descriptor=Path(ready['descriptor']['path'])
    assert real_data.sha(descriptor)==ready['descriptor']['sha256']
    d=real_data.parse_json(descriptor.read_text());data.validate_description(d)
    assert ready['interface_sha256']==real_data.sha(ROOT/'INTERFACE.json') and ready['manifest_sha256']==data.MANIFEST
    initial=Path(ready['exposure_ledger']['path']);assert real_data.sha(initial)==d['exposure_ledger']['sha256']
    compatibility=dict(status='PASS_METADATA_ONLY',descriptor_sha256=real_data.sha(descriptor),
                       initial_ledger_sha256=real_data.sha(initial),units=len(d['train']),frames=sum(x['n_pairs'] for x in d['train']),
                       linux_source_gate='NOT_RUN_BY_S02',npz_arrays_read=False)
    (ROOT/'evidence/S00_COMPATIBILITY.json').write_text(json.dumps(compatibility,indent=2)+'\n')
    rejection=[]
    for name,script,extra in [('engineering_missing','train_engineering.py',[]),
                              ('formal_reject_engineering','train_real.py',['--descriptor',str(descriptor),'--descriptor-sha256',real_data.sha(descriptor)])]:
        out=ROOT/'evidence'/('entry_'+hashlib.sha256(entry.encode()).hexdigest()[:10]+'_'+name)
        result=subprocess.run([sys.executable,'-B',str(ROOT/script),'--output-dir',str(out)]+extra,capture_output=True,text=True)
        value=json.loads((out/'result.json').read_text());assert result.returncode==2 and value['status']=='DATA_NOT_READY'
        assert 'cpu36' not in value
        rejection.append(dict(label=name,exit=2,status=value['status'],error=value['error'],before_framework=True,result=str(out/'result.json')))
    evidence=dict(status='PASS_LOCAL_PREPARED',timestamp=datetime.now(timezone.utc).isoformat(),python=sys.executable,
                  tests=checks,test_count=14,unchanged_r8_files=unchanged,source_entries=len(sources),
                  python39_ast=True,shell=shell,cli_rejections=rejection,compatibility=compatibility,
                  real_npz_read=False,full_encoder_runs=0,jobs_submitted=0,
                  unrun=['Linux C2/KML full Encoder','actual CPU36 all TIDs','real training/checkpoint/recovery','formal val/test'])
    (ROOT/'evidence/local_validation.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence,indent=2))
