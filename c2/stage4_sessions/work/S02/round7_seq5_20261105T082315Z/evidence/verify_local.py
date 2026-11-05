"""Local source/syntax/entry-boundary checks only; no full model or measurement."""
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


record=dict(status='LOCAL_CHECKS_ONLY',python=sys.executable,python_version=sys.version,
    torch_distribution_version=importlib.metadata.version('torch'),full_model_runs=0,new_jobs=0,memory_runs=0)
record['python39_syntax']=[]
for path in ROOT.rglob('*.py'):
    ast.parse(path.read_text('utf-8'),feature_version=(3,9))
    record['python39_syntax'].append(path.relative_to(ROOT).as_posix())
scripts=[ROOT/name for name in ['run_sequence5.sh','run_s00_seq5_job.sh','interfaces/cluster_runtime.env']]
blocks=re.findall(r'```bash\n(.*?)\n```',(ROOT/'C2_HANDOFF.md').read_text('utf-8'),re.S)
assert len(blocks)==2
for index,block in enumerate(blocks,1):
    path=ROOT/f'evidence/S00_COMMANDS_{index}.sh';path.write_text(block+'\n',encoding='utf-8',newline='\n')
    scripts.append(path)
    if "<<'PY'\n" in block:
        ast.parse(block.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0],feature_version=(3,9))
record['shell_checks']=[]
for path in scripts:
    assert b'\r' not in path.read_bytes()
    run=subprocess.run(['C:/Program Files/Git/bin/bash.exe','-n',str(path)],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    record['shell_checks'].append(dict(file=path.relative_to(ROOT).as_posix(),cr_bytes=0,git_bash_n_exit=0))
source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert all(sha(ROOT/name)==value for name,value in source.items())
before=json.loads((ROOT/'evidence/inputs_before.json').read_text());count=0
for name,item in before.items():
    if Path(name).name in ('SESSION_STATUS.md','ROUND_DELTA.md'):continue
    path=Path(name)
    assert dict(bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns,sha256=sha(path))==item,name
    count+=1
record['protected_sources_unchanged']=count
case=ROOT.parent/'round3_20261104T134939Z/case/fixed_16_pre.pt'
old_pass=ROOT.parents[1]/'S00/evidence/memory3_s07_r2_20261105/S02/received/strict_reference_result.json'
common=['--case-file',str(case),'--expected-cpus',','.join(map(str,range(36))), '--cpu-contract','not-read-on-Windows.json']
record['entry_rejections']=[]
for name,extra,reason in [('check_sequence5.py',[],'Linux'),
    ('train_sequence5.py',['--checkpoint','0','--strict-result',str(old_pass)],'old one-step result refused')]:
    out=ROOT/'evidence'/('rejected_'+name.replace('.py','.json'))
    run=subprocess.run([sys.executable,'-B',str(ROOT/name),*common,*extra,'--output',str(out)],capture_output=True,text=True)
    out.with_suffix('.stdout.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
    result=json.loads(out.read_text())
    assert run.returncode==2 and result['status']=='ERROR_RUNTIME_OR_STATE' and reason in result['error']
    record['entry_rejections'].append(dict(entry=name,exit=2,error=result['error']))
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
record.update(status='PASS_LOCAL_SYNTAX_IDENTITY_BOUNDARIES_ONLY',framework_imported_by_this_check=False,
              shell_commands_executed=False)
(ROOT/'evidence/local_validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:value for key,value in record.items() if key!='python39_syntax'},indent=2))
