"""Frozen R9 deployment and one targeted semantic-sampling check; stdlib only."""
from pathlib import Path, PurePosixPath
import ast
import hashlib
import importlib.util
import json
import sys
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
S00 = WORK / 'S00/round9_profile5_20261106'
S02 = WORK / 'S02/round9_profile5_20261106T023240Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(info):
    p = Path(info['path'])
    assert sha(p) == info['sha256'] and p.stat().st_size == info['bytes'], str(p)
    return p


ready = load(S00 / 'S00_DEPLOYMENT_READY.json')
code = load(HERE / 'code_review.json')
assert ready['status'] == 'S00_DEPLOYMENT_READY' and ready['immutable_after_publish'] is True
assert ready['protocol'] == 'ENGINEERING_REAL_CORPUS_PROFILE5_V1'
assert ready['node_count'] == ready['numa_domains'] == 1 and ready['new_jobs'] == ready['max_retry_count'] == 0
for value in ready.values():
    if isinstance(value, dict) and 'path' in value and 'sha256' in value:
        asset(value)
assert ready['profile_ready']['sha256'] == code['profile_ready']['sha256']
assert ready['profile_contract']['sha256'] == code['contract']['sha256']
assert ready['reference_first5']['sha256'] == code['reference']['sha256']
assert ready['descriptor']['sha256'] == code['descriptor']['sha256']
contract = load(asset(ready['profile_contract']))
assert ready['limits'] == contract['profiling']
assert ready['resources'] == contract['resources']
assert ready['workload'] == dict(actual_train_frames=320, continuous_updates=5, new_sample_selection=False,
    normalization_frames=1600, old_checkpoint_loaded=False, sampled_steps=[3, 4, 5], warmup_steps=[1, 2])
index = load(asset(ready['deployment_source_manifest']))
assert len(index) == 24
with zipfile.ZipFile(asset(ready['deployment_package'])) as archive:
    assert archive.testzip() is None and len(archive.namelist()) == len(set(archive.namelist())) == 27
    files = [name for name in archive.namelist() if not name.endswith('/')]
    assert len(files) == 26 and set(files) == set(index) | {'ARTIFACT_SHA256.json', 'ARTIFACT_SHA256.txt'}
    for name in files:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name
        assert archive.read(name) == (S00 / name).read_bytes(), name
    target = HERE / 'frozen_deployment'
    assert not target.exists(), 'do not overwrite frozen audit copies'
    archive.extractall(target)
for name, digest in index.items():
    assert sha(S00 / name) == digest
draft = load(HERE / 'preliminary_deployment_review.json')
for section in ('reviewed_modified_sources', 'unchanged_inherited_sources'):
    for name, digest in draft[section].items():
        assert sha(target / name) == digest, ('changed since read-only source review', name)
assert (target / 'S02_R9_PROFILE5_CODE.zip').read_bytes() == asset(code['package']).read_bytes()
assert sha(target / 'S02_SOURCE_SHA256.json') == code['source_manifest']['sha256']
pins = load(target / 'PINNED_INPUTS.json')
assert pins['entrypoint'] == ready['entrypoint'] == 'run_profile5.sh'
assert pins['entry_environment'] == ready['entry_environment'] == ['S02_ENGINEERING_DESCRIPTOR', 'S02_ENGINEERING_DESCRIPTOR_SHA256']
assert pins['remote_staging_root'] == ready['remote_staging_root']
for path in [*target.glob('*.py'), target / 'tests/test_profile_deployment.py']:
    ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))
    assert b'\r' not in path.read_bytes()
assert b'\r' not in (target / 'run_job.sh').read_bytes()
checks = load(asset(ready['checks']))
assert checks['status'] == 'PASS_NEW_PROFILE_DEPLOYMENT_LOCAL_AND_LOGIN_METADATA_ONLY'
assert checks['local_targeted_tests'] == checks['linux_login_targeted_tests'] == 8
assert checks['model_or_profiler_on_login'] == 'NOT_RUN' and checks['native_signal_fault_cleanup'] == 'NOT_EXERCISED_THIS_ROUND'
assert checks['metadata_gate'] == 'ENGINEERING_METADATA_HASH_GATE_PASS'
log = asset(ready['linux_login_log']).read_text(encoding='utf-8')
assert 'Ran 8 tests' in log and '\nOK' in log
assert 'R9_LOGIN_SHA_SYNTAX_METADATA_PASS_NO_MODEL_NO_JOB' in log
metadata = next(json.loads(line) for line in log.splitlines() if line.startswith('{"status": "ENGINEERING_METADATA_HASH_GATE_PASS"'))
assert metadata['framework_imported'] is metadata['npz_arrays_read'] is False
assert metadata['identity']['descriptor_sha256'] == code['descriptor']['sha256']
assert metadata['identity']['units'] == load(asset(ready['descriptor']))['train']
project = WORK.parents[2]
protected = load(S00 / 'evidence/PROTECTED_BEFORE.json')
for name, info in protected.items():
    path = Path(name) if Path(name).is_absolute() else project / name
    assert sha(path) == info['sha256'] and path.stat().st_size == info['bytes'], name

# The sole added coverage check addresses semantic rejection beyond checksum rejection.
sys.dont_write_bytecode = True
sys.path.insert(0, str(target))
import profile_outcome
import prepare
import review_gate
import submit_once
spec = importlib.util.spec_from_file_location('frozen_fixture', target / 'tests/test_profile_deployment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
case = module.ProfileDeploymentTests()
case.root = HERE / 'independent_fixture'
case.run = case.root / 'payload/outputs/profile_42'
case.run.mkdir(parents=True)
case.fixture()  # Does not call setUp; every write targets S01's local fixture.
positive = profile_outcome.inspect(case.root, '42')
assert positive['profile5_complete'] is True and positive['errors'] == []
trace_path = case.run / 'trace_step_3.json'
trace = load(trace_path)
trace['traceEvents'] = [x for x in trace['traceEvents'] if x['name'] != 'S02/backward']
trace_path.write_text(json.dumps(trace), encoding='utf-8')
summary_path = case.run / 'events_step_3.json'
summary = load(summary_path)
summary['events'] = len(trace['traceEvents'])
summary_path.write_text(json.dumps(summary), encoding='utf-8')
steps_path = case.run / 'steps.jsonl'
steps = [json.loads(line) for line in steps_path.read_text(encoding='utf-8').splitlines()]
steps[2]['profile']['events'] = len(trace['traceEvents'])
for key, path in [('trace', trace_path), ('summary', summary_path)]:
    steps[2]['profile'][key].update(bytes=path.stat().st_size, sha256=sha(path))
steps_path.write_text(''.join(json.dumps(x) + '\n' for x in steps), encoding='utf-8')
negative = profile_outcome.inspect(case.root, '42')
assert negative['profile5_complete'] is False
assert any('required phase events missing' in e for e in negative['errors'])
assert not any('SHA/bytes mismatch' in e for e in negative['errors'])
semantic = dict(scope='LOCAL_FIXTURE_STDLIB_ONLY_NO_MODEL_NO_PROFILER', positive=positive, negative=negative,
    change='Removed backward event; refreshed events count and both file SHA/bytes so the semantic guard is reached',
    author_sources_changed=False)
(HERE / 'independent_sampling_semantics.json').write_text(json.dumps(semantic, indent=2) + '\n', encoding='utf-8')
bindings = ready['required_review_bindings']
assert bindings == dict(code_package_sha256=code['package']['sha256'], code_source_manifest_sha256=code['source_manifest']['sha256'],
    deployment_package_sha256=ready['deployment_package']['sha256'], deployment_source_manifest_sha256=ready['deployment_source_manifest']['sha256'],
    descriptor_sha256=code['descriptor']['sha256'], interface_sha256=sha(target / 'INTERFACE.json'),
    profile_contract_sha256=code['contract']['sha256'], reference_first5_sha256=code['reference']['sha256'])
assert prepare.RESOURCES == ready['resources']
candidate = dict(decision='PASS_FOR_ENGINEERING_PROFILE5', review_complete=True, bindings=bindings, resources=ready['resources'])
review_gate.validate(candidate, bindings)
for change in (dict(decision='PASS_FOR_ENGINEERING_PILOT'),
               dict(bindings=dict(bindings, reference_first5_sha256='0' * 64)),
               dict(bindings=dict(bindings, deployment_source_manifest_sha256='0' * 64))):
    try:
        review_gate.validate(dict(candidate, **change), bindings)
    except ValueError:
        pass
    else:
        raise AssertionError(('failed exact new approval guard', change))
command = submit_once.command(PurePosixPath(ready['remote_staging_root']), 'a' * 64)
assert command[command.index('-x') + 1] == 'job' and command[command.index('-T') + 1] == '900'
assert 'cpu=38,mem=24576MB' in command and 'mem=24576MB' in command and 'numa[count=1,distribution=pack]' in command
result = dict(status='PROFILE5_DEPLOYMENT_REVIEW_PASS', deployment_package=ready['deployment_package'],
    deployment_source_manifest=ready['deployment_source_manifest'], deployment_ready_sha256=sha(S00 / 'S00_DEPLOYMENT_READY.json'),
    bindings=bindings, resources=ready['resources'], code_and_contract_and_reference_and_descriptor_match=True,
    source_review_identical_to_frozen_package=True, protected_original_files_unchanged=len(protected),
    source_files=24, zip_members=27, zip_files=26, local_test_receipts=8, login_test_receipts=8,
    independent_semantic_positive_and_missing_phase_negative='PASS_WITH_CHECKSUMS_REFRESHED',
    independent_exact_review_gate='PASS_REAL_BINDINGS_AND_OLD_DECISION_WRONG_REFERENCE_WRONG_DEPLOYMENT_INDEX_REJECTED',
    command=command, blocking_findings=[],
    unrun=['C2 CPU profiler capability and real 2+3 captures', 'real Torch36/KML/all TID profile execution',
           'native signal-fault cleanup this round', 'real first5 loss/checkpoint/zero-update recovery'])
(HERE / 'deployment_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S00_FROZEN_DEPLOYMENT_READY.json').write_bytes((S00 / 'S00_DEPLOYMENT_READY.json').read_bytes())
print(json.dumps({k: v for k, v in result.items() if k not in ('command',)}, indent=2))
