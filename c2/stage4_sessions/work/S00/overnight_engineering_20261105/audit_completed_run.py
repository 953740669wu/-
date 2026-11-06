"""Read original JSON/bytes of job2043445; never import Torch or load checkpoint."""
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parent
RECEIVED=ROOT/'evidence/received'


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    index=load(RECEIVED/'COLLECTION_S00.json');receipt=load(ROOT/'evidence/bundle_receipt.json')
    archive=ROOT/'evidence/JOB_2043445_evidence.zip'
    require(sha(archive)==receipt['sha256'] and archive.stat().st_size==receipt['bytes'],'bundle drift')
    for name,meta in index['files'].items():
        if meta['archive_payload']:
            p=RECEIVED/name;require(p.stat().st_size==meta['bytes'] and sha(p)==meta['sha256'],'archived bytes drift: '+name)
    require(index['state']=='SUCCEEDED' and index['job_exit_code']==0 and index['scheduler_pids_cleared'],'scheduler failure or PID uncleared')
    require(index['source_status']=='UNCHANGED' and not index['missing'],'missing evidence/source drift')
    job=load(RECEIVED/'djob_final.json')['data']['successData'][0]
    require(job['jobWallClockLimit']==900 and job['exclusive'] and job['retryPolicy']==dict(maxRetryCnt=0,currentRetryTimes=0),'resource/retry mismatch')
    group=job['resGroups'][0]
    require(group['resReq']['cpu']==38 and group['resReq']['mem']==group['resLimit']['mem']==24576,'wrong allocated resources')
    run=RECEIVED/'payload/outputs/engineering_2043445'
    app=load(run/'result.json');steps=[json.loads(x) for x in (run/'steps.jsonl').read_text().splitlines()]
    description=load(ROOT/'ENGINEERING_DESCRIPTOR.json');units={x['unit']:x for x in description['train']}
    sample=load(ROOT/'evidence/REAL_SAMPLE_CHECKS.json');bases={x['unit']:x['base_of_pair'] for x in sample['selected']}
    require(app['status']=='ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE' and app['engineering_only'],'wrong scope/result')
    for k,v in dict(formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT').items():require(app[k]==v,'scope drift: '+k)
    require(app['initialization']['parameters']==37995777 and app['data_identity']['descriptor_sha256']==sha(ROOT/'ENGINEERING_DESCRIPTOR.json'),'model/data identity mismatch')
    require(app['completed_updates']==app['planned_updates']==len(steps)==25 and app['consumed_frames']==1600 and app['stop_reason']=='epoch_complete','update/epoch mismatch')
    all_indices=[];frames=[]
    for i,s in enumerate(steps,1):
        require(s['step']==s['adamw_step']==i and s['cursor']==i*64 and s['batch_size']==len(s['frame_indices'])==len(s['frame_ids'])==64,'step/batch/state mismatch')
        require(s['kml_calls']>0 and s['masked_elements']>0 and all(math.isfinite(v) for v in s['losses'].values()),'missing KML/mask or nonfinite loss')
        all_indices.extend(s['frame_indices']);frames.extend(s['frame_ids'])
        for frame in s['frame_ids']:
            u=units[frame['unit']];row=frame['pair_index']
            require(frame['case']==u['case'] and frame['belt']==u['belt'] and frame['placement']==u['placement'] and frame['contact']==u['contact'] and frame['subject_id'] is None,'frame origin mismatch')
            require(frame['npz_sha256']==u['npz_sha256'] and frame['sidecar_sha256']==u['sidecar_sha256'] and frame['baseline_index']==bases[u['unit']][row],'frame SHA/baseline mismatch')
    require(sorted(all_indices)==list(range(1600)) and len({(x['unit'],x['pair_index']) for x in frames})==1600,'missing/repeated actual frames')
    require(len({s['mask_sha256'] for s in steps})==25,'training masks repeated')
    require(app['normalization']['image_scale']==sample['image_absmax_engineering_train_only'],'engineering train-only scale mismatch')
    cpu=app['cpu36'];require(not cpu['errors'] and len(cpu['checkpoints'])==59,'CPU receipt missing/errors')
    selected=set(cpu['receipt']['selected']);require(len(selected)==36 and cpu['receipt']['reserved']==[36,37],'CPU36/reserved mismatch')
    max_tids=0
    for cp in cpu['checkpoints']:
        snap=cp['snapshot'];require(snap['complete'] and not snap['errors'] and not snap['vanished'] and snap['threads'],'incomplete TID snapshot')
        max_tids=max(max_tids,len(snap['threads']))
        for tid in snap['threads']:require(set(tid['affinity']) and set(tid['affinity'])<=selected,'TID outside selected36')
        if cp['name']!='before_framework':require(cp['torch_intraop']==36,'actual intraop not36')
    require(app['runtime']['backend']=='kml' and app['runtime']['kml_gemm_calls']>0,'KML absent')
    require(app['source_and_data_after']=='PASS_SAME_FROZEN_IDENTITIES','source/data final gate absent')
    recovery=app['recovery'];require(recovery['status']=='PASS_NO_EXTRA_UPDATE' and recovery['extra_updates']==0,'recovery failed/extra update')
    require(all(recovery[k] for k in ['parameters_exact','optimizer_exact','rng_exact','cursor_exact','identity_exact']),'restore state mismatch')
    checkpoint=app['checkpoint'];meta=index['files']['payload/outputs/engineering_2043445/checkpoints/final.pt']
    require(checkpoint['bytes']==meta['bytes'] and checkpoint['sha256']==meta['sha256'] and not meta['archive_payload'],'checkpoint remote identity mismatch')
    ledger=load(RECEIVED/'payload/outputs/EXPOSURE_LEDGER.json')
    require(ledger['in_flight'] is None and len(ledger['confirmed_updates'])==25 and all(x['usage_status']=='CONSUMED_CONFIRMED' for x in ledger['units']),'exposure completion mismatch')
    require([x['frame_ids'] for x in ledger['confirmed_updates']]==[x['frame_ids'] for x in steps],'ledger/frame logs differ')
    clean=load(RECEIVED/'job_evidence/cleanup.json');require(clean['all_reaped'] and clean['remaining_live']==clean['remaining_processes']==[],'cleanup incomplete')
    begin,end=[datetime.datetime.fromisoformat(job[k].replace('Z','+00:00')) for k in ('startTime','endTime')]
    times=[s['step_seconds'] for s in steps]
    values=[s[k] for s in steps for k in ('rss_before','rss_after')]
    summary=dict(status='PASS_ENGINEERING_EVIDENCE_ONLY',job_id='2043445',host=cpu['host'],scheduler_state=job['state'],exit_code=0,
      engineering_only=True,formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
      completed_updates=25,actual_frames=1600,selected_units=len(units),selected_cases=description['selection']['selected_cases'],
      no_duplicate_or_padding_frames=True,distinct_training_masks=25,adamw_steps_contiguous=True,
      cpu_checkpoint_count=59,all_sampled_TIDs_within_selected36=True,max_observed_TIDs=max_tids,
      observed_torch_intraop=app['runtime']['torch_threads'],observed_torch_interop=app['runtime']['interop_threads'],
      cpu_evidence_scope='all TIDs per59 complete snapshots; not continuous monitoring; no setter used',
      kml_calls_training=sum(x['kml_calls'] for x in steps),kml_calls_runtime=app['runtime']['kml_gemm_calls'],
      step_seconds=dict(median=statistics.median(times),min=min(times),max=max(times)),
      sampled_process_lifetime_hwm_bytes=max(x['peak_rss_bytes'] for x in values),
      rss_scope='process lifetime HWM sampled during25 updates; not exclusive step memory or whole-job post-restore peak',
      first_loss=steps[0]['losses'],last_loss=steps[-1]['losses'],timing=app['timing'],
      checkpoint=checkpoint,recovery=recovery,all_owned_processes_reaped=True,scheduler_pids_cleared=True,
      node_seconds=(end-begin).total_seconds(),scheduler_usage_seconds=group['nodeResUsages'][0]['wallclockDuration'],
      source_status=index['source_status'],missing=[],bundle=receipt,
      scientific_acceptance=False,performance_acceptance=False,future_subject_test_exclusion_review_required=True)
    (ROOT/'RUN_AUDIT.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
