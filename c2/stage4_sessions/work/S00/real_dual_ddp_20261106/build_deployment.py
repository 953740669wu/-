"""Build once from the actual frozen S02/S07 deliveries; no job or framework."""
import ast
import difflib
import json
from pathlib import Path
import zipfile
from prepare import sha, save, check_archive, DEPLOYMENT, RESOURCES, WORKLOAD

root = Path(__file__).resolve().parent
if (root/DEPLOYMENT).exists(): raise FileExistsError('frozen outer ZIP already exists')
s02 = root.parents[1]/'S02/real_dual_ddp_reference_20261106'
s07 = root.parents[1]/'S07/real_dual_ddp_20261106'
r02 = json.loads((root/'REFERENCE_READY.json').read_text(encoding='utf-8'))
r07 = json.loads((root/'TRAINING_READY.json').read_text(encoding='utf-8'))
assert r07['code_frozen'] and r07['ready_for_s00_packaging']
assert r07['local_numerical_gate'] == 'FAIL_ORIGINAL_THRESHOLDS_PRESERVED'
packages = []
upstream = {}


def source(path, digest=None):
    path = Path(path).resolve()
    actual = sha(path)
    if digest is not None and actual != digest: raise ValueError('upstream drift: '+str(path))
    upstream[str(path)] = dict(path=str(path), bytes=path.stat().st_size, sha256=actual)
    return actual


for destination, ready, author, archive, manifest in [
    ('reference', r02, s02, 'S02_REAL_DUAL_DDP_REFERENCE.zip', 'SOURCE_SHA256.json'),
    ('training', r07, s07, 'S07_REAL_DUAL_DDP.zip', 'SOURCE_MANIFEST.json')]:
    source(Path(ready['package']['path']), ready['package']['sha256'])
    source(Path(ready['source_manifest']['path']), ready['source_manifest']['sha256'])
    if sha(root/archive) != ready['package']['sha256']: raise ValueError('copied archive drift')
    with zipfile.ZipFile(root/archive) as z:
        data = json.loads(z.read(manifest))
    files = data if destination == 'reference' else {x['path']:x['sha256'] for x in data['delivery_files']}
    files = dict(files, **{manifest:ready['source_manifest']['sha256']})
    if len(files) != (18 if destination == 'reference' else 20): raise ValueError('frozen file count differs')
    check_archive(root/archive, files)
    for name, digest in files.items(): source(author/name, digest)
    packages.append(dict(destination=destination, archive=archive, sha256=ready['package']['sha256'], files=files))
    with zipfile.ZipFile(root/archive) as z:
        for name in files:
            if name.endswith('.py'):
                raw = z.read(name)
                if b'\r' in raw: raise ValueError('non-LF inner Python source')
                ast.parse(raw.decode(), feature_version=(3,9))
source(s02/'REFERENCE_READY.json', sha(root/'REFERENCE_READY.json'))
source(s07/'TRAINING_READY.json', sha(root/'TRAINING_READY.json'))
source(Path(r07['local_checks']['path']), sha(root/'evidence/S07_LOCAL_CHECKS.json'))
source(Path(r02['local_checks']['path']), sha(root/'evidence/S02_LOCAL_CHECKS.json'))
local_checks = json.loads(Path(r07['local_checks']['path']).read_text(encoding='utf-8'))
source(s07/local_checks['groups'][-1]['strict_pair_evidence'], sha(root/'evidence/S07_LOCAL_STRICT_PAIR_METRICS.json'))
source(Path(r07['task_card']['path']), sha(root/'TASK_CARD.md'))
source(root.parent/'overnight_engineering_20261105/ENGINEERING_DESCRIPTOR.json', sha(root/'ENGINEERING_DESCRIPTOR.json'))
runtime = json.loads((root/'RUNTIME_CONTRACT.json').read_text(encoding='utf-8'))
source(runtime['environment_source']['path'], runtime['environment_source']['sha256'])
binding = json.loads((s07/'reference_binding.json').read_text(encoding='utf-8'))
assert binding['ready_sha256'] == sha(root/'REFERENCE_READY.json')
assert binding['package']['sha256'] == packages[0]['sha256']
assert {x['path']:x['sha256'] for x in binding['files']} == packages[0]['files']
bindings = dict(reference_package_sha256=packages[0]['sha256'], training_package_sha256=packages[1]['sha256'],
    reference_ready_sha256=sha(root/'REFERENCE_READY.json'), training_ready_sha256=sha(root/'TRAINING_READY.json'),
    reference_source_manifest_sha256=r02['source_manifest']['sha256'], training_source_manifest_sha256=r07['source_manifest']['sha256'],
    training_entry_sha256=r07['entry']['sha256'], training_config_sha256=r07['config']['sha256'],
    reference_binding_sha256=r07['reference_binding']['sha256'], model_sha256=r02['baseline']['model']['sha256'],
    baseline_kml_sha256=r02['baseline']['kml']['sha256'], comparator_sha256=r02['comparator']['sha256'],
    reference_first5_sha256=packages[0]['files']['REFERENCE_FIRST5.json'], reference_epoch25_sha256=packages[0]['files']['REFERENCE_EPOCH25.json'],
    corpus_manifest_sha256=r02['data_anchors']['manifest'], engineering_interface_sha256=r02['data_anchors']['interface'],
    runtime_contract_sha256=sha(root/'RUNTIME_CONTRACT.json'), installed_ddp_sha256=sha(root/'evidence/C2_INSTALLED_DDP.py'),
    upstream_local_checks_sha256=sha(root/'evidence/S07_LOCAL_CHECKS.json'),
    upstream_local_failed_metrics_sha256=sha(root/'evidence/S07_LOCAL_STRICT_PAIR_METRICS.json'))
envroot = '/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4'
environment = dict(PATH=envroot+'/venv/bin:/usr/bin:/bin', PYTHONPATH='/home/share/songzhenlong/eitfm/sw/torch_kml',
    PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', HBM='0', LINEAR_DTYPE='fp32',
    KML_BLAS_LIB='/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so',
    LD_LIBRARY_PATH='/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib',
    LD_PRELOAD=envroot+'/S01_payload/lib/libkml_sgemm_shim.so', **runtime['threading'])
checks = [dict(package='training',path='tests/'+name,methods=count)
          for name,count in r07['test_methods_by_file'].items() if name != 'test_training_torch.py']
checks.append(dict(package='reference',path='tests/test_dual_reference.py',methods=7))
checks.append(dict(package='training',path='tests/test_training_torch.py',methods=2))
assert sum(x['methods'] for x in checks) == 26
save(root/'PINNED_INPUTS.json', dict(packages=packages, bindings=bindings, upstream_files=list(upstream.values()),
    remote_staging_root=json.loads((root/'WORK_STARTED.json').read_text())['remote_staging_root'],
    python=runtime['python'], runtime_sha256=runtime['sha256'], training_environment=environment,
    descriptor_sha256=sha(root/'ENGINEERING_DESCRIPTOR.json'), linux_checks=checks,
    upstream_local_numerical_gate=r07['local_numerical_gate'], resources=RESOURCES, workload=WORKLOAD))
changes = []
for name in ['prepare.py','gate.py','run_job.py','run_job.sh','review_gate.py','submit_once.py','collect_evidence.py']:
    old = root.parent/'round12_dw_ab_20261106'/name
    changes.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(keepends=True),
        (root/name).read_text(encoding='utf-8').splitlines(keepends=True), fromfile='R12/'+name,tofile='REAL_DUAL_DDP/'+name))
(root/'MINIMAL.diff').write_text(''.join(changes),encoding='utf-8',newline='\n')
assets = ['prepare.py','gate.py','run_job.py','run_job.sh','review_gate.py','submit_once.py',
    'collect_evidence.py','owned_processes.py','scheduler_handoff.py','validate_release.py','tests/test_deployment.py',
    'S02_REAL_DUAL_DDP_REFERENCE.zip','S07_REAL_DUAL_DDP.zip','REFERENCE_READY.json','TRAINING_READY.json',
    'S02_SOURCE_SHA256.json','S07_SOURCE_MANIFEST.json','S02_INTERFACE_READY.json','S07_INTERFACE_READY.json',
    'ENGINEERING_DESCRIPTOR.json','RUNTIME_CONTRACT.json','R4_RUNTIME.env','PINNED_INPUTS.json','TASK_CARD.md',
    'DECISIONS_BEFORE_CODE.md','MINIMAL.diff','COMMANDS.md','evidence/S07_LOCAL_CHECKS.json',
    'evidence/S07_LOCAL_STRICT_PAIR_METRICS.json','evidence/S02_LOCAL_CHECKS.json','evidence/C2_INSTALLED_DDP.py',
    'evidence/SHARED_RUNTIME_IDENTITIES.json','evidence/LOCAL_ORIGINAL_ANCHORS.json','evidence/READONLY_RESUME.json',
    'evidence/LINUX_WRAPPER_PREPARATION_RECEIPT.json','evidence/REUSED_COMPONENTS.json']
save(root/'ARTIFACT_SHA256.json', {name:sha(root/name) for name in assets})
with zipfile.ZipFile(root/DEPLOYMENT,'x',zipfile.ZIP_DEFLATED) as z:
    for name in assets+['ARTIFACT_SHA256.json']: z.write(root/name,name)
save(root/'evidence/OUTER_BUILD_RECEIPT.json',dict(package=DEPLOYMENT, bytes=(root/DEPLOYMENT).stat().st_size,
    sha256=sha(root/DEPLOYMENT),source_manifest_sha256=sha(root/'ARTIFACT_SHA256.json'), files=len(assets)+1,
    upstream_local_numerical_gate=r07['local_numerical_gate'], job_submitted=False))
print(json.dumps(json.loads((root/'evidence/OUTER_BUILD_RECEIPT.json').read_text()),indent=2))
