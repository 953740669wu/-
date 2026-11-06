"""Only JSON/bytes from the unique R11 job; never load a model or checkpoint."""
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from gemm_outcome import inspect

ROOT=Path(__file__).resolve().parent
RECEIVED=ROOT/'evidence/received'
JOB=(ROOT/'job_id.txt').read_text().strip()


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def identity(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    receipt=load(ROOT/'evidence/bundle_receipt.json');archive=ROOT/('evidence/JOB_'+JOB+'_evidence.zip')
    require(sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes'],'archive drift')
    index=load(RECEIVED/'COLLECTION_S00.json')
    for name,meta in index['files'].items():
        if meta['archive_payload']:
            p=RECEIVED/name;require(sha(p)==meta['sha256'] and p.stat().st_size==meta['bytes'],'raw file drift: '+name)
    require(index['state']=='SUCCEEDED' and index['job_exit_code']==0 and index['scheduler_pids_cleared'],'terminal/PID failure')
    require(index['source_status']=='UNCHANGED' and not index['missing'],'source/evidence incomplete')
    from review_gate import check_review
    check_review(ROOT)
    for name,meta in load(ROOT/'evidence/PROTECTED_BEFORE.json').items():
        p=ROOT.parents[4]/name
        require(p.stat().st_size==meta['bytes'] and sha(p)==meta['sha256'],'protected local original changed: '+name)
    before_fixed=load(ROOT/'evidence/FIXED_INPUT_IDENTITIES.json')
    after_fixed=load(RECEIVED/'FIXED_INPUTS_AFTER.json')
    require(before_fixed['status']==after_fixed['status']=='FIXED16_CURRENT_SOURCE_SHA_PASS','fixed source final gate failed')
    require(before_fixed['files']==after_fixed['files']==36 and before_fixed['units']==after_fixed['units']==16,'fixed source set changed')
    require(before_fixed['checked']==after_fixed['checked'],'fixed36 input path/bytes/SHA/mtime changed')
    outcome=inspect(RECEIVED,JOB);require(outcome['gemm5_complete'] and not outcome['errors'],'gemm5 incomplete')
    run=RECEIVED/'payload/outputs'/('gemm_'+JOB);app=load(run/'result.json')
    source_manifest=load(ROOT/'S02_SOURCE_SHA256.json');observation=app['gemm_observation']
    require(observation['observer_import']['sha256']==observation['observer_source_sha256']==source_manifest['gemm_observer.py'],'actual observer import changed')
    require(observation['original_sgemm_type']=='_FuncPtr','actual native ctypes function required')
    runtime=app['runtime']
    require(runtime['backend']=='kml' and runtime['libraries']==runtime['libraries_after'],'actual backend/library source changed')
    libraries={x['sha256'] for x in runtime['libraries']}
    require({'a52c4da1a87b1a65b11121ecab2b8d0ca3fd2a03a5c92422873592381a92dd73','d336ec367ed4bd0a9594cc49bcef6ca9f8cdc7a44ce403509127af2d4bc0f8ac','c9b2f040c5b4756d426589956059e3865749cd8751eb3914c57d42a9e84ebf3c'}<=libraries,'original shim/OpenMP/KML identity missing')
    steps=[json.loads(s) for s in (run/'steps.jsonl').read_text().splitlines()]
    reference=load(ROOT/'REFERENCE_FIRST5.json')
    require(app['initialization']==reference['initialization'] and app['normalization']==reference['normalization'],'initialization/scale changed')
    require(app['data_identity']['corpus']==reference['corpus'] and app['data_identity']['units']==reference['units'],'fixed data changed')
    require(app['data_identity']['descriptor_sha256']==reference['descriptor_sha256']==sha(ROOT/'ENGINEERING_DESCRIPTOR.json'),'descriptor drift')
    all_indices=[];metrics=[]
    for i,step in enumerate(steps,1):
        old=reference['steps'][i-1]
        require(step['frame_indices']==old['frame_indices'] and identity(step['frame_ids'])==old['frame_ids_sha256'],'baseline frame order/origin changed')
        require(step['mask_sha256']==old['mask_sha256'] and step['kml_calls']==old['kml_calls']==149,'mask/KML identity changed')
        for metric in step['baseline_loss_metrics']:
            name=metric['name'].rsplit('.',1)[-1];ref=old['losses'][name];got=step['losses'][name]
            absolute=abs(got-ref);norm=abs(ref);relative=absolute/max(norm,1e-12)
            require(math.isfinite(got) and absolute<=2e-5 and (norm<=1e-8 or relative<=2e-6),'original scalar loss tolerance failed')
            require(metric['max_abs']==absolute and metric['l2_relative']==relative and metric['reference_norm']==norm,'loss comparison receipt differs from raw scalar values')
        metrics.extend(step['baseline_loss_metrics']);all_indices.extend(step['frame_indices'])
    require(len(metrics)==15 and all(x['passed'] for x in metrics),'original loss comparisons failed')
    require(len(all_indices)==len(set(all_indices))==320 and len({s['mask_sha256'] for s in steps})==5,'frame padding/repetition or mask repetition')
    cpu=app['cpu36'];selected=set(cpu['receipt']['selected']);require(len(selected)==36 and cpu['errors']==[],'CPU36 receipt errors')
    max_tids=0
    for checkpoint in cpu['checkpoints']:
        snapshot=checkpoint['snapshot'];require(snapshot['complete'] and not snapshot['vanished'] and not snapshot['errors'],'incomplete CPU snapshot')
        max_tids=max(max_tids,len(snapshot['threads']))
        for tid in snapshot['threads']:require(set(tid['affinity']) and set(tid['affinity'])<=selected,'TID outside selected36')
        if checkpoint['name']!='before_framework':require(checkpoint['torch_intraop']==36,'actual Torch not36')
    ledger=load(run/'EXPOSURE_LEDGER.json')
    require(ledger['in_flight'] is None and len(ledger['confirmed_updates'])==5,'unfinished exposure update')
    require([x['frame_ids'] for x in ledger['confirmed_updates']]==[x['frame_ids'] for x in steps],'ledger/log mismatch')
    checkpoint=app['checkpoint'];meta=index['files']['payload/outputs/gemm_'+JOB+'/checkpoints/final.pt']
    require(meta['bytes']==checkpoint['bytes'] and meta['sha256']==checkpoint['sha256'] and not meta['archive_payload'],'remote checkpoint identity mismatch')
    clean=load(RECEIVED/'job_evidence/cleanup.json');require(clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'owned cleanup incomplete')
    before={}
    for line in (ROOT/'evidence/INITIAL_REMOTE_READONLY.txt').read_text(encoding='utf-8-sig').splitlines():
        match=re.fullmatch(r'([a-f0-9]{64})\s+(/.*)',line)
        if match:before[match[2]]=match[1]
    after={}
    for line in (RECEIVED/'OLD_INPUTS_AFTER.sha256').read_text().splitlines():
        digest,path=line.split(None,1);after[path.strip()]=digest
    require(len(before)==7 and all(after.get(p)==h for p,h in before.items()),'original source/ledger/checkpoint changed')
    job=load(RECEIVED/'djob_final.json')['data']['successData'][0];group=job['resGroups'][0]
    require(job['exclusive'] and job['jobWallClockLimit']==900 and job['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'resource/retry drift')
    require(group['resReq']['cpu']==38 and group['resReq']['mem']==group['resLimit']['mem']==24576,'resource budget changed')
    begin,end=[datetime.datetime.fromisoformat(job[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
    summary=dict(status='PASS_GEMM5_ENGINEERING_EVIDENCE_ONLY',job_id=JOB,host=cpu['host'],scheduler_state=job['state'],exit_code=0,
       continuous_updates=5,warmup_steps=[1,2],sampled_steps=[3,4,5],actual_train_frames=320,normalization_frames=1600,
       original_loss_metrics=15,original_loss_max_abs=max(x['max_abs'] for x in metrics),original_loss_max_l2_relative=max(x['l2_relative'] for x in metrics),same_initialization_scale_frames_masks=True,
       samples=outcome['samples'],capture_bytes=sum(c['bytes'] for c in outcome['samples']),
       cpu_complete_snapshots=len(cpu['checkpoints']),all_sampled_TIDs_within_selected36=True,max_observed_TIDs=max_tids,
       actual_torch_intraop=app['runtime']['torch_threads'],actual_torch_interop=app['runtime']['interop_threads'],
       training_kml_calls=sum(s['kml_calls'] for s in steps),runtime_kml_calls=app['runtime']['kml_gemm_calls'],
       timing=app['timing'],step_wall_seconds=[dict(step=s['step'],step_seconds=s['step_seconds'],observed_call_wall_seconds=s['observed_call_wall_seconds']) for s in steps],
       checkpoint=checkpoint,recovery=app['recovery'],exposure_updates=5,exposure_in_flight=None,
       old_inputs_ledger_checkpoint_unchanged=True,scheduler_pids_cleared=True,all_owned_processes_reaped=True,
       original_fixed36_path_bytes_sha_mtime_unchanged=True,actual_observer_import=observation['observer_import'],actual_native_function_type=observation['original_sgemm_type'],actual_libraries_unchanged=runtime['libraries'],
       signal_fault_cleanup_triggered=bool(clean['actions']),node_seconds=(end-begin).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],
       source_status='UNCHANGED',missing=[],archive=receipt,engineering_only=True,formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
       native_kml_kernel_time='UNKNOWN_CTYPES_NOT_PURE_KERNEL',in_step_observer_overhead='UNKNOWN_WITHOUT_MATCHED_CONTROL',
       scientific_acceptance=False,steady_state_performance_acceptance=False)
    (ROOT/'RUN_AUDIT.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
