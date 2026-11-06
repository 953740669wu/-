"""Read-only local release validation; copy review only after exact approval."""
import json
from pathlib import Path
import shutil
from prepare import sha,RESOURCES
from review_gate import validate,expected
root=Path(__file__).resolve().parent
ready=json.loads((root/'S00_DEPLOYMENT_READY.json').read_text())
for name,digest in json.loads((root/'ARTIFACT_SHA256.json').read_text()).items():
    assert sha(root/name)==digest,name
for key,asset in ready.items():
    if isinstance(asset,dict) and {'path','bytes','sha256'}<=asset.keys():
        p=Path(asset['path']);assert p.stat().st_size==asset['bytes'] and sha(p)==asset['sha256'],key
original=root.parents[1]/'S02/round11_gemm_breakdown_20261106/GEMM_READY.json'
assert sha(original)==sha(root/'S02_GEMM_READY.json')
review=root.parents[1]/'S01/round11_gemm_review_20261106/S01_REVIEW.json'
value=json.loads(review.read_text());validate(value,expected(root))
assert value.get('protocol')==ready['protocol']
if not (root/'S01_REVIEW.json').exists():shutil.copyfile(review,root/'S01_REVIEW.json')
assert sha(root/'S01_REVIEW.json')==sha(review)
print(json.dumps(dict(status='EXACT_SHA_REVIEW_RELEASE_PASS',review_sha256=sha(review),bindings=expected(root),resources=RESOURCES)))
