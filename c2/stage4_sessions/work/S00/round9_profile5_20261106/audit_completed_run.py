"""Only JSON/bytes from the unique R9 job; never load a model or checkpoint."""
import datetime
import hashlib
import json
from pathlib import Path
import re
from profile_outcome import inspect

ROOT=Path(__file__).resolve().parent
RECEIVED=ROOT/'evidence/received'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def identity(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    receipt=load(ROOT/'evidence/bundle_receipt.json');archive=ROOT/'evidence/JOB_2048959_evidence.zip'
    require(sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes'],'archive drift')
    index=load(RECEIVED/'COLLECTION_S00.json')
    for name,meta in index['files'].items():
        if meta['archive_payload']:
            p=RECEIVED/name;require(sha(p)==meta['sha256'] and p.stat().st_size==meta['bytes'],'raw file drift: '+name)
    require(index['state']=='SUCCEEDED' and index['job_exit_code']==0 and index['scheduler_pids_cleared'],'terminal/PID failure')
    require(index['source_status']=='UNCHANGED' and not index['missing'],'source/evidence incomplete')
    outcome=inspect(RECEIVED,'2048959');require(outcome['profile5_complete'] and not outcome['errors'],'profile5 incomplete')
    run=RECEIVED/'payload/outputs/profile_2048959';app=load(run/'result.json')
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
        require(step['losses']==old['losses'],'baseline loss values differ')
        metrics.extend(step['baseline_loss_metrics']);all_indices.extend(step['frame_indices'])
    require(len(metrics)==15 and all(x['passed'] and x['max_abs']==x['l2_relative']==0 for x in metrics),'original loss comparisons failed')
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
    checkpoint=app['checkpoint'];meta=index['files']['payload/outputs/profile_2048959/checkpoints/final.pt']
    require(meta['bytes']==checkpoint['bytes'] and meta['sha256']==checkpoint['sha256'] and not meta['archive_payload'],'remote checkpoint identity mismatch')
    clean=load(RECEIVED/'job_evidence/cleanup.json');require(clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'owned cleanup incomplete')
    before={}
    for line in (ROOT/'evidence/INITIAL_REMOTE_READONLY_CONFIRMED.txt').read_text(encoding='utf-8-sig').splitlines():
        match=re.fullmatch(r'([a-f0-9]{64})\s+(/.*)',line)
        if match:before[match[2]]=match[1]
    after={}
    for line in (RECEIVED/'OLD_INPUTS_AFTER.sha256').read_text().splitlines():
        digest,path=line.split(None,1);after[path.strip()]=digest
    require(len(before)==4 and all(after.get(p)==h for p,h in before.items()),'original source/ledger/checkpoint changed')
    job=load(RECEIVED/'djob_final.json')['data']['successData'][0];group=job['resGroups'][0]
    require(job['exclusive'] and job['jobWallClockLimit']==900 and job['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'resource/retry drift')
    require(group['resReq']['cpu']==38 and group['resReq']['mem']==group['resLimit']['mem']==24576,'resource budget changed')
    begin,end=[datetime.datetime.fromisoformat(job[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
    summary=dict(status='PASS_PROFILE5_ENGINEERING_EVIDENCE_ONLY',job_id='2048959',host=cpu['host'],scheduler_state=job['state'],exit_code=0,
       continuous_updates=5,warmup_steps=[1,2],sampled_steps=[3,4,5],actual_train_frames=320,normalization_frames=1600,
       original_loss_metrics=15,original_loss_max_abs=0.,original_loss_max_l2_relative=0.,same_initialization_scale_frames_masks=True,
       captures=outcome['captures'],capture_bytes=sum(c[k]['bytes'] for c in outcome['captures'] for k in ('trace','summary')),
       cpu_complete_snapshots=len(cpu['checkpoints']),all_sampled_TIDs_within_selected36=True,max_observed_TIDs=max_tids,
       actual_torch_intraop=app['runtime']['torch_threads'],actual_torch_interop=app['runtime']['interop_threads'],
       training_kml_calls=sum(s['kml_calls'] for s in steps),runtime_kml_calls=app['runtime']['kml_gemm_calls'],
       timing=app['timing'],phase_wall_seconds=[dict(step=s['step'],sampled=s['profile']['sampled'],**s['profile']['phase_seconds']) for s in steps],
       checkpoint=checkpoint,recovery=app['recovery'],exposure_updates=5,exposure_in_flight=None,
       old_inputs_ledger_checkpoint_unchanged=True,scheduler_pids_cleared=True,all_owned_processes_reaped=True,
       signal_fault_cleanup_triggered=bool(clean['actions']),node_seconds=(end-begin).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],
       source_status='UNCHANGED',missing=[],archive=receipt,engineering_only=True,formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
       native_kml_kernel_time='UNKNOWN_PYTHON_ENVELOPES_ONLY',in_step_profiler_overhead='UNKNOWN_WITHOUT_MATCHED_CONTROL',
       scientific_acceptance=False,steady_state_performance_acceptance=False)
    (ROOT/'RUN_AUDIT.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
