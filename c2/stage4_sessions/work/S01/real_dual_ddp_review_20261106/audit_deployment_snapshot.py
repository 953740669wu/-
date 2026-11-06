"""Verify current S00 bytes without interpreting an unfinished deployment as READY."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile
from datetime import datetime, timezone

sys.dont_write_bytecode = True
OWN = Path(__file__).resolve().parent
ROOT = OWN.parent.parent / 'S00/real_dual_ddp_20261106'


def asset(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    files = json.loads((ROOT / 'ARTIFACT_SHA256.json').read_text(encoding='utf-8'))
    inputs = [asset(ROOT / 'ARTIFACT_SHA256.json')]
    for name, digest in files.items():
        value = asset(ROOT / name)
        assert value['sha256'] == digest, name
        inputs.append(value)
        if name.endswith('.py'):
            assert b'\r' not in (ROOT / name).read_bytes()
            ast.parse((ROOT / name).read_text(encoding='utf-8'), feature_version=(3, 9))
    archive = ROOT / 'S00_REAL_DUAL_DDP_DEPLOYMENT.zip'
    inputs.append(asset(archive))
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        assert len(names) == len(set(names)) and package.testzip() is None
        assert {n for n in names if not n.endswith('/')} == set(files) | {'ARTIFACT_SHA256.json'}
        for name in names:
            if not name.endswith('/'):
                assert package.read(name) == (ROOT / name).read_bytes(), name
    pins = json.loads((ROOT / 'PINNED_INPUTS.json').read_text(encoding='utf-8'))
    assert sum(item['methods'] for item in pins['linux_checks']) == 26
    sys.path.insert(0, str(ROOT))
    import review_gate
    bindings = review_gate.expected(ROOT)
    negative_checks = []
    for review in ({'decision': 'FAIL', 'review_complete': True},
                   {'decision': 'PASS_FOR_REAL_DUAL_DDP', 'review_complete': False},
                   {'decision': 'PASS_FOR_REAL_DUAL_DDP', 'review_complete': True, 'bindings': {}}):
        try:
            review_gate.validate(review, bindings)
        except ValueError as exc:
            negative_checks.append(str(exc))
        else:
            raise AssertionError('deployment accepted invalid review')
    receipt = json.loads((ROOT / 'evidence/LINUX_WRAPPER_PREPARATION_RECEIPT.json').read_text(encoding='utf-8'))
    mismatches = [name for name, digest in receipt['source_sha256'].items()
                  if asset(ROOT / name)['sha256'] != digest]
    ready_path = ROOT / 'S00_DEPLOYMENT_READY.json'
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  status='SNAPSHOT_IDENTITIES_VERIFIED_NOT_FINAL_READY',
                  deployment_ready_present=ready_path.exists(),
                  manifest_files=len(files), package_members=len(names),
                  bindings=bindings, resources=review_gate.RESOURCES, workload=review_gate.WORKLOAD,
                  linux_preflight_methods=26, invalid_reviews_rejected=negative_checks,
                  prior_login_receipt_drifted_files=mismatches,
                  final_Linux_package_checks='PENDING_FINAL_READY_NOT_ASSERTED',
                  inputs=inputs)
    (OWN / 'deployment_snapshot_review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'inputs'}, indent=2))


if __name__ == '__main__':
    main()
