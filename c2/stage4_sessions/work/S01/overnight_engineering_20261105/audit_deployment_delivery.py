"""Read-only frozen deployment identity and actual review-gate cross-check."""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import sys
import zipfile

HERE = Path(__file__).resolve().parent
S00 = HERE.parents[1] / 'S00/overnight_engineering_20261105'
S02 = HERE.parents[1] / 'S02/overnight_engineering_20261105'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(record):
    path = Path(record['path'])
    assert sha(path) == record['sha256'], str(path)
    if 'bytes' in record:
        assert path.stat().st_size == record['bytes']
    return path


ready = load(S00 / 'S00_DEPLOYMENT_READY.json')
code, data = load(HERE / 'code_review.json'), load(HERE / 'data_review.json')
assert ready['status'] == 'S00_DEPLOYMENT_READY' and ready['immutable_after_publish'] is True
assert ready['new_jobs'] == 0 and ready['node_count'] == ready['numa_domains'] == 1
assert ready['max_retry_count'] == 0 and ready['closing_seconds'] == 30 and ready['hbm'] is False
assert ready['protocol'] == 'ENGINEERING_REAL_CORPUS_PILOT_V1' and ready['engineering_only'] is True
for field in ('checks', 'code_ready', 'commands', 'data_ready', 'deployment_package', 'descriptor',
              'interface', 'linux_login_log', 'pre_freeze_resolution', 'source_manifest'):
    asset(ready[field])
assert ready['code_ready']['sha256'] == code['code_ready_sha256']
assert ready['data_ready']['sha256'] == data['data_ready_sha256']
assert ready['descriptor']['sha256'] == data['descriptor']['sha256']
assert ready['interface']['sha256'] == code['interface']['sha256']
assert asset(ready['code_ready']).read_bytes() == (S02 / 'CODE_READY.json').read_bytes()
assert asset(ready['data_ready']).read_bytes() == (HERE / 'S00_FROZEN_DATA_READY.json').read_bytes()
index = load(asset(ready['source_manifest']))
assert len(index) == 24
for name, digest in index.items():
    assert sha(S00 / name) == digest, name
target = HERE / 'frozen_deployment'
assert not target.exists(), 'keep frozen deployment audit copy immutable'
with zipfile.ZipFile(asset(ready['deployment_package'])) as archive:
    assert archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist())) == 27
    files = [name for name in archive.namelist() if not name.endswith('/')]
    assert len(files) == 26 and set(files) == set(index) | {'ARTIFACT_SHA256.json', 'ARTIFACT_SHA256.txt'}
    for name in files:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name
        assert archive.read(name) == (S00 / name).read_bytes(), name
    archive.extractall(target)
assert (target / 'S02_OVERNIGHT_ENGINEERING_CODE.zip').read_bytes() == asset(code['package']).read_bytes()
pins = load(target / 'PINNED_INPUTS.json')
assert pins['entrypoint'] == ready['actual_entrypoint'] == 'run_engineering.sh'
assert pins['entry_environment'] == ready['entry_environment'] == ['S02_ENGINEERING_DESCRIPTOR', 'S02_ENGINEERING_DESCRIPTOR_SHA256']
assert pins['code_package_sha256'] == code['package']['sha256']
assert pins['code_source_manifest_sha256'] == code['source_manifest']['sha256']
assert pins['descriptor_sha256'] == data['descriptor']['sha256']
assert pins['interface_sha256'] == code['interface']['sha256']
assert pins['remote_staging_root'] == ready['remote_staging_root']
for path in [*target.glob('*.py'), target / 'tests/test_deployment.py']:
    ast.parse(path.read_text(), feature_version=(3, 9))
    assert b'\r' not in path.read_bytes()
assert b'\r' not in (target / 'run_job.sh').read_bytes()
tree = ast.parse((target / 'run_job.py').read_text())
exports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and ast.unparse(node.func) == 'os.environ.update':
        exports.update(k.arg for k in node.keywords)
assert set(pins['entry_environment']) <= exports and 'S02_REAL_DESCRIPTOR' not in exports
resolution = load(asset(ready['pre_freeze_resolution']))
assert resolution['status'] == 'FIXED_BEFORE_FIRST_DEPLOYMENT_READY'
assert resolution['run_job_sha256'] == sha(target / 'run_job.py')
checks = load(asset(ready['checks']))
assert checks['status'] == 'PASS_LOCAL_AND_LOGIN_METADATA_ONLY'
assert checks['portable_tests'] == checks['linux_login_mock_tests'] == 12
assert checks['job_submitted'] is False and checks['full_model_on_login'] == 'NOT_RUN'
assert checks['real_engineering_metadata_gate'] == 'ENGINEERING_METADATA_HASH_GATE_PASS'
assert checks['zip_unpack_SHA'] is checks['inner_source_SHA'] is checks['linux_bash_n'] is checks['source_LF_AST39'] is True
log = asset(ready['linux_login_log']).read_text()
assert 'LOGIN_PREPARE_AND_METADATA_PASS_NO_MODEL_NO_JOB' in log
assert 'Ran 12 tests' in log and '\nOK' in log
metadata = next(json.loads(line) for line in log.splitlines() if line.startswith('{"status": "ENGINEERING_METADATA_HASH_GATE_PASS"'))
assert metadata['framework_imported'] is False and metadata['npz_arrays_read'] is False
assert metadata['identity']['descriptor_sha256'] == data['descriptor']['sha256']
assert metadata['identity']['units'] == load(asset(ready['descriptor']))['train']

# Use the frozen actual reviewer gate with concrete bindings, no scheduler calls.
sys.dont_write_bytecode = True
sys.path.insert(0, str(target))
import prepare
import review_gate
import submit_once
bindings = dict(code_package_sha256=code['package']['sha256'],
                code_source_manifest_sha256=code['source_manifest']['sha256'],
                deployment_package_sha256=ready['deployment_package']['sha256'],
                descriptor_sha256=data['descriptor']['sha256'], interface_sha256=code['interface']['sha256'])
assert bindings == ready['required_review_bindings']
assert prepare.RESOURCES == ready['resources']
candidate = dict(decision='PASS_FOR_ENGINEERING_PILOT', review_complete=True, bindings=bindings, resources=ready['resources'])
review_gate.validate(candidate, bindings)
rejected = []
for name in bindings:
    bad = dict(bindings)
    bad[name] = '0' * 64
    try:
        review_gate.validate(dict(candidate, bindings=bad), bindings)
    except ValueError:
        rejected.append(name)
    else:
        raise AssertionError(('binding was not enforced', name))
command = submit_once.command(PurePosixPath(ready['remote_staging_root']), 'a' * 64)
assert command[command.index('-x') + 1] == 'job' and command[command.index('-T') + 1] == '900'
assert 'cpu=38,mem=24576MB' in command and 'mem=24576MB' in command and 'numa[count=1,distribution=pack]' in command
assert command[-1] == 'a' * 64
result = dict(status='FROZEN_DEPLOYMENT_REVIEW_PASS', deployment_package=ready['deployment_package'],
              deployment_ready_sha256=sha(S00 / 'S00_DEPLOYMENT_READY.json'), bindings=bindings, resources=ready['resources'],
              source_index=ready['source_manifest'], zip_files=26, zip_entries=27,
              actual_export_wiring='PASS_FIXED_BEFORE_FIRST_DEPLOYMENT_READY',
              real_login_metadata_and_hash_gate='PASS_NO_MODEL_NO_JOB', linux_mock_test_receipts=12,
              exact_binding_positive=True, wrong_binding_rejections=rejected, command=command,
              unrun=['native PR_SET_CHILD_SUBREAPER/TERM/KILL cleanup', 'native job/NUMA/DDR/selected36',
                     'model PID Torch36/all TIDs/KML GEMM', 'real complete Encoder training/checkpoint/recovery'])
(HERE / 'deployment_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S00_FROZEN_S00_DEPLOYMENT_READY.json').write_bytes((S00 / 'S00_DEPLOYMENT_READY.json').read_bytes())
print(json.dumps(result, indent=2))
