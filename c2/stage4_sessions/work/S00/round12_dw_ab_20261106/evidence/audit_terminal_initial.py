"""Audit raw JSON/byte evidence only; never load data arrays or checkpoints."""
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
from prepare import sha,save
from review_gate import check_review
from r12_outcome import inspect,ORDER,STATUSES,require
root=Path(__file__).resolve().parent;received=root/'evidence/received';job=(root/'job_id.txt').read_text().strip()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def identity(value):
    import hashlib
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
receipt=load(root/'evidence/bundle_receipt.json');archive=root/('evidence/JOB_'+job+'_evidence.zip')
require(archive.stat().st_size==receipt['bytes'] and sha(archive)==receipt['sha256'],'archive identity changed')
index=load(received/'COLLECTION_S00.json')
for name,meta in index['files'].items():
    if meta['archive_payload']:
        path=received/name;require(path.stat().st_size==meta['bytes'] and sha(path)==meta['sha256'],'raw bytes changed: '+name)
require(index['state'] in ('SUCCEEDED','FAILED','CANCELLED') and index['scheduler_pids_cleared'],'terminal/PID evidence missing')
require(index['source_status']=='UNCHANGED' and not index['missing'],'source/core evidence missing')
check_review(root)
for name,digest in load(root/'ARTIFACT_SHA256.json').items():require(sha(root/name)==digest,'local deployment drift: '+name)
for name,meta in load(root/'evidence/PROTECTED_BEFORE.json').items():require(Path(name).stat().st_size==meta['bytes'] and sha(name)==meta['sha256'],'old local original drift')
for prefix,status,count in [('OLD_INPUTS','OLD_INPUT_IDENTITIES_PASS',9),('FIXED_INPUTS','FIXED16_CURRENT_SOURCE_SHA_PASS',36)]:
    before,after=[load(received/(prefix+'_'+phase+'.json')) for phase in ('BEFORE','AFTER')]
    require(before['status']==after['status']==status and len(before['checked'])==len(after['checked'])==count and before['checked']==after['checked'],'old/fixed source bytes/SHA/mtime changed')
clean=load(received/'job_evidence/cleanup.json');summary=load(received/'job_evidence/SUMMARY.json')
require(clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'owned descendants not cleared')
outcome=inspect(received,job)
phases={};performance={};reference=load(root/'REFERENCE_FIRST5.json');epoch=load(root/'REFERENCE_EPOCH25.json');frozen=load(root/'S02_SOURCE_SHA256.json')
for phase,success in zip(ORDER,STATUSES):
    directory=received/'payload/outputs'/(phase+'_'+job);path=directory/('screen_result.json' if phase=='target' else 'result.json')
    if not path.is_file():continue
    app=load(path);phase_info={k:app.get(k) for k in ('status','error','completed_updates','planned_updates','consumed_frames','optimizer_updates_total','wall_seconds','timing','pid')}
    metrics=app.get('metrics',[]);phase_info.update(metric_count=len(metrics),failed_metrics=[m for m in metrics if m.get('passed') is not True])
    if app.get('status')!=success:
        phases[phase]=phase_info;continue
    require(app['source_manifest_sha256']==sha(root/'S02_SOURCE_SHA256.json'),'actual source manifest mismatch')
    require(str(app['job_id'])==job,'actual job identity mismatch')
    cpu=app['cpu36'];selected=set(cpu['receipt']['selected']);max_tids=0
    for point in cpu['checkpoints']:
        snapshot=point['snapshot'];require(snapshot['complete'] and not snapshot['errors'] and not snapshot['vanished'],'incomplete CPU snapshot')
        max_tids=max(max_tids,len(snapshot['threads']))
        for tid in snapshot['threads']:require(set(tid['affinity']) and set(tid['affinity'])<=selected,'TID outside selected36')
        if point['name']!='before_framework':require(point['torch_intraop']==36,'actual Torch intra-op differs')
    expected_snapshots=7 if phase=='target' else (24 if phase=='strict' else 54)
    require(len(cpu['checkpoints'])==expected_snapshots,'missing phase CPU checkpoints')
    phase_info.update(cpu_snapshots=len(cpu['checkpoints']),max_observed_TIDs=max_tids,torch_intraop=app['runtime']['torch_threads'],torch_interop=app['runtime']['interop_threads'],libraries=app['runtime']['libraries'],imports=app['imports'])
    for role in ('baseline','candidate'):require(app['imports'][role]['sha256']==frozen[role+'/kml_ops.py'],'actual import SHA mismatch')
    for metric in metrics:
        limit=2e-6 if '.state.' in metric['name'] else 2e-5
        require(metric['passed'] and all(math.isfinite(metric[k]) for k in ('max_abs','l2_relative','reference_norm')) and metric['max_abs']<=limit and (metric['reference_norm']<=1e-8 or metric['l2_relative']<=2e-6),'original metric tolerance failed')
    phase_info.update(max_abs=max(m['max_abs'] for m in metrics),max_l2_relative=max(m['l2_relative'] for m in metrics))
    if phase!='target':
        require(app['descriptor_sha256']==sha(root/'ENGINEERING_DESCRIPTOR.json') and app['normalization']==reference['normalization'],'descriptor/statistics drift')
        steps=app['steps'];roles=['baseline','candidate'] if phase=='strict' else [phase[5:]]
        for record in steps:
            ref=epoch['steps'][record['step']-1]
            require(record['frame_indices']==ref['frame_indices'] and identity(record['frame_ids'])==ref['frame_ids_sha256'] and record['mask_sha256']==ref['mask_sha256'],'original epoch frame/mask changed')
        ledger=load(directory/'EXPOSURE_LEDGER.json');n=5 if phase=='strict' else 25
        require([x['frame_ids'] for x in ledger['confirmed_updates']]==[x['frame_ids'] for x in steps if x['role']==roles[0]],'ledger/step frame mismatch')
        for role in roles:require(app['initialization'][role]==reference['initialization'],'original full model initialization changed')
        phase_info.update(confirmed_ledger_updates=n,in_flight=ledger['in_flight'],native_counts=app['native_counts'])
        if phase=='strict':
            metric_names={m['name'] for m in metrics};parameter_sets=[]
            for step in range(1,6):
                parameters={name[len(str(step)+'.param.'):] for name in metric_names if name.startswith(str(step)+'.param.')};require(parameters,'all-parameter comparison missing')
                for kind in ('grad','delta'):
                    require({name[len(str(step)+'.'+kind+'.'):] for name in metric_names if name.startswith(str(step)+'.'+kind+'.')}==parameters,'full gradient/delta coverage missing')
                for state in ('exp_avg','exp_avg_sq'):
                    require({name[len(str(step)+'.state.'):-(len(state)+1)] for name in metric_names if name.startswith(str(step)+'.state.') and name.endswith('.'+state)}==parameters,'full AdamW moment coverage missing')
                require({str(step)+'.output.'+k for k in ('h','v','coarse')}|{str(step)+'.loss.'+k for k in ('total','voltage','coarse')}|{str(step)+'.input_grad.'+str(i) for i in (0,1)}<=metric_names,'output/loss/input-gradient coverage missing')
                parameter_sets.append(parameters)
            require(all(p==parameter_sets[0] for p in parameter_sets),'strict parameter set changed')
            phase_info['compared_parameters_per_step']=len(parameter_sets[0])
        else:
            cp=app['checkpoint'];meta=index['files']['payload/outputs/'+phase+'_'+job+'/checkpoints/final.pt']
            require(meta['bytes']==cp['bytes'] and meta['sha256']==cp['sha256'] and not meta['archive_payload'],'remote checkpoint identity mismatch')
            times=[row['step_seconds'] for row in steps];sample=times[5:];require(len(sample)==20,'full observed20 required')
            performance[roles[0]]=dict(warmup5_seconds=times[:5],observed20_seconds=sample,observed20_median_seconds=statistics.median(sample),observed20_range_seconds=[min(sample),max(sample)],all25_seconds=times,all25_training_seconds=sum(times),timing=app['timing'],checkpoint=cp,recovery=app['recovery'],rss_before_MiB=[row['rss_before']['rss_MiB'] for row in steps],rss_after_MiB=[row['rss_after']['rss_MiB'] for row in steps],process_lifetime_HWM_MiB=max(row[k]['peak_rss_MiB'] for row in steps for k in ('rss_before','rss_after')),rss_scope='independent perf process at same before/after update sampling; HWM is process lifetime, not per-step exclusive or whole-job final peak')
    phases[phase]=phase_info
schedule=load(received/'djob_final.json')['data']['successData'][0];group=schedule['resGroups'][0]
require(schedule['exclusive'] and schedule['jobWallClockLimit']==900 and schedule['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'resource/retry drift')
require(group['resReq']['cpu']==group['resAlloc']['cpu']==38 and group['resReq']['mem']==group['resLimit']['mem']==group['resAlloc']['mem']==24576,'actual CPU/DDR allocation changed')
if outcome['complete']:require(index['state']=='SUCCEEDED' and index['job_exit_code']==summary['exit_code']==0,'complete chain terminal mismatch')
if outcome['complete']:
    require(len({phases[p]['pid'] for p in ORDER})==4,'four distinct phase processes required')
    mtimes=[index['files']['payload/outputs/'+phase+'_'+job+'/'+('screen_result.json' if phase=='target' else 'result.json')]['mtime_ns'] for phase in ORDER]
    require(mtimes==sorted(mtimes) and len(set(mtimes))==4,'original stage completion order differs')
start,end=[datetime.fromisoformat(schedule[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
save(root/'RUN_AUDIT.json',dict(status='R12_FULL_CHAIN_COMPLETE_EXPLORATORY_ONLY' if outcome['complete'] else 'R12_FAILED_OR_INCOMPLETE_RAW_EVIDENCE_PRESERVED',job_id=job,host=schedule['taskExecNodes'],scheduler_state=index['state'],job_exit_code=index['job_exit_code'],outcome=outcome,phases=phases,performance=performance,node_seconds=(end-start).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],archive=receipt,old9_and_fixed36_unchanged=True,source_status='UNCHANGED',all_owned_processes_reaped=True,scheduler_pids_cleared=True,signal_fault_cleanup_triggered=bool(clean['actions']),active_s00_job=None,engineering_only=True,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',scientific_acceptance=False,steady_state_speedup_acceptance=False))
print(json.dumps(dict(job=job,complete=outcome['complete'],outcome=outcome,performance={k:{x:v[x] for x in ('observed20_median_seconds','observed20_range_seconds','all25_training_seconds','process_lifetime_HWM_MiB')} for k,v in performance.items()})))
