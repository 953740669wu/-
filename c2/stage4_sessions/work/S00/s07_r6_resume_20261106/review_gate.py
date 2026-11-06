"""Exact R6 code/deployment/task/budget and original-criteria approval gate."""
import json
from prepare import sha
DEPLOYMENT='S00_S07_R6_DIAGNOSTIC_DEPLOYMENT.zip'
RESOURCES=dict(allocated_cores=76,actual_physical_cores=72,reserved_cores=4,domains=2,actual_cores_per_domain=36,memory_MB=24576,memory_limit_MB=24576,exclusive=True,HBM=0,job_seconds=300,consumer_seconds=270,cleanup_seconds=15,closing_seconds=15)
WORKLOAD=dict(max_jobs=1,case_order=['normal','crash','collective-timeout','watchdog'],linux_checks=71,skipped_checks=0,pg_timeout_seconds=5,case_deadline_seconds=30,python_dump_before_deadline_seconds=5,proc_shared_window_seconds=2,repeat=False,exit=False,retry=False,communication_criterion='original candidate/run_checks.py check_case unchanged; watchdog requires both injected_hang')
BINDING_KEYS=('inner_package_sha256','inner_manifest_sha256','observer_sha256','comm_probe_sha256','observation_contract_sha256','deployment_package_sha256','deployment_source_manifest_sha256','task_card_sha256')
def expected(root):
    manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'));delivery={i['path']:i['sha256'] for i in manifest['delivery_files']}
    return dict(inner_package_sha256=sha(root/'S07_ALIGNED_STACK_R6.zip'),inner_manifest_sha256=sha(root/'SOURCE_MANIFEST.json'),observer_sha256=delivery['candidate/stack_observer.py'],comm_probe_sha256=delivery['candidate/comm_probe.py'],observation_contract_sha256=sha(root/'OBSERVATION_CONTRACT.md'),deployment_package_sha256=sha(root/DEPLOYMENT),deployment_source_manifest_sha256=sha(root/'ARTIFACT_SHA256.json'),task_card_sha256=sha(root/'TASK_CARD.md'))
def validate(review,bindings):
    if review.get('decision')!='PASS_FOR_S07_R6_DIAGNOSTIC' or review.get('review_complete') is not True:raise ValueError('explicit complete R6 diagnostic review required')
    if any(review.get('bindings',{}).get(k)!=bindings[k] for k in BINDING_KEYS):raise ValueError('R6 exact SHA bindings mismatch')
    if any(review.get('resources',{}).get(k)!=v for k,v in RESOURCES.items()):raise ValueError('R6 total resource/budget mismatch')
    if any(review.get('workload',{}).get(k)!=v for k,v in WORKLOAD.items()):raise ValueError('R6 original cases/criteria/observation/workload mismatch')
def check_review(root,expected_review_sha=None):
    path=root/'S01_REVIEW.json';digest=sha(path)
    if expected_review_sha is not None and digest!=expected_review_sha:raise ValueError('review itself changed')
    validate(json.loads(path.read_text(encoding='utf-8')),expected(root));return digest
