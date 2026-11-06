"""Publish the frozen concrete R12 deployment after login-only checks."""
from datetime import datetime,timezone
import json
from pathlib import Path
from prepare import sha,save,RESOURCES
from review_gate import expected,WORKLOAD
root=Path(__file__).resolve().parent
def asset(name):
    p=root/name
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
log=(root/'evidence/LOGIN_DEPLOYMENT_CHECKS.txt').read_text(encoding='utf-8')
assert all(s in log for s in ['R12_LOGIN_DEPLOYMENT_PASS','ENGINEERING_METADATA_HASH_GATE_PASS','OLD_INPUT_IDENTITIES_PASS BEFORE 9','FIXED16_CURRENT_SOURCE_SHA_PASS','Ran 9 tests'])
save(root/'evidence/DEPLOYMENT_CHECKS.json',dict(status='LOCAL_AND_LINUX_LOGIN_PASS_NO_MATRIX_OR_MODEL',local_fixture_tests=9,linux_login_fixture_tests=9,
    LF=True,Python39_AST=True,Linux_bash_n=True,ZIP_CRC_and_source_manifest=True,fixed_source_files=36,fixed_units=16,old_artifact_SHA_receipts=9,
    metadata_hash_gate='ENGINEERING_METADATA_HASH_GATE_PASS',actual_KML='NOT_RUN',full_encoder='NOT_RUN',signal_fault_cleanup='NOT_RUN'))
ready=dict(status='S00_DEPLOYMENT_READY',protocol='ENGINEERING_DW_TILES_R12_AB_V1',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
 new_jobs=0,max_retry_count=0,engineering_only=True,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',
 resources=RESOURCES,workload=WORKLOAD,required_review_workload=WORKLOAD,node_count=1,numa_domains=1,hbm=False,
 remote_staging_root=json.loads((root/'PINNED_INPUTS.json').read_text(encoding='utf-8'))['remote_staging_root'],entrypoint='run_ab_proposal.sh',
 entry_environment=['S02_ENGINEERING_DESCRIPTOR','S02_ENGINEERING_DESCRIPTOR_SHA256'],success='R12_COMPLETE_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE',
 phase_success=dict(target='PASS_ACTUAL_KML_TARGET_ONLY',strict='PASS_STRICT_ENCODER5',perf_baseline='PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE',perf_candidate='PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE'),
 required_review=dict(path=str(root.parents[1]/'S01/round12_dw_ab_review_20261106/S01_REVIEW.json'),decision='PASS_FOR_ENGINEERING_R12_AB',review_complete=True,bindings_object_required=True,resources_object_required=True,workload_object_required=True),
 required_review_bindings=expected(root),authorization='User current round and frozen TASK_CARD.md; original R12_READY execution_authorized=false retained as history',
 assertions='Non-optimized Python: env-i excludes PYTHONOPTIMIZE; Python -B, never -O/-OO; frozen asserts unchanged',
 deadline='Absolute START+840 from wrapper import covers gate and whole frozen chain; unified cleanup<=30 ends<=START+870, reserve30 under scheduler900. Inner phase720 only fallback, no reset of outer deadline.',
 expected_counts_per_update=dict(baseline=dict(logical=149,native=149,target_full=12,target_tiles=0,dispatch=0),candidate=dict(logical=149,native=161,target_full=0,target_tiles=24,dispatch=12)),
 stop='Any failed/missing gate stops all later phases; budget insufficiency INCOMPLETE, never shorten25 or retry/fallback/change tile or precision.',
 collection=dict(all_phase_outputs=True,partial_and_raw_failures_preserved=True,checkpoint='REMOTE_ONLY_PATH_BYTES_SHA_ZERO_UPDATE_RESTORE',exposure='separate strict/perf ledgers; preserve in_flight/unknown conservatively'),
 old_outputs_and_formal_gates='READ_ONLY_UNCHANGED',submit_marker='new exclusive submit_once.marker in new root')
for key,name in [('deployment_package','S00_R12_DW_AB_DEPLOYMENT.zip'),('deployment_source_manifest','ARTIFACT_SHA256.json'),('source_manifest','ARTIFACT_SHA256.json'),
 ('code_source_manifest','S02_SOURCE_SHA256.json'),('r12_ready','S02_R12_READY.json'),('r12_contract','R12_CONTRACT.json'),('reference_first5','REFERENCE_FIRST5.json'),
 ('reference_epoch25','REFERENCE_EPOCH25.json'),('descriptor','ENGINEERING_DESCRIPTOR.json'),('task_card','TASK_CARD.md'),('commands','COMMANDS.md'),
 ('checks','evidence/DEPLOYMENT_CHECKS.json'),('local_fixture_log','evidence/tests_after.txt'),('linux_login_log','evidence/LOGIN_DEPLOYMENT_CHECKS.txt'),('initial_remote_check','evidence/INITIAL_REMOTE_READONLY.txt')]:ready[key]=asset(name)
save(root/'S00_DEPLOYMENT_READY.json',ready)
print(json.dumps(ready['required_review_bindings']))
