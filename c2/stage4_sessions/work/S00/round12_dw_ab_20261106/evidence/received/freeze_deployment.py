"""One-time local R12 deployment builder; no matrix/model/cluster actions."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from prepare import sha,save,DEPLOYMENT
root=Path(__file__).resolve().parent;source=root.parents[1]/'S02/round12_dw_output_tiles_20261106';old=root.parent/'round11_gemm_breakdown_20261106'
ready=json.loads((source/'R12_READY.json').read_text(encoding='utf-8'))
assert ready['status']=='LOCAL_SCREEN_PASS_PENDING_ACTUAL_KML' and ready['immutable_after_publish'] is True
assets={}
for key,asset in ready.items():
    if isinstance(asset,dict) and {'path','bytes','sha256'}<=asset.keys():
        path=Path(asset['path']);assert path.stat().st_size==asset['bytes'] and sha(path)==asset['sha256'],key
        assets[key]=asset
assert ready['package']['sha256']=='44232f7627cfbcf59fb721acd23af46aed8fa790b20fe743a3c9886717ec4de4'
shutil.copyfile(source/'R12_READY.json',root/'S02_R12_READY.json')
for key,name in [('package','S02_R12_DW_TWO_COLUMN_TILES.zip'),('source_manifest','S02_SOURCE_SHA256.json'),('contract','R12_CONTRACT.json')]:shutil.copyfile(ready[key]['path'],root/name)
for name in ['REFERENCE_FIRST5.json','REFERENCE_EPOCH25.json']:shutil.copyfile(source/name,root/name)
shutil.copyfile(root.parents[1]/'COORDINATION/R12_DW_AB_EXECUTION_NEXT_20261106.md',root/'TASK_CARD.md')
with zipfile.ZipFile(root/'S02_R12_DW_TWO_COLUMN_TILES.zip') as z:
    assert z.testzip() is None
    manifest=json.loads(z.read('SOURCE_SHA256.json'));assert set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'}
    for name,digest in manifest.items():
        raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==digest,name
        if name.endswith(('.py','.sh')):assert b'\r' not in raw,name
        if name.endswith('.py'):ast.parse(raw.decode(),feature_version=(3,9))
    for name in ['R12_CONTRACT.json','REFERENCE_FIRST5.json','REFERENCE_EPOCH25.json']:assert sha(root/name)==manifest[name]
    assert manifest['baseline/kml_ops.py']==ready['baseline']['sha256'] and manifest['candidate/kml_ops.py']==ready['candidate_source']['sha256']
pins=dict(code_archive='S02_R12_DW_TWO_COLUMN_TILES.zip',code_package_bytes=ready['package']['bytes'],code_package_sha256=ready['package']['sha256'],
 code_source_manifest_name='SOURCE_SHA256.json',code_source_manifest_sha256=ready['source_manifest']['sha256'],entrypoint=ready['entrypoint'],
 descriptor_sha256=sha(root/'ENGINEERING_DESCRIPTOR.json'),candidate_sha256=ready['candidate_source']['sha256'],baseline_sha256=ready['baseline']['sha256'],
 contract_sha256=sha(root/'R12_CONTRACT.json'),reference_first5_sha256=sha(root/'REFERENCE_FIRST5.json'),reference_epoch25_sha256=sha(root/'REFERENCE_EPOCH25.json'),
 task_card_sha256=sha(root/'TASK_CARD.md'),remote_staging_root=json.loads((root/'WORK_STARTED.json').read_text(encoding='utf-8'))['remote_staging_root'])
assert pins['descriptor_sha256']=='b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6'
save(root/'PINNED_INPUTS.json',pins)
helpers=['owned_processes.py','gate.py','scheduler_handoff.py','cpu36_contract.py','submit_once.py','run_job.sh','recheck_fixed_inputs.py']
save(root/'UNCHANGED_HELPERS.json',{n:dict(source=str(old/n),sha256=sha(root/n),unchanged=sha(root/n)==sha(old/n)) for n in helpers})
assert all(sha(root/n)==sha(old/n) for n in helpers)
diff=[]
for name in ['prepare.py','review_gate.py','run_job.py','collect_evidence.py']:
    diff.extend(difflib.unified_diff((old/name).read_text(encoding='utf-8').splitlines(True),(root/name).read_text(encoding='utf-8').splitlines(True),fromfile='R11/'+name,tofile='R12/'+name))
for name in ['r12_outcome.py','inspect_metadata.py','check_old_inputs.py','tests/test_r12_deployment.py']:
    diff.extend(difflib.unified_diff([], (root/name).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='R12/'+name))
(root/'MINIMAL.diff').write_text(''.join(diff),encoding='utf-8',newline='\n')
names=sorted(set([p.name for p in root.glob('*.py')]+[p.name for p in root.glob('*.sh')]+['tests/test_r12_deployment.py','ENGINEERING_DESCRIPTOR.json','EXPOSURE_LEDGER_INITIAL.json','R12_CONTRACT.json','REFERENCE_FIRST5.json','REFERENCE_EPOCH25.json','TASK_CARD.md','PINNED_INPUTS.json','S02_R12_READY.json','S02_SOURCE_SHA256.json','S02_R12_DW_TWO_COLUMN_TILES.zip','COMMANDS.md','MINIMAL.diff','UNCHANGED_HELPERS.json','OLD_INPUT_IDENTITIES.json']))
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
save(root/'evidence/FROZEN_INPUT_CHECKS.json',dict(status='ALL_R12_READY_ASSETS_AND_ZIP_PASS',assets=assets,zip_source_entries=len(manifest),actual_KML='NOT_RUN'))
print(json.dumps(receipt))
