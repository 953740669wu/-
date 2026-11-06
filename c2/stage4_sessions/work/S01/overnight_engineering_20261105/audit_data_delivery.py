"""Read-only metadata/receipt cross-check; never loads shared NPZ or trains."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import random

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / 'S00/overnight_engineering_20261105'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def asset(info):
    path = Path(info['path'])
    raw = path.read_bytes()
    assert len(raw) == info['bytes'] and hashlib.sha256(raw).hexdigest() == info['sha256'], str(path)
    return load(path)


ready = load(DATA / 'DATA_READY.json')
assert ready['status'] == 'DATA_READY' and ready['protocol'] == 'ENGINEERING_REAL_CORPUS_PILOT_V1'
description, checks, ledger = [asset(ready[name]) for name in ('descriptor', 'sample_checks', 'exposure_ledger')]
interface = asset(ready['interface'])
assert ready['interface_sha256'] == description['interface_sha256'] == ready['interface']['sha256']
assert hashlib.sha256((HERE / 'INTERFACE_FROZEN_COPY.json').read_bytes()).hexdigest() == ready['interface_sha256']
anchor = interface['source_anchor']['manifest_sha256']
assert ready['manifest_sha256'] == description['corpus']['manifest']['sha256'] == anchor
assert checks['manifest']['sha256'] == checks['manifest_after_sha256'] == anchor
assert checks['manifest']['bytes'] == ready['manifest']['bytes'] == 3399057
assert description['corpus']['manifest'] == ready['manifest']
assert checks['original_case_range']['sha256'] == description['selection']['cases_txt']['sha256']
for value in (ready, description, checks, ledger):
    assert value['engineering_only'] is True and value['formal_split_status'] == value['subject_mapping_status'] == 'UNKNOWN'
    assert value['validation_status'] == 'NOT_RUN_NO_FORMAL_SPLIT'
assert not {'split', 'mapping', 'val', 'test'}.intersection(description)
assert description['status'] == 'ENGINEERING_DATA_READY' and description['data_origin'] == 'REAL_CORPUS_ENGINEERING_SAMPLES'
assert description['selection']['seed'] == checks['selection_seed'] == 2026
assert description['selection']['preferred_scope_used'] is True
pool = checks['candidate_cases']
assert pool == sorted(set(pool)) and len(pool) == 119
assert sorted(random.Random(2026).sample(pool, 2)) == ready['selected_cases'] == description['selection']['selected_cases']
units = description['train']
assert [(u['case'], u['unit']) for u in units] == sorted((u['case'], u['unit']) for u in units)
assert len(units) == len({u['unit'] for u in units}) == ready['total_units'] == 16
assert Counter(u['case'] for u in units) == dict.fromkeys(ready['selected_cases'], 8)
assert sum(u['n_pairs'] for u in units) == ready['total_frames'] == 1600
assert checks['total_frames'] == 1600 and checks['multiple_batches_at64'] is True
assert checks['training_consumed'] is False and checks['jobs_submitted'] == 0
assert len(checks['selected']) == len(ledger['units']) == 16
for u, c, e in zip(units, checks['selected'], ledger['units']):
    assert u['belt'] == '16_adjacent' and u['subject_id'] is None
    for name in ('case', 'unit', 'placement', 'contact', 'belt', 'n_pairs', 'path', 'sidecar_path', 'npz_sha256', 'sidecar_sha256'):
        assert u[name] == c[name], (u['unit'], name)
    assert Path(u['path']).stem == Path(u['sidecar_path']).stem == u['unit']
    for name in ('case', 'unit', 'npz_sha256', 'sidecar_sha256'):
        assert u[name] == e[name]
    assert e['selection_status'] == 'SELECTED_RESERVED' and e['usage_status'] == 'NOT_STARTED'
    for field, identity in (('npz', 'npz_identity'), ('sidecar', 'sidecar_identity')):
        assert c[identity]['sha256'] == u[field + '_sha256'] and c[identity]['bytes'] == u[field + '_bytes']
    assert c['code_hash'] == description['corpus']['code_hash'] == 'd8b2be8d1f'
    assert c['config_hash'] == description['corpus']['config_hash'] == 'b1049eac1a'
    assert c['status'] == 'PASS_FINITE_PAIRED_REAL_UNIT_ONLY' and c['same_belt_unit_pair_rows'] is True
    assert all(a['finite'] is True for a in c['arrays'].values())
    assert c['arrays']['images']['shape'] == [100, 64, 64] and c['arrays']['v_cur']['shape'] == [100, 208]
    assert c['base_of_pair'] == c['states_baselines'] and len(c['base_of_pair']) == u['n_pairs'] == 100
    assert min(c['base_of_pair']) >= 0 and max(c['base_of_pair']) < c['arrays']['v_ref']['shape'][0]
    assert 0 < c['reference_denominator_min'] <= c['reference_denominator_max']
assert checks['image_absmax_engineering_train_only'] == max(c['image_absmax'] for c in checks['selected'])
assert description['exposure_ledger']['sha256'] == ready['exposure_ledger']['sha256']
assert description['runtime_exposure_ledger_path'].startswith(ready['remote_staging_root'] + '/payload/outputs/')
result = dict(status='DATA_RECEIPT_REVIEW_PASS_NOT_EXECUTION_RELEASE', descriptor=ready['descriptor'],
              data_ready_sha256=hashlib.sha256((DATA / 'DATA_READY.json').read_bytes()).hexdigest(),
              sample_checks=ready['sample_checks'], exposure_ledger=ready['exposure_ledger'],
              cases=ready['selected_cases'], units=16, frames=1600, planned_updates_at64=25,
              manifest_sha256=anchor, image_absmax=checks['image_absmax_engineering_train_only'],
              scope='Independent local cross-check of actual C2 metadata receipts; no independent NPZ reread',
              unit_selection_note='Required: verify exact unit selection against anchored manifest in the frozen loader when CODE_READY arrives; not yet reviewed')
(HERE / 'data_review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
for name in ('DATA_READY.json', 'ENGINEERING_DESCRIPTOR.json', 'EXPOSURE_LEDGER_INITIAL.json'):
    (HERE / ('S00_FROZEN_' + name)).write_bytes((DATA / name).read_bytes())
print(json.dumps(result, indent=2))
