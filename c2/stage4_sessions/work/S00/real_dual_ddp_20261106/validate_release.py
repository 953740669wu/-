"""Local release recheck: frozen origins, outer index, READY, optional exact review."""
import argparse
import json
from pathlib import Path
from prepare import sha, pinned, RESOURCES, WORKLOAD
from review_gate import expected, check_review


def check(root, require_review=False):
    pins = pinned(root)
    for name, digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():
        if sha(root/name) != digest: raise ValueError('local source drift: '+name)
    for item in pins['upstream_files']:
        path = Path(item['path'])
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('published upstream changed: '+str(path))
    ready = json.loads((root/'S00_DEPLOYMENT_READY.json').read_text(encoding='utf-8'))
    bindings = expected(root)
    if ready['required_review_bindings'] != bindings or ready['resources'] != RESOURCES or ready['workload'] != WORKLOAD:
        raise ValueError('READY differs from actual deployment identities/budget')
    result = dict(status='FROZEN_LOCAL_RELEASE_VERIFIED_NO_SUBMISSION', bindings=bindings,
                  deployment_ready_sha256=sha(root/'S00_DEPLOYMENT_READY.json'))
    if require_review: result['review_sha256'] = check_review(root)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(Path(__file__).resolve().parent, args.review), indent=2))
