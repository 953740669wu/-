"""One-time local package construction; no model or cluster submission."""
import ast
import difflib
import json
from pathlib import Path
import shutil
import zipfile
from prepare import sha,save,DEPLOYMENT

root=Path(__file__).resolve().parent
source=root.parents[1]/'S02/round11_gemm_breakdown_20261106'
old=root.parent/'round9_profile5_20261106'
ready=json.loads((source/'GEMM_READY.json').read_text())
assert ready['status']=='GEMM_READY' and ready['immutable_after_publish'] is True
checks={}
for key,value in ready.items():
    if isinstance(value,dict) and {'path','bytes','sha256'}<=value.keys():
        p=Path(value['path']);assert p.stat().st_size==value['bytes'] and sha(p)==value['sha256'],key
        checks[key]=value
shutil.copyfile(source/'GEMM_READY.json',root/'S02_GEMM_READY.json')
for key,name in [('package','S02_R11_GEMM5_CODE.zip'),('source_manifest','S02_SOURCE_SHA256.json'),('interface','INTERFACE.json'),('contract','GEMM_CONTRACT.json'),('reference','REFERENCE_FIRST5.json')]:
    shutil.copyfile(ready[key]['path'],root/name)
assert ready['baseline']['sha256']=='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
with zipfile.ZipFile(root/'S02_R11_GEMM5_CODE.zip') as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('SOURCE_SHA256.json'))
    assert set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'}
    import hashlib
    for name,digest in manifest.items():
        raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==digest,name
        if name.endswith(('.py','.sh')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9))
    assert manifest['baseline/kml_ops.py']==ready['baseline']['sha256']
pins=dict(code_archive='S02_R11_GEMM5_CODE.zip',code_package_sha256=ready['package']['sha256'],code_package_bytes=ready['package']['bytes'],
    code_source_manifest_name='SOURCE_SHA256.json',code_source_manifest_sha256=ready['source_manifest']['sha256'],entrypoint='run_gemm5.sh',
    entry_environment=['S02_ENGINEERING_DESCRIPTOR','S02_ENGINEERING_DESCRIPTOR_SHA256'],descriptor_sha256=sha(root/'ENGINEERING_DESCRIPTOR.json'),
    interface_sha256=ready['interface']['sha256'],contract_sha256=ready['contract']['sha256'],reference_sha256=ready['reference']['sha256'],
    remote_staging_root=json.loads((root/'WORK_STARTED.json').read_text())['remote_staging_root'])
assert pins['descriptor_sha256']=='b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
save(root/'PINNED_INPUTS.json',pins)
helpers=['owned_processes.py','gate.py','scheduler_handoff.py','cpu36_contract.py','submit_once.py','run_job.sh']
save(root/'UNCHANGED_HELPERS.json',{n:dict(source=str(old/n),sha256=sha(root/n),unchanged=sha(root/n)==sha(old/n)) for n in helpers})
assert all(sha(root/n)==sha(old/n) for n in helpers)
diff=[]
for name in ['prepare.py','review_gate.py','run_job.py','collect_evidence.py']:
    diff.extend(difflib.unified_diff((old/name).read_text().splitlines(True),(root/name).read_text().splitlines(True),fromfile='R9/'+name,tofile='R11/'+name))
for name in ['gemm_outcome.py','tests/test_gemm_deployment.py']:
    diff.extend(difflib.unified_diff([], (root/name).read_text().splitlines(True),fromfile='/dev/null',tofile='R11/'+name))
(root/'MINIMAL.diff').write_text(''.join(diff),encoding='utf-8',newline='\n')
names=[p.name for p in root.glob('*.py')]+[p.name for p in root.glob('*.sh')]+[
 'tests/test_gemm_deployment.py','ENGINEERING_DESCRIPTOR.json','EXPOSURE_LEDGER_INITIAL.json','INTERFACE.json','GEMM_CONTRACT.json','REFERENCE_FIRST5.json',
 'PINNED_INPUTS.json','S02_GEMM_READY.json','S02_SOURCE_SHA256.json','S02_R11_GEMM5_CODE.zip','COMMANDS.md','MINIMAL.diff','UNCHANGED_HELPERS.json']
names=sorted(set(names))
for name in names:
    if name.endswith(('.py','.sh')):
        raw=(root/name).read_bytes();assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9))
save(root/'ARTIFACT_SHA256.json',{n:sha(root/n) for n in names})
(root/'ARTIFACT_SHA256.txt').write_text(''.join(sha(root/n)+'  '+n+'\n' for n in names),encoding='utf-8',newline='\n')
with zipfile.ZipFile(root/DEPLOYMENT,'x',zipfile.ZIP_DEFLATED) as z:
    for name in names+['ARTIFACT_SHA256.json','ARTIFACT_SHA256.txt']:z.write(root/name,name)
    z.writestr('evidence/','')
receipt=dict(path=str(root/DEPLOYMENT),bytes=(root/DEPLOYMENT).stat().st_size,sha256=sha(root/DEPLOYMENT),files=len(names)+2,source_index_sha256=sha(root/'ARTIFACT_SHA256.json'))
save(root/'DEPLOYMENT_RECEIPT.json',receipt)
(root/(DEPLOYMENT+'.sha256')).write_text(receipt['sha256']+'  '+DEPLOYMENT+'\n',encoding='utf-8',newline='\n')
save(root/'evidence/FROZEN_INPUT_CHECKS.json',dict(status='ALL_GEMM_READY_ASSETS_AND_ZIP_PASS',assets=checks,zip_source_entries=len(manifest),actual_KML='NOT_RUN'))
print(json.dumps(receipt))
