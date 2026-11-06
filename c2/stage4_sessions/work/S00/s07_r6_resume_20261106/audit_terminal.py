"""Read-only terminal/failure audit; no Torch/Gloo or new communication run."""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from prepare import sha,save
from review_gate import check_review
root=Path(__file__).resolve().parent;received=root/'evidence/received';job=(root/'job_id.txt').read_text().strip()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def require(ok,message):
    if not ok:raise ValueError(message)
receipt=load(root/'evidence/bundle_receipt.json');archive=root/('evidence/JOB_'+job+'_full_evidence.zip')
require(archive.stat().st_size==receipt['bytes'] and sha(archive)==receipt['sha256'],'archive bytes/SHA mismatch')
index=load(received/'COLLECTION_S00.json')
for name,meta in index['files'].items():
    p=received/name;require(p.stat().st_size==meta['bytes'] and sha(p)==meta['sha256'],'raw snapshot bytes changed: '+name)
require(not index['changed_source_files'] and not any(m['changed_during_read'] for m in index['files'].values()),'source or terminal read instability')
for name,digest in load(root/'ARTIFACT_SHA256.json').items():require(sha(root/name)==digest and sha(received/name)==digest,'frozen deployment changed: '+name)
for name,meta in load(root/'evidence/PROTECTED_BEFORE.json').items():require(Path(name).stat().st_size==meta['bytes'] and sha(Path(name))==meta['sha256'],'protected old original changed')
check_review(root)
final=load(received/'djob_final.json')['data']['successData'][0];summary=load(received/'job_evidence/SUMMARY.json');clean=load(received/'job_evidence/cleanup.json')
require(str(final['jobId'])==job and final['state']=='FAILED' and final['jobExitCode']==summary['exit_code']==1,'exact failed terminal missing')
group=final['resGroups'][0]
require(final['exclusive'] and final['jobWallClockLimit']==300 and final['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'scheduler resource/retry drift')
require(group['resReq']['cpu']==group['resAlloc']['cpu']==76 and group['resReq']['mem']==group['resLimit']['mem']==group['resAlloc']['mem']==24576,'total resource budget differs')
require(index['scheduler_pids_cleared'] and clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'residual job processes')
request=load(received/'scheduler_request.json');ready=load(received/'scheduler_ready.json')
require(request['context']['job_id']==ready['job_id']==job and request['context']['host']==final['taskExecNodes'],'native identity mismatch')
require(ready['nonce']==request['nonce'] and ready['raw_sha256']==sha(received/'scheduler_allocation.json') and ready['request_sha256']==sha(received/'scheduler_request.json'),'native nonce/raw/request binding mismatch')
require(0<=ready['generated_at']-request['created_at']<=30,'original handoff freshness exceeded')
require(summary['standard_library_tests']==dict(passed=71,skipped=0),'71 Linux/no-skip checks missing')
for label,count in [('stack_observer_tests',27),('readiness_tests',16),('diagnostic_tests',6),('job_identity_tests',6),('probe_tests',16)]:
    record=load(received/'job_evidence'/(label+'.json'));log=(received/'job_evidence'/(label+'.log')).read_text(encoding='utf-8')
    require(record['returncode']==0 and ('Ran '+str(count)+' tests') in log and 'OK' in log and 'skipped=' not in log and '... skipped' not in log,'Linux test receipt mismatch')
allocation=load(received/'job_evidence/verified_allocation.json');ranks=allocation['ranks']
require(allocation['job_id']==job and len(ranks)==2 and all(len(r['allocated'])==38 and len(r['selected'])==36 and len(r['reserved'])==2 for r in ranks),'two36 allocation receipts missing')
require(len(set().union(*(set(r['selected']) for r in ranks)))==72 and len(set().union(*(set(r['allocated']) for r in ranks)))==76,'domain overlap/missing CPUs')
sys.path.insert(0,str(received/'payload/candidate'))
import cpu36_contract as contract
for rank in ranks:contract.validate_receipt(rank)
spec=importlib.util.spec_from_file_location('frozen_s07_case_reader',received/'payload/candidate/run_checks.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
checks=load(received/'payload/checks_current_job/checks.json')
require(checks['status']=='FAIL' and [r['case'] for r in checks['cases']]==['normal'] and checks['error']=='Expecting value: line 1 column 1 (char 0)','original fail-stop point differs')
reader.check_case('normal',checks['cases'][0]['probe_exit'],received/'payload/checks_current_job/normal')
delivery={p['path']:p['sha256'] for p in load(root/'SOURCE_MANIFEST.json')['delivery_files']};cases={};missing_cpu=[];snapshots=0
environment=load(received/'payload/environment_current.json');expected_libraries=environment['loaded_torch_libraries']
for case in ('normal','crash'):
    directory=received/'payload/checks_current_job'/case;manifest=load(directory/'manifest.json');supervisor=load(directory/'summary.json')['supervisor']
    require(manifest['job_id']==job and manifest['host']==final['taskExecNodes'] and manifest['pg_timeout']==5 and manifest['deadline']==30,'case native/timeout identity mismatch')
    require(manifest['source_sha256']=={Path(p).name:delivery[p] for p in ('candidate/comm_probe.py','candidate/cpu36_contract.py','candidate/stack_observer.py')},'actual case source identity mismatch')
    reports={}
    for rank in (0,1):
        p=directory/f'rank{rank}.json';meta=index['files'][p.relative_to(received).as_posix()]
        reports[str(rank)]=dict(bytes=meta['bytes'],sha256=meta['sha256'])
        if not meta['bytes']:
            missing_cpu.append(case+'/rank'+str(rank));continue
        row=load(p);require(row['pid']==supervisor['pids'][rank] and row['cpu_receipt']==ranks[rank] and row['torch_intraop']==36,'actual worker CPU/rank differs')
        require(row['runtime']['loaded_torch_libraries']==expected_libraries,'runtime libraries differ from same-job environment')
        for point in row['checkpoints']:contract.validate_snapshot(ranks[rank]['selected'],point['snapshot']);snapshots+=1
        reports[str(rank)].update(stage=row['stage'],status=row['status'],pid=row['pid'],torch_intraop=row['torch_intraop'],error=row.get('error'),cpu_snapshot_count=len(row['checkpoints']))
    cases[case]=dict(supervisor=supervisor,rank_reports=reports)
crash=received/'payload/checks_current_job/crash'
require((crash/'rank0.json').stat().st_size==0 and cases['crash']['supervisor']['exit_codes']==[-15,17] and cases['crash']['rank_reports']['1']['stage']=='injected_crash','specific crash evidence differs')
require(not (received/'payload/checks_current_job/collective-timeout').exists() and not (received/'payload/checks_current_job/watchdog').exists(),'later cases executed after failure')
begin,end=[datetime.fromisoformat(final[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
save(root/'RUN_AUDIT.json',dict(status='FAILED_SUITE_RAW_EVIDENCE_VERIFIED_NO_RETRY',job_id=job,host=final['taskExecNodes'],scheduler_state='FAILED',job_exit_code=1,
    new_jobs=1,retries=0,active_s00_job=None,communication_suite_passed=False,normal_fixed_tensor_passed=True,original_checks_error=checks['error'],failed_case='crash',
    observed_stop='crash rank0.json empty at original case result reader; rank1 reached injected_crash/exit17; parent reaped both',cases=cases,not_run=['collective-timeout','watchdog'],
    watchdog_observation_status='NOT_RUN',diagnostic_task_complete=False,available_trace_inventory=index['diagnostics'],available_readiness_inventory=index['readiness'],stack_inventory=index['stack_observation'],
    linux_tests_passed=71,linux_tests_skipped=0,allocated_cores=76,selected_cores=[r['selected'] for r in ranks],reserved_cores=[r['reserved'] for r in ranks],actual_torch_intraop_available_reports=36,
    validated_serialized_cpu_snapshots=snapshots,missing_serialized_cpu_reports=missing_cpu,actual_libraries_unchanged=expected_libraries,source_status='UNCHANGED',protected_local_old_originals_unchanged=True,
    scheduler_pids_cleared=True,all_owned_processes_reaped=True,owned_pid_count=len(clean['owned']),outer_cleanup_signal_actions=clean['actions'],
    node_seconds=(end-begin).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],archive=receipt,
    inference_boundary='Empty JSON and nearby worker_error/parent TERM are consistent with interrupted direct JSON rewrite; exact cause not proven here. No payload repair, regenerated report or extra watchdog run.',formal_training=False,performance_acceptance=False))
print(json.dumps(dict(status='FAILED_SUITE_HANDOFF_VERIFIED',job=job,node_seconds=(end-begin).total_seconds(),not_run=['collective-timeout','watchdog'],validated_cpu_snapshots=snapshots,missing_cpu_reports=missing_cpu)))
