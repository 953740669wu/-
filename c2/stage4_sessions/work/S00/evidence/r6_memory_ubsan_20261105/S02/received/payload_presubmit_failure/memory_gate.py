"""Require this checkpoint candidate's actual strict result before memory work."""
import json
from pathlib import Path
import sys

import cpu36_guard
from diagnostic_common import sha_file

ROOT = Path(__file__).resolve().parent


def validate(data, frozen, actual_sources):
    if (data.get('status') != 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
            or data.get('mode') != 'checkpoint_strict' or data.get('comparison_failures') != 0):
        raise ValueError('checkpoint strict numerical PASS required; R5/control/FAIL is insufficient')
    config = data['config']
    required = dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
                    reference_checkpoint=False, candidate_checkpoint=True,
                    history='fresh', precision='fp32', threads=36)
    if any(config.get(key) != value for key, value in required.items()):
        raise ValueError('wrong checkpoint comparison configuration')
    if (data.get('case_file_sha256') != frozen['sha256'] or data.get('case_identity') != frozen['identity']
            or data.get('source_sha256') != actual_sources):
        raise ValueError('strict result case/source differs from current candidate')
    if (len(data.get('metrics', [])) != 1063 or data.get('failures') != []
            or any(item.get('passed') is not True for item in data['metrics'])):
        raise ValueError('missing/failed original strict metrics')
    runtime = data['runtime']
    if runtime.get('backend') != 'kml' or runtime.get('kml_gemm_calls', 0) <= 0:
        raise ValueError('actual KML execution evidence required')
    calls = data.get('kml_calls_by_side', {})
    if set(calls) != {'reference', 'candidate'} or any(value <= 0 for value in calls.values()):
        raise ValueError('both comparison paths require KML execution')
    state = data['cpu36']
    expected = ['before_framework', 'after_framework', 'after_backend', 'before_reference',
                'after_reference', 'after_candidate', 'publish']
    if state['errors'] or [item['name'] for item in state['checkpoints']] != expected:
        raise ValueError('incomplete CPU36 result')
    for item in state['checkpoints']:
        cpu36_guard.validate_checkpoint(item, state['receipt'])


if __name__ == '__main__':
    path = Path(sys.argv[1])
    data = json.loads(path.read_text())
    frozen = json.loads((ROOT / 'CASE_MANIFEST.json').read_text())
    sources = data.get('source_sha256', {})
    required = {'diagnose_update.py', 'candidate/full_batch_step.py', 'candidate/training_step.py',
                'tests/check_equivalence.py', 'cpu36_guard.py', 'cpu36_contract.py', 'CASE_MANIFEST.json'}
    if not required <= set(sources):
        raise ValueError('missing strict candidate source identity')
    actual = {name: sha_file(ROOT / name) for name in sources}
    validate(data, frozen, actual)
    print(json.dumps(dict(status='STRICT_CANDIDATE_PASS_REFERENCE_ONLY', path=str(path.resolve()),
                          sha256=sha_file(path), does_not_authorize_submission=True), indent=2))
