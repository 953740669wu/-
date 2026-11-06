"""Audit frozen R11 deployment/receipts; no model, mock suite or scheduler call."""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import json
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
S00 = WORK / 'S00/round11_gemm_breakdown_20261106'
R9 = WORK / 'S00/round9_profile5_20261106'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(info):
    p = Path(info['path'])
    assert sha(p) == info['sha256'] and p.stat().st_size == info['bytes'], str(p)
    return p


ready, code = load(S00 / 'S00_DEPLOYMENT_READY.json'), load(HERE / 'code_review.json')
assert ready['status'] == 'S00_DEPLOYMENT_READY' and ready['immutable_after_publish'] is True
assert ready['protocol'] == 'ENGINEERING_REAL_CORPUS_GEMM5_V1'
assert ready['node_count'] == ready['numa_domains'] == 1 and ready['new_jobs'] == ready['max_retry_count'] == 0
for obj in ready.values():
    if isinstance(obj, dict) and 'path' in obj and 'sha256' in obj:
        asset(obj)
assert ready['gemm_ready']['sha256'] == code['gemm_ready']['sha256']
for name, source in [('interface', 'interface'), ('gemm_contract', 'contract'), ('reference_first5', 'reference'), ('descriptor', 'descriptor')]:
    assert ready[name]['sha256'] == code[source]['sha256']
assert ready['resources'] == load(asset(code['contract']))['resources']
assert ready['entrypoint'] == 'run_gemm5.sh' and ready['entry_environment'] == ['S02_ENGINEERING_DESCRIPTOR', 'S02_ENGINEERING_DESCRIPTOR_SHA256']
assert ready['workload'] == dict(actual_train_frames=320, continuous_updates=5, new_sample_selection=False,
    normalization_frames=1600, old_checkpoint_loaded=False, sampled_steps=[3, 4, 5], warmup_steps=[1, 2])
assert ready['limits'] == dict(detail_bytes_each=1048576, expected_records_per_sample=149, full_torch_profiler=False,
    max_detail_files=3, max_records_per_sample=256, over_limit='FAIL_STOP_NO_RETRY_NO_TRUNCATION')
index = load(asset(ready['deployment_source_manifest']))
assert len(index) == 26
target = HERE / 'frozen_deployment'
assert not target.exists(), 'keep first frozen audit copy immutable'
with zipfile.ZipFile(asset(ready['deployment_package'])) as archive:
    names = archive.namelist()
    assert archive.testzip() is None and len(names) == len(set(names)) == 29
    files = [n for n in names if not n.endswith('/')]
    assert len(files) == 28 and set(files) == set(index) | {'ARTIFACT_SHA256.json', 'ARTIFACT_SHA256.txt'}
    for name in files:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name and '\\' not in name
        assert archive.read(name) == (S00 / name).read_bytes(), name
    archive.extractall(target)
for name, digest in index.items():
    assert sha(S00 / name) == digest
    if name.endswith('.py'):
        ast.parse((S00 / name).read_text(encoding='utf-8'), feature_version=(3, 9))
assert (target / 'S02_R11_GEMM5_CODE.zip').read_bytes() == asset(code['package']).read_bytes()
assert sha(target / 'S02_SOURCE_SHA256.json') == code['source_manifest']['sha256']
pins = load(target / 'PINNED_INPUTS.json')
assert pins['entrypoint'] == ready['entrypoint'] and pins['entry_environment'] == ready['entry_environment']
assert pins['remote_staging_root'] == ready['remote_staging_root']
common = ('cpu36_contract.py', 'gate.py', 'owned_processes.py', 'scheduler_handoff.py', 'submit_once.py', 'run_job.sh')
assert all((target / n).read_bytes() == (R9 / n).read_bytes() for n in common)
def functions(path):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}
assert functions(target / 'prepare.py') == functions(R9 / 'prepare.py')
checks = load(asset(ready['checks']))
assert checks['status'] == 'LOCAL_AND_LINUX_LOGIN_DEPLOYMENT_PASS_NO_MODEL'
assert checks['local_fixture_tests'] == checks['linux_login_fixture_tests'] == 9
assert checks['actual_KML'] == checks['fault_signal_cleanup'] == 'NOT_RUN'
assert checks['metadata_hash_gate'] == 'ENGINEERING_METADATA_HASH_GATE_PASS'
fixed = load(asset(checks['original_fixed16_files_sha']))
assert fixed['status'] == 'FIXED16_CURRENT_SOURCE_SHA_PASS' and fixed['units'] == 16
assert fixed['arrays_read'] is fixed['model_run'] is False
description = load(asset(ready['descriptor']))
by_path = {x['path']: x for x in fixed['checked']}
assert len(by_path) == len(fixed['checked']) == fixed['files'] == 36
assert by_path[description['corpus']['manifest']['path']]['sha256'] == description['corpus']['manifest']['sha256']
for unit in description['train']:
    for path_key, prefix in [('path', 'npz'), ('sidecar_path', 'sidecar')]:
        assert by_path[unit[path_key]]['sha256'] == unit[prefix + '_sha256']
        assert by_path[unit[path_key]]['bytes'] == unit[prefix + '_bytes']
raw = asset(ready['linux_login_log']).read_text(encoding='utf-8')
clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw)
assert 'Ran 9 tests' in clean and '\nOK' in clean and 'R11_LOGIN_DEPLOYMENT_PASS' in clean
assert 'ENGINEERING_METADATA_HASH_GATE_PASS' in clean
assert 'Ran 9 tests' in (S00 / 'evidence/tests_after.txt').read_text(encoding='utf-8')
attempt = load(S00 / 'evidence/OPTIONAL_METADATA_ATTEMPT.json')
assert attempt['status'] == 'NO_RESULT_OWN_READONLY_SSH_INTERRUPTED' and attempt['replacement_pass'] is True

# Exact gate consumption is the only local invocation; author fixture suites are not repeated.
sys.dont_write_bytecode = True
sys.path.insert(0, str(target))
import prepare
import review_gate
import submit_once
bindings = ready['required_review_bindings']
assert bindings == dict(code_package_sha256=code['package']['sha256'], code_source_manifest_sha256=code['source_manifest']['sha256'],
    deployment_package_sha256=ready['deployment_package']['sha256'], deployment_source_manifest_sha256=ready['deployment_source_manifest']['sha256'],
    descriptor_sha256=code['descriptor']['sha256'], interface_sha256=code['interface']['sha256'],
    gemm_contract_sha256=code['contract']['sha256'], reference_first5_sha256=code['reference']['sha256'])
assert prepare.RESOURCES == ready['resources']
review_gate.validate(dict(decision='PASS_FOR_ENGINEERING_GEMM5', review_complete=True, bindings=bindings, resources=ready['resources']), bindings)
command = submit_once.command(PurePosixPath(ready['remote_staging_root']), 'a' * 64)
assert command[command.index('-x') + 1] == 'job' and command[command.index('-T') + 1] == '900'
assert 'cpu=38,mem=24576MB' in command and 'mem=24576MB' in command and 'numa[count=1,distribution=pack]' in command
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
result = dict(status='GEMM5_DEPLOYMENT_REVIEW_PASS', deployment_package=ready['deployment_package'],
    deployment_source_manifest=ready['deployment_source_manifest'], deployment_ready_sha256=sha(S00 / 'S00_DEPLOYMENT_READY.json'),
    bindings=bindings, resources=ready['resources'], source_files=26, zip_members=29, zip_files=28,
    local_test_receipts=9, linux_login_fixture_receipts=9, inherited_byte_identical_helpers=list(common),
    inherited_prepare_function_AST='UNCHANGED_EXCEPT_MODULE_CONSTANTS', original_fixed_units=16, original_fixed_file_receipts=36,
    optional_metadata_attempt='INTERRUPTED_NO_RESULT_PRESERVED; independent bounded SHA replacement and later login metadata gate PASS',
    terminal_log_ansi='Original retained; escape stripping only for token checks, no synthetic JSON or mtime restoration',
    exact_actual_review_gate='CONSUMED_CONCRETE_8_BINDINGS_SUCCESSFULLY', command=command,
    independent_model_or_mock_suite_runs=0, blocking_findings=[],
    unrun=['actual C2 _sgemm ctypes and three149-record pairings', 'original first5 loss/actual CPU36/KML/TID/restore',
           'native signal-fault cleanup this round and final job/PID termination'])
(HERE / 'deployment_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S00_FROZEN_DEPLOYMENT_READY.json').write_bytes((S00 / 'S00_DEPLOYMENT_READY.json').read_bytes())
print(json.dumps({k: v for k, v in result.items() if k != 'command'}, indent=2))
