"""Read-only current source/ready validation, then copy exact passing S01 review."""
import json
from pathlib import Path
import shutil
from prepare import sha
from review_gate import validate,expected
root=Path(__file__).resolve().parent
for name,digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():assert sha(root/name)==digest,name
ready=json.loads((root/'S00_DEPLOYMENT_READY.json').read_text(encoding='utf-8'))
for name,asset in ready.items():
    if isinstance(asset,dict) and {'path','bytes','sha256'}<=asset.keys():
        path=Path(asset['path']);assert path.stat().st_size==asset['bytes'] and sha(path)==asset['sha256'],name
assert sha(root.parents[1]/'S02/round12_dw_output_tiles_20261106/R12_READY.json')==sha(root/'S02_R12_READY.json')
assert sha(root.parents[1]/'COORDINATION/R12_DW_AB_EXECUTION_NEXT_20261106.md')==sha(root/'TASK_CARD.md')
review=root.parents[1]/'S01/round12_dw_ab_review_20261106/S01_REVIEW.json';value=json.loads(review.read_text(encoding='utf-8'))
validate(value,expected(root));assert value.get('remote_staging_root')==ready['remote_staging_root']
if not (root/'S01_REVIEW.json').exists():shutil.copyfile(review,root/'S01_REVIEW.json')
assert sha(root/'S01_REVIEW.json')==sha(review)
print(json.dumps(dict(status='EXACT_R12_SHA_WORKLOAD_RESOURCE_RELEASE_PASS',review_sha256=sha(review),bindings=expected(root))))
