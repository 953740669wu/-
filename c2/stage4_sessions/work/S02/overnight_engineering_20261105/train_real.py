"""One authorized real-corpus encoder pilot, fp32/CKPT0, one epoch or 200 updates."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random
import signal
import sys
import time
import traceback

import cpu36_guard
from diagnostic_common import configure_backend,finish_backend
import memory_metrics
import pilot_training as training
import real_data

ROOT=Path(__file__).resolve().parent
STOP_REQUESTED=False


def request_stop(_signal,_frame):
    global STOP_REQUESTED
    STOP_REQUESTED=True


def source_identity():
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text())
    for name,value in source.items():
        if real_data.sha(ROOT/name)!=value:raise ValueError('source SHA mismatch: '+name)
    return dict(manifest_sha256=real_data.sha(ROOT/'SOURCE_SHA256.json'),files=source)


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main(args,result):
    started=time.monotonic()
    result['source']=source_identity()
    metadata=real_data.load_descriptor(args.descriptor,args.descriptor_sha256)
    result['data_identity']=metadata['identity']
    result['cpu36']={}
    cpu36_guard.prepare(args.expected_cpus,args.cpu_contract,result['cpu36'])
    import numpy as np
    import torch
    cpu36_guard.checkpoint(result['cpu36'],'after_framework',torch)
    runtime,expected=configure_backend(torch,'kml',args.expected_cpus);result['runtime']=runtime
    cpu36_guard.checkpoint(result['cpu36'],'after_backend',torch)
    loaded=real_data.load_arrays(metadata)
    frames=len(loaded['train']['v'])
    real_data.require(frames>args.batch_size,'pilot needs multiple real batches; never duplicate/pad frames')
    result['normalization']=dict(image_scale=loaded['image_scale'],scope=loaded['normalization_scope'],
        fit_partition='train',train_units=[x['unit'] for x in metadata['units']['train']])
    result['dataset_counts']=dict(train_frames=frames,val_frames=len(loaded['val']['v']) if loaded['val'] else 0,
        train_units=len(metadata['units']['train']),val_units=len(metadata['units']['val']))
    sys.path.insert(0,str(ROOT/'tests'))
    import check_equivalence as accepted
    definitions=accepted.model_definitions(torch)
    torch.manual_seed(0);np.random.seed(0);random.seed(0)
    factory=definitions['Encoder'];model=factory()
    if sum(p.numel() for p in model.parameters())!=37995777:raise ValueError('full encoder identity/size mismatch')
    opt=training.optimizer(torch,model);angles=definitions['protocol_angles'](16,1)
    result['initialization']=dict(kind='original_torch_encoder_default_seed0',parameters=37995777,
        model_source_sha256=real_data.sha(ROOT/'baseline/s4_models.py'),initial_weights_sha256=training.model_sha(model))
    order=list(range(frames));random.Random(0).shuffle(order)
    planned=min(200,math.ceil(frames/args.batch_size));step=cursor=0
    result['planned_updates']=planned;result['completed_updates']=0
    cpu36_guard.checkpoint(result['cpu36'],'initialized',torch)
    before=runtime['kml_gemm_calls']
    result['val_initial']=training.evaluate(torch,model,loaded['val'],args.batch_size,angles)
    result['val_initial']['kml_calls']=runtime['kml_gemm_calls']-before
    if loaded['val'] and result['val_initial']['kml_calls']<=0:raise ValueError('no KML in initial validation')
    cpu36_guard.checkpoint(result['cpu36'],'initial_val',torch)
    records=[];stop='epoch_complete'
    with (args.output_dir/'steps.jsonl').open('x',encoding='utf-8') as log:
        while cursor<frames and step<200:
            # The outer process is limited to840s. Reserve120s for val/save/recovery.
            if STOP_REQUESTED or time.monotonic()-started>=720:
                stop='BUDGET_INCOMPLETE';break
            indices=order[cursor:cursor+args.batch_size]
            load_start=time.perf_counter();values=training.batch(torch,loaded['train'],indices,angles)
            loader_seconds=time.perf_counter()-load_start
            mask=torch.rand(len(indices),208)<0.5
            if not mask.any():raise ValueError('empty training mask; no resampling')
            cpu36_guard.checkpoint(result['cpu36'],f'before_train_{step+1}',torch)
            rss_before=memory_metrics.rss();calls=runtime['kml_gemm_calls']
            tick=time.perf_counter();losses=training.train_step(torch,model,opt,values,mask)
            elapsed=time.perf_counter()-tick;rss_after=memory_metrics.rss()
            training.validate_update(torch,model,opt,values,step+1)
            if any(not torch.isfinite(value) for value in losses.values()):raise ValueError('nonfinite training loss')
            count=runtime['kml_gemm_calls']-calls
            if count<=0:raise ValueError('no actual KML in training step')
            step+=1;cursor+=len(indices);result['completed_updates']=step
            cpu36_guard.checkpoint(result['cpu36'],f'after_train_{step}',torch)
            record=dict(step=step,batch_size=len(indices),frame_indices=indices,
                frame_ids=[loaded['train']['frame_ids'][i] for i in indices],masked_elements=int(mask.sum()),
                mask_sha256=hashlib.sha256(mask.numpy().tobytes()).hexdigest(),
                losses={name:value.item() for name,value in losses.items()},loader_seconds=loader_seconds,
                step_seconds=elapsed,rss_before=rss_before,rss_after=rss_after,rss_peak_scope='process_lifetime',
                kml_calls=count,adamw_step=step,cursor=cursor)
            log.write(json.dumps(record)+'\n');log.flush();records.append({k:v for k,v in record.items() if k!='frame_ids'})
    if cursor<frames and step==200:stop='update_cap_200'
    result.update(stop_reason=stop,steps=records,consumed_frames=cursor,elapsed_seconds=time.monotonic()-started)
    # A hard outer TERM leaves an honest incomplete checkpoint, without extra work.
    before=runtime['kml_gemm_calls']
    result['val_final']=dict(status='VAL_NOT_RUN_BUDGET') if STOP_REQUESTED else training.evaluate(torch,model,loaded['val'],args.batch_size,angles)
    result['val_final']['kml_calls']=runtime['kml_gemm_calls']-before
    if loaded['val'] and not STOP_REQUESTED:
        if result['val_final']['mask_sha256']!=result['val_initial']['mask_sha256']:raise ValueError('validation masks changed')
        if result['val_final']['kml_calls']<=0:raise ValueError('no KML in final validation')
    cpu36_guard.checkpoint(result['cpu36'],'final_val',torch)
    if source_identity()!=result['source']:raise ValueError('pilot source changed during execution')
    real_data.load_descriptor(args.descriptor,args.descriptor_sha256)
    for items in metadata['units'].values():
        for item in items:
            real_data.require(real_data.sha(item['path'])==item['npz_sha256'] and
                real_data.sha(item['sidecar_path'])==item['sidecar_sha256'],'input source changed during execution')
    result['source_and_data_after']='PASS_SAME_FROZEN_IDENTITIES'
    progress=dict(epoch_completed=cursor==frames,epoch_order=order,cursor=cursor,optimizer_updates=step,
                  planned_updates=planned,stop_reason=stop,order_seed=0,
                  order_method='Python_Random_shuffle_once',cursor_unit='frame_offset')
    identity=dict(source=result['source'],data=result['data_identity'],config=result['config'],
                  initialization=result['initialization'])
    result['checkpoint']=training.save_checkpoint(torch,args.output_dir/'checkpoints/final.pt',model,opt,
                                                  identity,progress,result['normalization'])
    cpu36_guard.checkpoint(result['cpu36'],'checkpoint_saved',torch)
    if STOP_REQUESTED:
        result['recovery']=dict(status='NOT_RUN_BUDGET',extra_updates=0)
    else:
        probe_values=training.batch(torch,loaded['train'],list(range(min(2,frames))),angles)
        result['recovery']=training.verify_restore(torch,result['checkpoint'],model,opt,factory,identity,
            progress,result['normalization'],probe_values,accepted.compare)
        cpu36_guard.checkpoint(result['cpu36'],'restore_verified',torch)
    finish_backend(runtime,expected)
    cpu36_guard.checkpoint(result['cpu36'],'publish',torch)
    names=['before_framework','after_framework','after_backend','initialized','initial_val']
    for i in range(1,step+1):names += [f'before_train_{i}',f'after_train_{i}']
    names += ['final_val','checkpoint_saved']+(['restore_verified'] if not STOP_REQUESTED else [])+['publish']
    if result['cpu36']['errors'] or [x['name'] for x in result['cpu36']['checkpoints']]!=names:raise ValueError('missing pilot CPU36 evidence')
    incomplete=stop=='BUDGET_INCOMPLETE' or STOP_REQUESTED or step<planned
    result['status']='INCOMPLETE' if incomplete else 'PILOT_COMPLETE_NOT_QUALITY_ACCEPTANCE'
    return 3 if incomplete else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor',type=Path)
    parser.add_argument('--descriptor-sha256')
    parser.add_argument('--expected-cpus',type=lambda s:[int(x) for x in s.split(',')])
    parser.add_argument('--cpu-contract',type=Path)
    parser.add_argument('--batch-size',type=int,default=64)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.batch_size<=64:parser.error('batch size must be1..64, no accumulation')
    if any((args.output_dir/name).exists() for name in ('result.json','steps.jsonl','checkpoints/final.pt')):
        parser.error('refuse existing pilot outputs')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    signal.signal(signal.SIGTERM,request_stop)
    result=dict(status='STARTED',started_utc=datetime.now(timezone.utc).isoformat(),protocol=real_data.PROTOCOL,
        config=dict(belt='16_adjacent',part='pre',precision='fp32',checkpoint=False,compile=False,hbm=False,
            attention='original_native_SDPA',linear='existing_KML_fp32',batch_size=args.batch_size,
            max_epochs=1,max_updates=200,gradient_accumulation=False,train_seed=0,subset_seed=2026,
            lr=1e-4,betas=[0.9,0.999],eps=1e-8,weight_decay=0.01,threads=36))
    try:code=main(args,result)
    except real_data.DataNotReady as exc:result.update(status='DATA_NOT_READY',error=str(exc));code=2
    except Exception as exc:result.update(status='ERROR_RUNTIME_OR_STATE',error=repr(exc),traceback=traceback.format_exc());code=2
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    write_json(args.output_dir/'result.json',result)
    print(json.dumps({k:result[k] for k in ('status','completed_updates','stop_reason','error') if k in result},indent=2))
    sys.exit(code)
