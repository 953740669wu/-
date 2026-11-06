"""Freeze this S00 wrapper, preserving the exact existing R6 inner bytes."""
import ast
import difflib
import json
from pathlib import Path
import zipfile
from prepare import sha,save,ARCHIVE,INNER_SHA,check_members
from review_gate import DEPLOYMENT
root=Path(__file__).resolve().parent;old=root.parent/'s07_wrapper_r5_ready_20261105';previous=root.parent/'round12_dw_ab_20261106'
assert (root/ARCHIVE).stat().st_size==43727 and sha(root/ARCHIVE)==INNER_SHA
with zipfile.ZipFile(root/ARCHIVE) as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('SOURCE_MANIFEST.json'));check_members(z,manifest)
    assert z.read('SOURCE_MANIFEST.json')==(root/'SOURCE_MANIFEST.json').read_bytes()
    for name in z.namelist():
        if name.endswith('.py'):
            raw=z.read(name);assert b'\r' not in raw;ast.parse(raw.decode(),feature_version=(3,9))
assert sha(root/'scheduler_handoff.py')==sha(old/'scheduler_handoff.py') and sha(root/'readiness_inventory.py')==sha(old/'readiness_inventory.py')
save(root/'UNCHANGED_HELPERS.json',{name:dict(source=str(old/name),sha256=sha(root/name),unchanged=True) for name in ['scheduler_handoff.py','readiness_inventory.py']})
diff=[]
for name in ['prepare.py','bounded_round_step.py','run_s07_diag_job.py','run_s07_diag_job.sh','submit_once.py','collect_evidence.py','trace_inventory.py']:
    diff.extend(difflib.unified_diff((old/name).read_text(encoding='utf-8').splitlines(True),(root/name).read_text(encoding='utf-8').splitlines(True),fromfile='R5/'+name,tofile='R6/'+name))
for name in ['review_gate.py','stack_inventory.py','tests/test_r6_deployment.py']:diff.extend(difflib.unified_diff([], (root/name).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='R6/'+name))
(root/'MINIMAL.diff').write_text(''.join(diff),encoding='utf-8',newline='\n')
(root/'OWNERSHIP_FROM_R12.diff').write_text(''.join(difflib.unified_diff((previous/'owned_processes.py').read_text(encoding='utf-8').splitlines(True),(root/'owned_processes.py').read_text(encoding='utf-8').splitlines(True),fromfile='R12/owned_processes.py',tofile='R6/owned_processes.py')),encoding='utf-8',newline='\n')
save(root/'OWNERSHIP_PROVENANCE.json',dict(source=str(previous/'owned_processes.py'),source_sha256=sha(previous/'owned_processes.py'),current_sha256=sha(root/'owned_processes.py'),change='same subreaper/PID-start_ticks/process discovery; original S07 wrapper TERM2/KILL10 within15 cap; shared global consumer+15 cap, not per-descendant extra grace'))
names=sorted(set([p.name for p in root.glob('*.py')]+[p.name for p in root.glob('*.sh')]+[ARCHIVE,'SOURCE_MANIFEST.json','OBSERVATION_CONTRACT.md','INTERFACE_FOR_S00.md','TASK_CARD.md','WORK_STARTED.json','COMMANDS.md','MINIMAL.diff','OWNERSHIP_FROM_R12.diff','OWNERSHIP_PROVENANCE.json','UNCHANGED_HELPERS.json','tests/test_r6_deployment.py']))
for name in names:
    if name.endswith(('.py','.sh')):
        raw=(root/name).read_bytes();assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9))
save(root/'ARTIFACT_SHA256.json',{name:sha(root/name) for name in names})
(root/'ARTIFACT_SHA256.txt').write_text(''.join(sha(root/name)+'  '+name+'\n' for name in names),encoding='utf-8',newline='\n')
with zipfile.ZipFile(root/DEPLOYMENT,'x',zipfile.ZIP_DEFLATED) as z:
    for name in names+['ARTIFACT_SHA256.json','ARTIFACT_SHA256.txt']:z.write(root/name,name)
    z.writestr('evidence/','')
receipt=dict(path=str(root/DEPLOYMENT),bytes=(root/DEPLOYMENT).stat().st_size,sha256=sha(root/DEPLOYMENT),files=len(names)+2,source_index_sha256=sha(root/'ARTIFACT_SHA256.json'))
save(root/'DEPLOYMENT_RECEIPT.json',receipt)
(root/(DEPLOYMENT+'.sha256')).write_text(receipt['sha256']+'  '+DEPLOYMENT+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt))
