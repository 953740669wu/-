"""Publish concrete SHA-bound S00 handoff after successful login checks."""
import json
from datetime import datetime,timezone
from pathlib import Path
from prepare import sha,save,RESOURCES
from review_gate import expected
root=Path(__file__).resolve().parent
def asset(name):
    p=root/name
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
assert 'R11_LOGIN_DEPLOYMENT_PASS' in (root/'evidence/LOGIN_DEPLOYMENT_CHECKS.txt').read_text()
checks=dict(status='LOCAL_AND_LINUX_LOGIN_DEPLOYMENT_PASS_NO_MODEL',local_fixture_tests=9,linux_login_fixture_tests=9,
    LF=True,python39_AST=True,Linux_bash_n=True,code_ZIP_manifest=True,metadata_hash_gate='ENGINEERING_METADATA_HASH_GATE_PASS',
    original_fixed16_files_sha=asset('evidence/FIXED_INPUT_IDENTITIES.json'),actual_KML='NOT_RUN',fault_signal_cleanup='NOT_RUN')
save(root/'evidence/DEPLOYMENT_CHECKS.json',checks)
ready=dict(status='S00_DEPLOYMENT_READY',protocol='ENGINEERING_REAL_CORPUS_GEMM5_V1',published_utc=datetime.now(timezone.utc).isoformat(),
 immutable_after_publish=True,engineering_only=True,new_jobs=0,max_retry_count=0,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',
 validation_status='NOT_RUN_NO_FORMAL_SPLIT',resources=RESOURCES,node_count=1,numa_domains=1,hbm=False,
 remote_staging_root=json.loads((root/'PINNED_INPUTS.json').read_text())['remote_staging_root'],
 required_review=dict(path=str(root.parents[1]/'S01/round11_gemm_review_20261106/S01_REVIEW.json'),decision='PASS_FOR_ENGINEERING_GEMM5',review_complete=True,bindings_object_required=True,resources_object_required=True),
 required_review_bindings=expected(root),entrypoint='run_gemm5.sh',entry_environment=['S02_ENGINEERING_DESCRIPTOR','S02_ENGINEERING_DESCRIPTOR_SHA256'],
 success='GEMM5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE',failure_states_preserved=['GEMM_OBSERVATION_ERROR','GEMM_LIMIT_EXCEEDED','UNSUPPORTED_GEMM_OBSERVATION','SOURCE_CHANGED','DATA_NOT_READY','ERROR_RUNTIME_OR_STATE','INCOMPLETE'],
 workload=dict(normalization_frames=1600,actual_train_frames=320,continuous_updates=5,warmup_steps=[1,2],sampled_steps=[3,4,5],new_sample_selection=False,old_checkpoint_loaded=False),
 limits=dict(max_detail_files=3,detail_bytes_each=1048576,max_records_per_sample=256,expected_records_per_sample=149,full_torch_profiler=False,over_limit='FAIL_STOP_NO_RETRY_NO_TRUNCATION'),
 timing_scope='ctypes wall includes Python conversion and native packing/scheduling/compute; outer difference includes preparation/counters/allocation/observer; not pure kernel or A/B speedup',
 R10_disposition='CLOSED_NOT_SELECTED_LOW_BENEFIT_NO_AB',submit_marker='new exclusive submit_once.marker in new root',old_outputs_and_formal_gates='READ_ONLY_UNCHANGED',
 collection=dict(all_gemm_files=True,raw_failures_preserved=True,checkpoint='REMOTE_ONLY_PATH_BYTES_SHA_RESTORE',command='/usr/bin/python3 -B collect_evidence.py <fixed RUN>'))
for key,name in [('deployment_package','S00_R11_GEMM5_DEPLOYMENT.zip'),('deployment_source_manifest','ARTIFACT_SHA256.json'),('source_manifest','ARTIFACT_SHA256.json'),
 ('code_source_manifest','S02_SOURCE_SHA256.json'),('gemm_ready','S02_GEMM_READY.json'),('interface','INTERFACE.json'),('gemm_contract','GEMM_CONTRACT.json'),
 ('reference_first5','REFERENCE_FIRST5.json'),('descriptor','ENGINEERING_DESCRIPTOR.json'),('commands','COMMANDS.md'),('checks','evidence/DEPLOYMENT_CHECKS.json'),
 ('linux_login_log','evidence/LOGIN_DEPLOYMENT_CHECKS.txt'),('initial_remote_check','evidence/INITIAL_REMOTE_READONLY.txt')]:ready[key]=asset(name)
save(root/'S00_DEPLOYMENT_READY.json',ready)
print(json.dumps(ready['required_review_bindings']))
