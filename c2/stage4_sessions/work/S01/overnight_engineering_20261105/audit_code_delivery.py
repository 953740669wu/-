"""Audit the frozen S02 ZIP and minimal independent metadata guards only."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import sys
import zipfile

HERE = Path(__file__).resolve().parent
S02 = HERE.parents[1] / 'S02/overnight_engineering_20261105'
R8 = S02.parent / 'round8_real_corpus_20261105T142243Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset(record):
    p = Path(record['path'])
    assert sha(p) == record['sha256'] and p.stat().st_size == record['bytes'], str(p)
    return p


ready = json.loads((S02 / 'CODE_READY.json').read_text())
assert ready['status'] == 'CODE_READY' and ready['immutable_after_publish'] is True
assert ready['protocol'] == 'ENGINEERING_REAL_CORPUS_PILOT_V1' and ready['engineering_only'] is True
for field in ('package', 'source_manifest', 'interface', 'checks', 'report', 'diff', 'compatibility'):
    asset(ready[field])
assert asset(ready['interface']).read_bytes() == (HERE / 'INTERFACE_FROZEN_COPY.json').read_bytes()
sources = json.loads(asset(ready['source_manifest']).read_text())
assert len(sources) == 28
reviewed = json.loads((HERE / 'preliminary_source_review.json').read_text())
for name, digest in reviewed['draft_source_sha256'].items():
    assert sources[name] == sha(S02 / name) == digest, ('changed since source review', name)
with zipfile.ZipFile(asset(ready['package'])) as archive:
    names = archive.namelist()
    assert len(names) == len(set(names)) == 29 and archive.testzip() is None
    assert set(names) == set(sources) | {'SOURCE_SHA256.json'}
    for name in names:
        assert not Path(name).is_absolute() and '..' not in Path(name).parts and ':' not in name
        assert archive.read(name) == (S02 / name).read_bytes(), name
    for name, digest in sources.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    target = HERE / 'frozen_code'
    assert not target.exists(), 'keep the frozen audit copy immutable'
    archive.extractall(target)
for name, digest in reviewed['original_r8_files_identical'].items():
    assert sha(R8 / name) == sha(S02 / name) == digest
for path in target.rglob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'), feature_version=(3, 9))
for name in ('run_engineering.sh', 'interfaces/cluster_runtime.env'):
    assert b'\r' not in (target / name).read_bytes()
checks = json.loads(asset(ready['checks']).read_text())
assert checks['status'] == 'PASS_LOCAL_PREPARED' and checks['test_count'] == 14
assert checks['full_encoder_runs'] == checks['jobs_submitted'] == 0 and checks['real_npz_read'] is False
for entry in checks['tests']:
    assert entry['exit'] == 0
    log = (S02 / entry['log']).read_text()
    assert '\nOK' in log and 'FAILED' not in log
for entry in checks['cli_rejections']:
    assert entry['exit'] == 2 and entry['before_framework'] is True
    result = json.loads(Path(entry['result']).read_text())
    assert result['status'] == 'DATA_NOT_READY' and 'cpu36' not in result

# Only a frozen stdlib module is imported; no author files are written and no Torch.
sys.dont_write_bytecode = True
sys.path.insert(0, str(target))
import engineering_data as data
import real_data
description = json.loads((HERE / 'S00_FROZEN_ENGINEERING_DESCRIPTOR.json').read_text())
data.validate_description(description)
rejections = []
for name, mutate in (
        ('formal_protocol', lambda d: d.update(protocol='REAL_CORPUS_PILOT_V1')),
        ('false_engineering', lambda d: d.update(engineering_only=False)),
        ('fabricated_validation', lambda d: d.update(validation_status='PASS')),
        ('third_source', lambda d: d['corpus']['manifest'].update(sha256='0' * 64)),
        ('invented_subject', lambda d: d['train'][0].update(subject_id='invented')),
        ('duplicate_unit', lambda d: d['train'].append(copy.deepcopy(d['train'][0])))):
    bad = copy.deepcopy(description)
    mutate(bad)
    try:
        data.validate_description(bad)
    except real_data.DataNotReady:
        rejections.append(name)
    else:
        raise AssertionError(('failed rejection', name))
try:
    real_data.load_descriptor(HERE / 'S00_FROZEN_ENGINEERING_DESCRIPTOR.json', sha(HERE / 'S00_FROZEN_ENGINEERING_DESCRIPTOR.json'))
except real_data.DataNotReady:
    rejections.append('formal_cli_module_rejects_engineering_descriptor')
else:
    raise AssertionError('formal loader accepted engineering descriptor')
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
result = dict(status='FROZEN_CODE_REVIEW_PASS_NOT_DEPLOYMENT_RELEASE', package=ready['package'],
              source_manifest=ready['source_manifest'], code_ready_sha256=sha(S02 / 'CODE_READY.json'),
              interface=ready['interface'], checks=ready['checks'], source_files=len(sources), zip_members=29,
              original_r8_files_unchanged=len(reviewed['original_r8_files_identical']),
              source_review_identical_to_frozen_package=True, local_test_receipts=14,
              independent_checks=dict(positive_engineering_metadata=1, rejected=rejections,
                                      torch_imported=False, numpy_imported=False),
              unrun=['actual Linux process cleanup', 'actual C2 Torch36/all TIDs/KML', 'real Encoder/checkpoint/recovery'])
(HERE / 'code_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
(HERE / 'S02_FROZEN_CODE_READY.json').write_bytes((S02 / 'CODE_READY.json').read_bytes())
print(json.dumps(result, indent=2))
