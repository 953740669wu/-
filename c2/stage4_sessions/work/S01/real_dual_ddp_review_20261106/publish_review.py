"""Publish one immutable refusal for the exact failed candidate; no execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
S01 = OWN.parent


def asset(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write_new(name, value):
    with (OWN / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    assert not (OWN / 'S01_REVIEW.json').exists(), 'published review is immutable'
    training = json.loads((OWN / 'training_review.json').read_text(encoding='utf-8'))
    deployment = json.loads((OWN / 'deployment_snapshot_review.json').read_text(encoding='utf-8'))
    assert training['status'] == 'FAIL_CURRENT_CANDIDATE_LOCAL_STRICT_NUMERICAL_GATE'
    inputs = {}
    for name in ('reference_review.json', 'training_review.json', 'deployment_snapshot_review.json'):
        value = json.loads((OWN / name).read_text(encoding='utf-8'))
        for row in value['inputs']:
            actual = asset(row['path'])
            assert actual == row, row['path']
            inputs[row['path']] = row
    write_new('FROZEN_INPUTS.json', dict(inputs=sorted(inputs.values(), key=lambda row: row['path']),
              deployment_scope='observed package snapshot, not final READY acceptance'))
    review = dict(schema_version=1, task='S01', round='REAL_DUAL_DDP_20261106',
                  reviewed_utc=datetime.now(timezone.utc).isoformat(), decision='FAIL',
                  review_complete=True, execution_authorized=False, immutable_after_publish=True,
                  reasons=[dict(code='B01_LOCAL_STRICT_NUMERICAL_FAILURE',
                        message='Frozen necessary small B64/two-rank gradient control fails 3/13 original-threshold metrics; fail-stop, no waiver.',
                        evidence=training['strict_metrics']['evidence'],
                        failed_metrics=training['strict_metrics']['failed'])],
                  bindings=deployment['bindings'], resources=deployment['resources'], workload=deployment['workload'],
                  deployment_acceptance='NOT_GRANTED_SNAPSHOT_ONLY_FINAL_READY_NOT_REVIEWED',
                  actual_cluster_result='NOT_RUN_NO_RELEASE',
                  report=asset(OWN / 'REPORT.md'), frozen_inputs=asset(OWN / 'FROZEN_INPUTS.json'),
                  local_checks=training['local_tests'],
                  boundaries=dict(S01_jobs_submitted=0, S01_full_model_updates=0, SSH=0,
                    actual_S00_queue='NOT_INDEPENDENTLY_QUERIED', C2_numerics='NOT_RUN',
                    split='UNKNOWN', subject_mapping='UNKNOWN', speedup='NOT_MEASURED'),
                  next_step='Stop current candidate release. Coordination must define any further diagnosis/new revision; this review authorizes no job or retry.')
    write_new('S01_REVIEW.json', review)
    progress = json.loads((OWN / 'REVIEW_PROGRESS.json').read_text(encoding='utf-8'))
    progress.update(decision='FAIL', review_complete=True, execution_authorized=False,
                    stopped_due_to='B01_LOCAL_STRICT_NUMERICAL_FAILURE',
                    dependency_wait='ENDED_EARLY_ON_CONCRETE_FAILURE_NOT_TIMEOUT',
                    review=asset(OWN / 'S01_REVIEW.json'), waiting_for=[])
    (OWN / 'REVIEW_PROGRESS.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(review=asset(OWN / 'S01_REVIEW.json'), report=asset(OWN / 'REPORT.md'),
                          frozen_input_files=len(inputs), decision='FAIL'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
