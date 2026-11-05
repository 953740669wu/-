"""Only this complete five-update numerical PASS unlocks memory preparation."""
import json
from pathlib import Path
import sys

from diagnostic_common import sha_file
import sequence_runtime

ROOT = Path(__file__).resolve().parent
REQUIRED_CONFIG = dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
    reference_checkpoint=False, candidate_checkpoint=True, precision='fp32', threads=36, hbm=False,
    history='fresh_once_then_continuous', updates=5, repeated_same_fixed_case=True, loss='original_mean')
FAMILIES = dict(loss=1, input_v=1, input_y0=1, output=3, grad=153, param=299, delta=299, state=306)


def validate(data, frozen, source_sha256, manifest_sha256):
    if (data.get('status') != 'PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY'
            or data.get('mode') != 'sequence5_strict' or data.get('completed_steps') != 5
            or data.get('comparison_failures') != 0):
        raise ValueError('complete new five-step strict PASS required; one-step PASS is insufficient')
    if any(data.get('config', {}).get(key) != value for key, value in REQUIRED_CONFIG.items()):
        raise ValueError('wrong five-step configuration')
    if (data.get('source_sha256') != source_sha256 or data.get('source_manifest_sha256') != manifest_sha256
            or data.get('case_file_sha256') != frozen['sha256'] or data.get('case_identity') != frozen['identity']):
        raise ValueError('wrong five-step source/case identity')
    records = data.get('steps', [])
    if len(records) != 5 or data.get('runtime', {}).get('backend') != 'kml':
        raise ValueError('missing steps/actual KML')
    previous, identities, metric_names = None, None, None
    for step, record in enumerate(records, 1):
        if (record['step'] != step or record['comparison_failures'] != 0 or record['failures'] != []
                or record['case_file_sha256'] != frozen['sha256'] or record['source_manifest_sha256'] != manifest_sha256):
            raise ValueError('failed/misidentified sequence step')
        metrics = record['metrics']; names = [item['name'] for item in metrics]
        families = {}
        for item in metrics:
            family = item['name'].split('.')[0]; families[family] = families.get(family, 0) + 1
        if (len(names) != len(set(names)) or families != FAMILIES
                or any(item.get('passed') is not True for item in metrics)
                or (metric_names is not None and names != metric_names)):
            raise ValueError('incomplete/failed/changed original metric coverage')
        metric_names = names
        lineage = [record['lineage'][side] for side in ('reference','candidate')]
        if step == 1 and lineage[0]['before_digest'] != lineage[1]['before_digest']:
            raise ValueError('reference and candidate did not start from the same state')
        if previous is not None and [item['before_digest'] for item in lineage] != previous:
            raise ValueError('parameter/optimizer digest chain broken')
        current_ids = []
        for item in lineage:
            before, after = item['before'], item['after']
            if (item['step'] != step or before['completed_updates'] != step-1 or after['completed_updates'] != step
                    or before['optimizer_step_min'] != step-1 or before['optimizer_step_max'] != step-1
                    or before['optimizer_states'] != (0 if step == 1 else 153)
                    or after['optimizer_step_min'] != step or after['optimizer_step_max'] != step
                    or after['optimizer_states'] != 153 or not before['input_gradients_cleared']
                    or not before['parameter_gradients_cleared']):
                raise ValueError('optimizer steps/gradient cleanup not continuous')
            if (before['model_id'],before['optimizer_id']) != (after['model_id'],after['optimizer_id']):
                raise ValueError('model/optimizer recreated within update')
            current_ids.append((after['model_id'],after['optimizer_id']))
        if identities is not None and identities != current_ids:
            raise ValueError('model/optimizer recreated across updates')
        if current_ids[0][0] == current_ids[1][0] or current_ids[0][1] == current_ids[1][1]:
            raise ValueError('reference and candidate must be isolated instances')
        identities = current_ids; previous = [item['after_digest'] for item in lineage]
        if set(record['kml_calls']) != {'reference','candidate'} or any(x <= 0 for x in record['kml_calls'].values()):
            raise ValueError('missing actual KML on a sequence side/step')
    sequence_runtime.validate(data['cpu36'], 'strict', 5)


def check_path(path):
    data = json.loads(path.read_text())
    source = data.get('source_sha256', {})
    required = {'check_sequence5.py','sequence_core.py','sequence_runtime.py','candidate/full_batch_step.py',
                'candidate/training_step.py','tests/check_equivalence.py','cpu36_guard.py','cpu36_contract.py'}
    if not required <= set(source):
        raise ValueError('five-step source identity required; old one-step result refused')
    actual = {name: sha_file(ROOT / name) for name in source}
    validate(data, json.loads((ROOT/'CASE_MANIFEST.json').read_text()), actual, sha_file(ROOT/'SOURCE_SHA256.json'))
    return dict(path=str(path.resolve()), sha256=sha_file(path), source_manifest_sha256=data['source_manifest_sha256'],
                strict_libraries={item['path']: item['sha256'] for item in data['runtime']['libraries']},
                status='FIVE_STEP_PASS_REFERENCE_ONLY_NOT_SUBMISSION_AUTHORIZATION')


if __name__ == '__main__':
    print(json.dumps(check_path(Path(sys.argv[1])), indent=2))
