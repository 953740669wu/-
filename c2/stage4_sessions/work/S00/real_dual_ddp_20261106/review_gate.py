"""Only a complete current S01 review for this frozen workload releases one job."""
import json
from prepare import sha, pinned, RESOURCES, WORKLOAD, DEPLOYMENT


def expected(root):
    pins = pinned(root)
    return dict(pins['bindings'], deployment_package_sha256=sha(root/DEPLOYMENT),
                deployment_source_manifest_sha256=sha(root/'ARTIFACT_SHA256.json'),
                descriptor_sha256=sha(root/'ENGINEERING_DESCRIPTOR.json'), task_card_sha256=sha(root/'TASK_CARD.md'))


def validate(review, bindings):
    if review.get('decision') != 'PASS_FOR_REAL_DUAL_DDP' or review.get('review_complete') is not True:
        raise ValueError('complete PASS_FOR_REAL_DUAL_DDP required; old probe review cannot release training')
    for section, wanted in [('bindings', bindings), ('resources', RESOURCES), ('workload', WORKLOAD)]:
        if any(review.get(section, {}).get(key) != value for key, value in wanted.items()):
            raise ValueError('S01 exact '+section+' binding mismatch')


def check_review(root, expected_review_sha=None):
    path = root/'S01_REVIEW.json'
    digest = sha(path)
    if expected_review_sha is not None and digest != expected_review_sha:
        raise ValueError('S01 review itself changed')
    validate(json.loads(path.read_text(encoding='utf-8')), expected(root))
    return digest
