"""Exact frozen S00/S07 inputs and S01 concrete release; no cluster actions."""
import json
from pathlib import Path
import shutil
from prepare import sha,INNER_SHA
from review_gate import expected,validate
root=Path(__file__).resolve().parent;ready=json.loads((root/'S00_DEPLOYMENT_READY.json').read_text(encoding='utf-8'))
for name,digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():assert sha(root/name)==digest,name
for name,asset in ready.items():
    if isinstance(asset,dict) and {'path','bytes','sha256'}<=asset.keys():
        p=Path(asset['path']);assert p.stat().st_size==asset['bytes'] and sha(p)==asset['sha256'],name
source=root.parents[1]/'S07/round7_atomic_reports_20261106'
assert sha(source/'package/S07_ATOMIC_REPORTS_R7.zip')==INNER_SHA and sha(source/'SOURCE_MANIFEST.json')==sha(root/'SOURCE_MANIFEST.json')
assert sha(root.parents[1]/'COORDINATION/S07_R7_ATOMIC_REPORT_NEXT_20261106.md')==sha(root/'TASK_CARD.md')
review=root.parents[1]/'S01/s07_r7_atomic_review_20261106/S01_REVIEW.json';value=json.loads(review.read_text(encoding='utf-8'));validate(value,expected(root))
if not (root/'S01_REVIEW.json').exists():shutil.copyfile(review,root/'S01_REVIEW.json')
assert sha(root/'S01_REVIEW.json')==sha(review)
print(json.dumps(dict(status='EXACT_S07_R7_RELEASE_PASS',review_sha256=sha(review),bindings=expected(root))))
