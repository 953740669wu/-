"""Login-only final actual queue/attempt check after S01 numeric rejection."""
import datetime
import json
from pathlib import Path
import sys

root = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z')
sys.path.insert(0,str(root))
from prepare import verify_prepared, save, sha
from submit_once import deduplicate

verify_prepared(root)
# Only call the read-only de-duplication function, never submit(). It saves the
# exact current queue plus every active job detail and all series markers.
deduplicate(root)
record = dict(status='NO_SERIES_ATTEMPT_OR_ACTIVE_JOB_AFTER_S01_FAIL',
    observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    review_sha256='f933a3af02a9362b9bce854935cbb18eecebfb38dd761805da163b48ff110f74',
    review_decision='FAIL',new_jobs=0,retries=0,active_job=None,
    deployment_sources='UNCHANGED',deployment_package_sha256=sha(root/'S00_REAL_DUAL_DDP_DEPLOYMENT.zip'),
    live_deduplication=json.loads((root/'pre_submit_deduplication.json').read_text(encoding='utf-8')),
    note='No dsub invoked. Current candidate stopped; no C2 numerical/preflight/full-model update or checkpoint.')
save(root/'NO_SUBMISSION_FINAL_CHECK.json',record)
print(json.dumps(record,indent=2),flush=True)
