"""Require S01's explicit complete decision and every concrete frozen identity."""
import json
from prepare import sha,pinned,RESOURCES,DEPLOYMENT

BINDING_KEYS=('code_package_sha256','code_source_manifest_sha256','deployment_package_sha256',
              'descriptor_sha256','interface_sha256','gemm_contract_sha256','reference_first5_sha256','deployment_source_manifest_sha256')


def expected(root):
    pins=pinned(root)
    return dict(code_package_sha256=pins['code_package_sha256'],code_source_manifest_sha256=pins['code_source_manifest_sha256'],
      deployment_package_sha256=sha(root/DEPLOYMENT),descriptor_sha256=sha(root/'ENGINEERING_DESCRIPTOR.json'),
      interface_sha256=sha(root/'INTERFACE.json'),gemm_contract_sha256=sha(root/'GEMM_CONTRACT.json'),
      reference_first5_sha256=sha(root/'REFERENCE_FIRST5.json'),deployment_source_manifest_sha256=sha(root/'ARTIFACT_SHA256.json'))


def validate(review,bindings):
    if review.get('decision')!='PASS_FOR_ENGINEERING_GEMM5' or review.get('review_complete') is not True:
        raise ValueError('S01 explicit complete PASS required; fail/blocked is not approval')
    if any(review.get('bindings',{}).get(k)!=bindings[k] for k in BINDING_KEYS):
        raise ValueError('S01 concrete SHA bindings mismatch')
    if any(review.get('resources',{}).get(k)!=v for k,v in RESOURCES.items()):
        raise ValueError('S01 resource/budget binding mismatch')


def check_review(root,expected_review_sha=None):
    path=root/'S01_REVIEW.json';digest=sha(path)
    if expected_review_sha is not None and digest!=expected_review_sha:raise ValueError('S01 review itself changed')
    validate(json.loads(path.read_text(encoding='utf-8')),expected(root))
    return digest
