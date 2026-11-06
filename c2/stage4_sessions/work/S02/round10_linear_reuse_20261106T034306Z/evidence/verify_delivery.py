"""Final local source/identity/CLI checks; no full encoder or KML execution."""
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
    frozen=json.loads((ROOT/'evidence/PROTECTED_INPUTS.json').read_text());old=Path(frozen['old_root'])
    assert sha(old/'PROFILE_READY.json')==frozen['profile_ready_sha256']
    assert all(sha(old/k)==v for k,v in frozen['old_files'].items())
    reused=[k for k,v in frozen['old_files'].items() if (ROOT/k).is_file()]
    assert len(reused)==14 and all(sha(ROOT/k)==frozen['old_files'][k] for k in reused)
    a=(ROOT/'baseline/kml_ops.py').read_text();b=(ROOT/'candidate/kml_ops.py').read_text()
    expected=a.replace('        g = gy.reshape(-1, gy.shape[-1]).to(LINEAR_DTYPE).contiguous()',
        '        gy2 = gy.reshape(-1, gy.shape[-1]) if LINEAR_DTYPE == torch.float32 and gy.dtype == torch.float32 else None\n        g = (gy2 if gy2 is not None else gy.reshape(-1, gy.shape[-1])).to(LINEAR_DTYPE).contiguous()')
    expected=expected.replace('        gb = gy.reshape(-1, gy.shape[-1]).sum(0) if ctx.hasb and ctx.needs_input_grad[2] else None',
        '        gb = (gy2 if gy2 is not None else gy.reshape(-1, gy.shape[-1])).sum(0) if ctx.hasb and ctx.needs_input_grad[2] else None')
    assert b==expected,'candidate scope changed'
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert all(sha(ROOT/k)==v for k,v in source.items())
    for name in source:
        raw=(ROOT/name).read_bytes()
        if name.endswith(('.py','.sh','.env')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode('utf-8'),feature_version=(3,9))
    for name in ['train_linear_ab.py','screen_linear.py']:
        tree=ast.parse((ROOT/name).read_text())
        assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('set_num_threads','set_num_interop_threads','profile') for n in ast.walk(tree))
    metrics=json.loads((ROOT/'evidence/linear_metrics.json').read_text())
    assert metrics['scope']=='NATIVE_SUBSTITUTE_NOT_KML' and not metrics['actual_kml']
    assert len(metrics['metrics'])==115 and all(x['passed'] and x['max_abs']==0 for x in metrics['metrics'])
    assert metrics['imports'][0]['sha256']==sha(ROOT/'baseline/kml_ops.py') and metrics['imports'][1]['sha256']==sha(ROOT/'candidate/kml_ops.py')
    for row in json.loads((ROOT/'evidence/shell_syntax.json').read_text()):assert row['exit']==0 and row['sha256']==sha(ROOT/row['path'])
    mappings=json.loads((ROOT/'evidence/PROFILE_CODE_MAPPING.json').read_text())
    for asset in mappings['bindings'].values():
        p=Path(asset['path']);assert p.stat().st_size==asset['bytes'] and sha(p)==asset['sha256']
    rejection=[]
    cpu=','.join(map(str,range(36)))
    for label,script,extra,status in [
        ('full_entry_wrong_platform_path','train_linear_ab.py',['--phase','strict','--descriptor',str(ROOT/'REFERENCE_FIRST5.json'),
          '--descriptor-sha256','unused','--expected-cpus',cpu,'--cpu-contract',str(ROOT/'REFERENCE_FIRST5.json')],'FAIL_STOP_NO_RETRY'),
        ('actual_kml_screen_windows_no_fallback','screen_linear.py',['--expected-cpus',cpu,'--cpu-contract',str(ROOT/'REFERENCE_FIRST5.json')],'FAIL_STOP')]:
        out=ROOT/'evidence'/('reject_'+sha(ROOT/script)[:10]+'_'+label)
        proc=subprocess.run([sys.executable,'-B',str(ROOT/script),'--output-dir',str(out)]+extra,capture_output=True,text=True)
        path=out/('screen_result.json' if script.startswith('screen') else 'result.json');value=json.loads(path.read_text())
        assert proc.returncode==2 and value['status']==status and 'runtime' not in value
        rejection.append(dict(label=label,exit=2,status=value['status'],error=value['error'],scope='EXPECTED_PLATFORM_OR_PATH_REFUSAL_NOT_NUMERIC_FAILURE',result=str(path)))
    coord=ROOT.parent.parent/'COORDINATION/JOB2048959_PROFILE_REVIEW_20261106.json'
    assert json.loads(coord.read_text())['decision']=='R9_ENGINEERING_PROFILE_EVIDENCE_VERIFIED'
    result=dict(status='PASS_LOCAL_NATIVE_INTERFACE_ONLY',timestamp=datetime.now(timezone.utc).isoformat(),python=sys.executable,
        tests=dict(targeted_native=4,ab_contract=3,total=7),frozen_comparator_metrics=115,max_abs=0.,actual_imports=metrics['imports'],
        baseline_sha256=sha(ROOT/'baseline/kml_ops.py'),candidate_sha256=sha(ROOT/'candidate/kml_ops.py'),
        preserved_files=reused,protected_r9_source_entries=len(frozen['old_files']),original_comparator_unchanged=True,
        python39_ast=True,LF=True,bash_syntax_only=True,negative_cli_checks=rejection,
        R9_bound_inputs_verified=len(mappings['bindings']),coordinator_review_sha256=sha(coord),
        actual_KML_numeric='NOT_RUN',full_encoder_strict='NOT_RUN',same_node_AB='NOT_RUN',new_jobs=0,
        gain='NOT_ACCEPTED; R9 only duplicate views, no matrix-copy saving proven',production_default_changed=False)
    (ROOT/'evidence/local_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
