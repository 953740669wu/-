"""Publish frozen S07 R7 deployment for concrete S01 review; no job submit."""
from datetime import datetime,timezone
import json
from pathlib import Path
from prepare import sha,save
from review_gate import expected,RESOURCES,WORKLOAD
root=Path(__file__).resolve().parent
def asset(name):
    p=root/name
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
log=(root/'evidence/LOGIN_DEPLOYMENT_CHECKS.txt').read_text(encoding='utf-8')
assert 'S07_R7_LOGIN_DEPLOYMENT_PASS' in log and 'Ran 15 tests' in log
save(root/'evidence/DEPLOYMENT_CHECKS.json',dict(status='LOCAL_AND_LINUX_LOGIN_WRAPPER_CHECKS_PASS',local_fixture_tests=15,linux_login_fixture_tests=15,inner_files=16,inner_delivery=15,inner_entries=17,ZIP_CRC=True,source_SHA=True,LF=True,Python39_AST=True,Linux_bash_n=True,actual_Torch_Gloo='NOT_RUN',candidate_checks88='MUST_RUN_WITH_ZERO_SKIPS_IN_THIS_JOB',signal_fault_cleanup='NOT_RUN_THIS_ROUND'))
ready=dict(status='S00_DEPLOYMENT_READY',protocol='S07_R7_ATOMIC_REPORT_DIAGNOSTIC_V1',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
 new_jobs=0,max_retry_count=0,resources=RESOURCES,workload=WORKLOAD,required_review_workload=WORKLOAD,
 remote_staging_root=json.loads((root/'WORK_STARTED.json').read_text(encoding='utf-8'))['remote_staging_root'],
 required_review=dict(path=str(root.parents[1]/'S01/s07_r7_atomic_review_20261106/S01_REVIEW.json'),decision='PASS_FOR_S07_R7_ATOMIC',review_complete=True,bindings_object_required=True,resources_object_required=True,workload_object_required=True),
 required_review_bindings=expected(root),inner_package_name='S07_ATOMIC_REPORTS_R7.zip',inner_actual_files=16,inner_delivery_files=15,inner_zip_members=17,
 candidate_check_groups=[dict(label=label,count=count,max_seconds=limit) for label,count,limit in [('atomic_reports',17,30),('stack_observer',27,30),('readiness',16,30),('diagnostics',6,30),('job_identity',6,45),('probe',16,45)]],
 deadlines='Single START before consumer imports: all authorization/88 checks/environment/four cases/observation share START+270. Each cleanup and final cleanup capped START+285, original wrapper TERM2/KILL10<=15, closing15 within scheduler300. Frozen worker TERM/helper stop order and original grace unchanged; no per-helper/stage budget reset.',
 authorization='This task card and current user; original frozen cluster_job_submitted/old authorization fields retained unchanged',
 native_identity='Original scheduler_handoff byte-identical: actual CCS_JOB_ID/host/affinity -> nonce/request -> login djob raw/ready fresh30s; no generated fake PID/job or candidate S07_PROC_TASK/deadline environment',
 ownership='PR_SET_CHILD_SUBREAPER and sampled PID/start_ticks descendants across independent sessions; identity recheck before signalling; bounded cleanup, residuals recorded',
 acceptance='Original frozen run_checks.py: all four cases once in order; watchdog requires injected_hang on both workers. Communication, event/readiness and Python/proc completeness reported independently.',
 collection='All raw files/empty/truncated/permission/MISSED/temporary/store retained; snapshot bytes/SHA/remote mtime and changed_during_read; parent helper PID/kill/reap/returncode plus two rank stacks/source/proc receipts',
 login_scope='No real Torch import, Gloo or model; preparation fixtures only. Linux88 and actual communication/observer pending the one approved job.',
 real_HBM=False,formal_training=False,R12='CLOSED_NO_TRAINING_GAIN_KEEP_ORIGINAL_BASELINE_NO_MORE_TILES_OR_AB')
for key,name in [('inner_package','S07_ATOMIC_REPORTS_R7.zip'),('inner_manifest','SOURCE_MANIFEST.json'),('atomic_ready','S07_ATOMIC_READY.json'),('interface_ready','S07_INTERFACE_READY.json'),('observation_contract','OBSERVATION_CONTRACT.md'),('deployment_package','S00_S07_R7_ATOMIC_DEPLOYMENT.zip'),('deployment_source_manifest','ARTIFACT_SHA256.json'),('task_card','TASK_CARD.md'),('commands','COMMANDS.md'),('checks','evidence/DEPLOYMENT_CHECKS.json'),('local_fixture_log','evidence/tests_after.txt'),('linux_login_log','evidence/LOGIN_DEPLOYMENT_CHECKS.txt'),('initial_remote_check','evidence/INITIAL_REMOTE_READONLY.txt'),('pre_deploy_check','evidence/PRE_DEPLOY_CHECK.txt')]:ready[key]=asset(name)
ready['rank_report_residues']='Record .rank[01].json.*.tmp as raw metadata; formal reports only, no temp-to-formal fallback. Distinct from participants/ready publication residues.'
ready['official_report_scope']='Last atomically committed checkpoint, possibly broadcast without final error fields; original reader remains strict.'
save(root/'S00_DEPLOYMENT_READY.json',ready);print(json.dumps(ready['required_review_bindings']))
