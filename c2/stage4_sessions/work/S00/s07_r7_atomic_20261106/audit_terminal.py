"""Audit this one complete protocol and its separate observation limits."""
from datetime import datetime
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
receipt=load(root/'evidence/bundle_receipt.json');archive=root/('evidence/JOB_'+job+'_full_evidence.zip');index=load(received/'COLLECTION_S00.json')
require(archive.stat().st_size==receipt['bytes'] and sha(archive)==receipt['sha256'],'archive drift')
for name,meta in index['files'].items():require((received/name).stat().st_size==meta['bytes'] and sha(received/name)==meta['sha256'] and not meta['changed_during_read'],'snapshot drift/unstable read: '+name)
require(not index['changed_source_files'],'source changed')
for name,digest in load(root/'ARTIFACT_SHA256.json').items():require(sha(root/name)==sha(received/name)==digest,'frozen source drift: '+name)
for name,meta in load(root/'evidence/PROTECTED_BEFORE.json').items():require(Path(name).stat().st_size==meta['bytes'] and sha(Path(name))==meta['sha256'],'protected prior evidence changed')
check_review(root)
final=load(received/'djob_final.json')['data']['successData'][0];summary=load(received/'job_evidence/SUMMARY.json');clean=load(received/'job_evidence/cleanup.json');group=final['resGroups'][0]
require(str(final['jobId'])==job and final['state']=='SUCCEEDED' and final['jobExitCode']==summary['exit_code']==0 and summary['communication_passed'],'terminal/protocol success missing')
require(final['exclusive'] and final['jobWallClockLimit']==300 and final['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'budget/retry drift')
require(group['resReq']['cpu']==group['resAlloc']['cpu']==76 and group['resReq']['mem']==group['resLimit']['mem']==group['resAlloc']['mem']==24576,'total resources drift')
require(index['scheduler_pids_cleared'] and clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'cleanup incomplete')
request=load(received/'scheduler_request.json');ready=load(received/'scheduler_ready.json')
require(request['context']['job_id']==ready['job_id']==job and request['context']['host']==final['taskExecNodes'] and ready['nonce']==request['nonce'],'native context/nonce mismatch')
require(ready['raw_sha256']==sha(received/'scheduler_allocation.json') and ready['request_sha256']==sha(received/'scheduler_request.json') and 0<=ready['generated_at']-request['created_at']<=30,'raw/request/freshness mismatch')
require(summary['standard_library_tests']==dict(passed=88,skipped=0),'88 Linux/no-skip evidence missing')
for label,count in [('atomic_report_tests',17),('stack_observer_tests',27),('readiness_tests',16),('diagnostic_tests',6),('job_identity_tests',6),('probe_tests',16)]:
    record=load(received/'job_evidence'/(label+'.json'));log=(received/'job_evidence'/(label+'.log')).read_text(encoding='utf-8')
    require(record['returncode']==0 and ('Ran '+str(count)+' tests') in log and 'OK' in log and 'skipped=' not in log and '... skipped' not in log,'test count/skip mismatch')
allocation=load(received/'job_evidence/verified_allocation.json');ranks=allocation['ranks']
require(allocation['job_id']==job and len(ranks)==2 and all(len(r['allocated'])==38 and len(r['selected'])==36 and len(r['reserved'])==2 for r in ranks),'two36 receipts invalid')
require(len(set().union(*(set(r['selected']) for r in ranks)))==72 and len(set().union(*(set(r['allocated']) for r in ranks)))==76,'overlapping CPU domains')
sys.path.insert(0,str(received/'payload/candidate'));import cpu36_contract as contract
for rank in ranks:contract.validate_receipt(rank)
spec=importlib.util.spec_from_file_location('frozen_r7_case_reader',received/'payload/candidate/run_checks.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
checks=load(received/'payload/checks_current_job/checks.json');order=['normal','crash','collective-timeout','watchdog']
require(checks['status']=='PASS_PROBE_CHECKS_ONLY' and [c['case'] for c in checks['cases']]==order and [c['probe_exit'] for c in checks['cases']]==[0,1,1,124],'original four-case sequence failed')
environment=load(received/'payload/environment_current.json');libraries=environment['loaded_torch_libraries'];delivery={x['path']:x['sha256'] for x in load(root/'SOURCE_MANIFEST.json')['delivery_files']}
require(delivery['candidate/run_checks.py']=='7b7cc96edd9401981a61db5122bf785e3e2348a41cda5363ba5d2ea4b0217d07' and delivery['candidate/stack_observer.py']=='5b3ad54e675a293e3eb51d292b149c6939bbdc52b68322f340eb76be3b02b875','original reader/observer changed')
reports_inventory=load(received/'RANK_REPORT_INVENTORY.json');cases={};snapshots=0;max_tids=0
for accepted in checks['cases']:
    case=accepted['case'];directory=received/'payload/checks_current_job'/case
    reader.check_case(case,accepted['probe_exit'],directory)
    manifest=load(directory/'manifest.json');state=load(directory/'summary.json')['supervisor']
    require(manifest['job_id']==job and manifest['host']==final['taskExecNodes'] and manifest['pg_timeout']==5 and manifest['deadline']==30,'case identity/timeout mismatch')
    require(manifest['source_sha256']=={Path(p).name:delivery[p] for p in ('candidate/comm_probe.py','candidate/cpu36_contract.py','candidate/stack_observer.py')},'case import/source mismatch')
    require(state['all_reaped'] and len(state['pids'])==2,'case cleanup missing');rows={}
    for rank in (0,1):
        p=directory/f'rank{rank}.json';row=load(p);require(p.stat().st_size>0 and row['rank']==rank and row['pid']==state['pids'][rank] and row['run_id']==manifest['run_id'] and row['cpu_receipt']==ranks[rank] and row['torch_intraop']==36,'formal rank/CPU record invalid')
        require(row['runtime']['loaded_torch_libraries']==libraries,'same-job library identity mismatch')
        for point in row['checkpoints']:
            contract.validate_snapshot(ranks[rank]['selected'],point['snapshot']);snapshots+=1;max_tids=max(max_tids,len(point['snapshot']['threads']))
        inventory=reports_inventory['cases'][case]['reports'][str(rank)];require(inventory['formal_report_valid'] and inventory['stage']==row['stage'],'rank inventory mismatch')
        rows[str(rank)]=dict(pid=row['pid'],bytes=p.stat().st_size,sha256=sha(p),stage=row['stage'],status=row['status'],error=row.get('error'),torch_intraop=row['torch_intraop'],torch_interop=row['torch_interop'],checkpoint_count=len(row['checkpoints']),last_checkpoint_end=inventory['last_checkpoint_end_event'])
    cases[case]=dict(accepted_by_original_reader=True,probe_exit=accepted['probe_exit'],supervisor=state,reports=rows,atomic_residuals=reports_inventory['cases'][case]['residuals'])
require(not reports_inventory['not_run'],'case not run')
require(cases['normal']['reports']['0']['status']==cases['normal']['reports']['1']['status']=='PASS','normal did not pass')
require(cases['crash']['reports']['0']['stage']=='broadcast' and cases['crash']['reports']['1']['stage']=='injected_crash','crash stage differs')
watch=received/'payload/checks_current_job/watchdog';context=load(watch/'participants.json');target=context['deadline_ns']-5_000_000_000;stack_states=[]
def guard_cpu_evidence(value,selected):
    require(value['calling_affinity'] and set(value['calling_affinity'])<=set(selected),'observer caller CPU mismatch');contract.validate_snapshot(selected,value['snapshot'])
for rank in (0,1):
    value=load(watch/f'rank{rank}.stack_status.json');require(value['rank']==rank and value['pid']==cases['watchdog']['reports'][str(rank)]['pid'] and value['job_id']==job and value['target_ns']==target,'stack identity/target mismatch')
    require(value['status']=='CANCELLED_OR_DUMP_FINISHED' and value['cancel_reason']=='init_end' and value['armed_at_ns']<value['cancelled_at_ns']<target and (watch/f'rank{rank}.python_stack.txt').stat().st_size==0,'expected legal init-end cancellation differs')
    for name in ('before_timer_cpu','after_timer_cpu'):guard_cpu_evidence(value[name],ranks[rank]['selected'])
    sources=load(watch/f'rank{rank}.installed_python.json');require(sources['status']=='RECORDED' and len(sources['files'])==2 and all(s.get('sha256') and s.get('path') and 0<s['bytes']<=1048576 for s in sources['files']),'installed Python identities missing')
    stack_states.append(dict(rank=rank,status=value['status'],target_ns=target,armed_at_ns=value['armed_at_ns'],cancelled_at_ns=value['cancelled_at_ns'],cancel_reason=value['cancel_reason'],seconds_before_target=(target-value['cancelled_at_ns'])/1e9,python_stack_bytes=0,installed_python=sources))
proc=load(watch/'proc_summary.json');identity=load(watch/'proc_identity.json');helper=cases['watchdog']['supervisor']['stack_observation']
parent_events=[json.loads(line) for line in (watch/'supervisor.events.jsonl').read_bytes().splitlines()];parent_pid=parent_events[0]['pid']
require(helper['reaped'] and helper['status']=='EXITED' and helper['returncode']==0 and helper['helper_pid']==proc['helper_pid'] and str(helper['helper_pid']) in clean['owned'],'helper ownership/return/reap mismatch')
require(identity['identity']=={k:context[k] for k in ('run_id','job_id','ready_token')} and identity['captured_ns']<target,'proc identity/context mismatch')
require(proc['status']=='RECORDED_AVAILABLE_FIELDS_ONLY' and proc['target_ns']==helper['target_ns']==target and proc['sample_stop_ns']==helper['sample_stop_ns']==target+2_000_000_000 and target<=proc['sample_started_ns']<=proc['finished_ns']<=target+2_000_000_000,'proc shared window mismatch')
require(len(proc['ranks'])==len(identity['targets'])==2,'proc target ranks missing')
for record in proc['ranks']:
    rank=record['rank'];expected=identity['targets'][rank]
    require(record['status']=='RECORDED' and expected['pid']==cases['watchdog']['reports'][str(rank)]['pid'] and expected['ppid']==parent_pid and expected['sid']==expected['pid'] and expected['start_ticks']>0 and record['target']['identity']==record['identity_after']['identity']==expected,'proc parent/session/start-tick recheck differs')
    for side in ('target','identity_after'):require(record[side]['affinity'] and set(record[side]['affinity'])<=set(ranks[rank]['selected']),'proc target CPU boundary differs')
    guard_cpu_evidence(record['helper_cpu'],ranks[rank]['selected'])
fields=[json.loads(line) for line in (watch/'proc_fields.jsonl').read_bytes().splitlines()]
require(len(fields)==8 and {(x['rank'],x['field']) for x in fields}=={(rank,name) for rank in (0,1) for name in ('wchan','syscall','stack','mountinfo')},'proc field set differs')
errors=[{k:x.get(k) for k in ('rank','pid','field','status','error')} for x in fields if x['status']!='OK']
require(len(errors)==2 and all(x['field']=='stack' and x['status']=='ERROR' and 'PermissionError' in x['error'] for x in errors),'proc limitation differs from observed permission failures')
require(index['diagnostics']['complete'] and not index['diagnostics']['not_run'] and index['readiness']['complete'] and not index['readiness']['not_run'],'event/readiness evidence incomplete')
require(not index['stack_observation']['complete'],'do not promote cancelled/permission-limited capture')
start,end=[datetime.fromisoformat(final[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
save(root/'RUN_AUDIT.json',dict(status='PASS_ORIGINAL_FOUR_CASE_PROTOCOL_OBSERVATION_LIMITS_RECORDED',job_id=job,host=final['taskExecNodes'],scheduler_state='SUCCEEDED',job_exit_code=0,new_jobs=1,retries=0,active_s00_job=None,
    linux_tests_passed=88,linux_tests_skipped=0,communication_suite_passed=True,cases=cases,not_run=[],formal_rank_reports=8,all_formal_reports_valid=True,atomic_residual_count=sum(len(c['atomic_residuals']) for c in cases.values()),
    worker_cpu_snapshots=snapshots,max_observed_worker_TIDs=max_tids,selected_cores=[r['selected'] for r in ranks],reserved_cores=[r['reserved'] for r in ranks],actual_libraries_unchanged=libraries,
    bounded_diagnostic_attempt_completed=True,python_stack_capture_status='LEGALLY_CANCELLED_ON_INIT_END_NO_CAPTURE',python_stack_capture_complete=False,python_stack_states=stack_states,
    proc_observation_status='PARTIAL_KERNEL_STACK_PERMISSION_DENIED',proc_fields_total=8,proc_fields_ok=6,proc_fields_errors=errors,proc_shared_sample_seconds=(proc['finished_ns']-proc['sample_started_ns'])/1e9,proc_helper=helper,
    full_stack_capture_complete=False,event_inventory=index['diagnostics'],readiness_inventory=index['readiness'],stack_inventory=index['stack_observation'],source_status='UNCHANGED',old_protected_evidence_unchanged=True,
    scheduler_pids_cleared=True,all_owned_processes_reaped=True,owned_pid_count=len(clean['owned']),outer_cleanup_signal_actions=clean['actions'],node_seconds=(end-start).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],archive=receipt,
    limits='One bounded four-case tensor probe, not synchronized model training, performance acceptance or proof of permanent initialization root-cause repair. Controlled Linux atomic tests passed; this real crash report committed its error record, not an observed pre-commit interruption.',formal_training=False,performance_acceptance=False))
print(json.dumps(dict(status='AUDIT_PASS_PROTOCOL_AND_SEPARATE_CAPTURE_LIMITS',job=job,worker_cpu_snapshots=snapshots,max_TIDs=max_tids,atomic_residuals=sum(len(c['atomic_residuals']) for c in cases.values()),node_seconds=(end-start).total_seconds(),python_stack='LEGAL_CANCEL_NO_CAPTURE',proc='6_OK_2_KERNEL_STACK_PERMISSION_ERROR')))
