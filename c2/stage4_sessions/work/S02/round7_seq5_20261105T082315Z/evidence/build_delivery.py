"""Build this source-only sequence package; never generates case/model tensors."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'round6_ckpt64_20261105T043038Z'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


frozen=['baseline/s4_models.py','baseline/kml_ops.py','candidate/training_step.py','candidate/full_batch_step.py',
    'tests/check_equivalence.py','diagnostic_common.py','memory_metrics.py','cpu36_guard.py','cpu36_contract.py',
    'interfaces/cluster_runtime.env','CASE_MANIFEST.json','VALIDATION_PLAN.md','INPUT_PAIRING_PROTOCOL.md']
added=['sequence_core.py','sequence_runtime.py','check_sequence5.py','train_sequence5.py','sequence_gate.py',
       'run_sequence5.sh','run_s00_seq5_job.sh','tests/check_seq5_native.py','tests/test_sequence_contract.py','C2_HANDOFF.md']
payload=frozen+added
for name in frozen:assert (ROOT/name).read_bytes()==(OLD/name).read_bytes(),name
save(ROOT/'SOURCE_SHA256.json',{name:sha(ROOT/name) for name in payload})
payload+=['SOURCE_SHA256.json']
entries={}
patch=[]
for name in sorted(payload):
    path=ROOT/name;origin=OLD/name
    entries[name]=dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path),
        origin=str(origin.resolve()) if name in frozen else 'NEW_S02_R7',
        origin_sha256=sha(origin) if name in frozen else None,
        relation='BYTE_IDENTICAL_R6' if name in frozen else 'NEW_S02_R7')
    if path.suffix=='.py':ast.parse(path.read_text('utf-8'),feature_version=(3,9))
    if path.suffix in ('.sh','.env'):assert b'\r' not in path.read_bytes()
    if name in added and path.suffix in ('.py','.sh'):
        patch.extend(difflib.unified_diff([],path.read_text('utf-8').splitlines(True),fromfile='/dev/null',tofile='R7/'+name))
(ROOT/'diff/SEQUENCE5_ADDITIONS.patch').write_text(''.join(patch),encoding='utf-8',newline='\n')
(ROOT/'diff/R6_MEMORY_TO_SEQUENCE5.patch').write_text(''.join(difflib.unified_diff(
    (OLD/'train_memory.py').read_text('utf-8').splitlines(True),(ROOT/'train_sequence5.py').read_text('utf-8').splitlines(True),
    fromfile='R6/train_memory.py',tofile='R7/train_sequence5.py')),encoding='utf-8',newline='\n')
archive=ROOT/'package/S02_SEQUENCE5_R7_CODE.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name in sorted(payload):
        info=zipfile.ZipInfo(name,date_time=(2026,11,5,8,23,16));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=0o100644<<16;z.writestr(info,(ROOT/name).read_bytes())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==len(payload)
    assert all(hashlib.sha256(z.read(name)).hexdigest()==entries[name]['sha256'] for name in payload)
manifest=dict(version='S02_SEQUENCE5_R7_20261105',status='PREPARED_NOT_RUN_ON_C2',
    archive=archive.name,archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,entries=entries,
    frozen_r6_files=frozen,separate_case=dict(json.loads((ROOT/'CASE_MANIFEST.json').read_text()),
        source=str((ROOT.parent/'round3_20261104T134939Z/case/fixed_16_pre.pt').resolve())),
    config=dict(belt='16_adjacent',part='pre',effective_batch=64,microbatch=64,updates=5,
        reference_checkpoint=False,candidate_checkpoint=True,precision='fp32',backend='kml',hbm=False,
        history='fresh_once_then_continuous',loss='original_mean',repeat_same_case=True),
    acceptance=dict(metrics_per_step=1063,steps_required=5,old_one_step_pass_insufficient=True,
        failure_stops_sequence=True,memory_separate_processes=True,steady_state_claim=False),
    resources=dict(preferred_allocated_physical_cores=38,selected=36,reserved=2,memory_MB=24576,
        memory_limit_MB=24576,job_seconds=900,strict_timeout=780,memory_process_timeout=360,kill_after=15),
    environment=dict(OMP_NUM_THREADS='36',MKL_NUM_THREADS='36',OPENBLAS_NUM_THREADS='1',OMP_PLACES='cores',OMP_PROC_BIND='close'))
save(ROOT/'package/PACKAGE_MANIFEST.json',manifest)
(ROOT/'package/S02_SEQUENCE5_R7_CODE.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='ascii')
save(ROOT/'evidence/package_validation.json',dict(status='PASS_CRC_SHA_SIZE_SOURCE_ONLY',archive_sha256=sha(archive),
    archive_bytes=archive.stat().st_size,files=len(payload),frozen_files=len(frozen),full_model_runs=0,new_jobs=0,memory_runs=0))
print(json.dumps(dict(archive=str(archive.resolve()),sha256=sha(archive),bytes=archive.stat().st_size,files=len(payload)),indent=2))
