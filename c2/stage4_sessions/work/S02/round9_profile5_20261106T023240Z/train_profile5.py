"""Bounded CPU profile: same first5 updates, warmup2/sample3, no performance acceptance."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import os
import random
import signal
import sys
import time
import traceback

import cpu36_guard
from diagnostic_common import configure_backend,finish_backend
import memory_metrics
import engineering_training as training
import engineering_data
import real_data
import profile_probe
import profile_contract

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
    metadata=engineering_data.load_descriptor(args.descriptor,args.descriptor_sha256)
    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())
    if args.descriptor_sha256!=reference['descriptor_sha256']:raise ValueError('exact baseline descriptor bytes required')
    profile_contract.check_data(metadata['description'],reference)
    if ROOT.name!='payload' or not ROOT.parent.name.startswith('S02_PROFILE5_') or ROOT.parent.parent!=Path('/home/share/dengqingtian/opt/stage4_sessions/S00'):
        raise ValueError('new S00/S02_PROFILE5_*/payload required; never reuse baseline deployment')
    if args.output_dir.resolve().parent!=ROOT/'outputs' or args.output_dir.name!='profile_'+os.environ.get('CCS_JOB_ID',''):
        raise ValueError('new owned profile job output path required')
    ledger=engineering_data.Exposure(args.output_dir/'EXPOSURE_LEDGER.json',metadata['description'])
    result['exposure_path_policy']='profile ledger in fresh job outputs; original descriptor runtime ledger is read-only and NOT USED as output'
    result['exposure_ledger']=dict(path=str(ledger.path),initial=metadata['description']['exposure_ledger'])
    result['data_identity']=metadata['identity']
    result['cpu36']={}
    cpu36_guard.prepare(args.expected_cpus,args.cpu_contract,result['cpu36'])
    import numpy as np
    import torch
    cpu36_guard.checkpoint(result['cpu36'],'after_framework',torch)
    runtime,expected=configure_backend(torch,'kml',args.expected_cpus);result['runtime']=runtime
    cpu36_guard.checkpoint(result['cpu36'],'after_backend',torch)
    import kml_ops
    probe=profile_probe.Probe(torch,args.output_dir,kml_ops)
    result['profiling']=dict(warmup_updates=[1,2],sampled_updates=[3,4,5],updates=probe.records,
        activity='CPU',record_shapes=False,profile_memory=False,with_stack=False,with_flops=False,
        event_limit_per_sample=profile_probe.MAX_EVENTS,kml_markers_per_sample=profile_probe.MAX_KML_MARKERS,
        trace_limit_per_sample_bytes=profile_probe.TRACE_BYTES,summary_limit_per_sample_bytes=profile_probe.SUMMARY_BYTES,
        maximum_traces=3,maximum_summaries=3,
        overhead_scope='setup/start/stop/postprocess/export separately measured; event/marker overhead inside instrumented steps is UNKNOWN without matched unprofiled control; no throughput acceptance',
        trace_scope='CPU spans including nested events; do not sum inclusive totals or compare CPU time to wall as a percentage',
        kml_scope='Python GEMM envelope, not precise native kernel duration')
    tick=time.perf_counter()
    loaded=engineering_data.load_arrays(metadata,ledger)
    result['timing']['data_loading_seconds']=time.perf_counter()-tick
    frames=len(loaded['train']['v'])
    real_data.require(frames==1600 and args.batch_size==64,'same1600 frames/B64 required; no padding or scope changes')
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
    if result['initialization']!=reference['initialization'] or result['normalization']!=reference['normalization']:raise ValueError('baseline initialization/normalization drift')
    order=list(range(frames));random.Random(0).shuffle(order)
    planned=5;step=cursor=0
    result['planned_updates']=planned;result['completed_updates']=0
    cpu36_guard.checkpoint(result['cpu36'],'initialized',torch)
    result['val_initial']=dict(status='NOT_RUN_NO_FORMAL_SPLIT')
    cpu36_guard.checkpoint(result['cpu36'],'initial_val',torch)
    records=[];result['steps']=records;result['consumed_frames']=0;stop='profile_update_cap_5'
    with (args.output_dir/'steps.jsonl').open('x',encoding='utf-8') as log:
        while cursor<frames and step<5:
            # The outer process is limited to840s. Reserve120s for save/recovery.
            if STOP_REQUESTED or time.monotonic()-started>=720:
                stop='BUDGET_INCOMPLETE';break
            indices=order[cursor:cursor+args.batch_size]
            load_start=time.perf_counter();values=training.batch(torch,loaded['train'],indices,angles)
            loader_seconds=time.perf_counter()-load_start
            result['timing']['batch_materialization_seconds']+=loader_seconds
            diagnostic_start=time.perf_counter()
            mask=torch.rand(len(indices),208)<0.5
            if not mask.any():raise ValueError('empty training mask; no resampling')
            profile_contract.check_step_identity(step+1,indices,profile_contract.identity([loaded['train']['frame_ids'][i] for i in indices]),hashlib.sha256(mask.numpy().tobytes()).hexdigest(),reference)
            ledger.attempt(step+1,indices,[loaded['train']['frame_ids'][i] for i in indices])
            cpu36_guard.checkpoint(result['cpu36'],f'before_train_{step+1}',torch)
            rss_before=memory_metrics.rss();calls=runtime['kml_gemm_calls']
            pre_diagnostic=time.perf_counter()-diagnostic_start
            tick=time.perf_counter();losses,profile_record=probe.run(step+1,model,opt,values,mask)
            profiled_call_wall=time.perf_counter()-tick;elapsed=profile_record['instrumented_step_seconds'];rss_after=memory_metrics.rss()
            result['timing']['profiler_outside_step_seconds']+=profile_record['profiler_outside_step_seconds']
            diagnostic_start=time.perf_counter()
            training.validate_update(torch,model,opt,values,step+1)
            if any(not torch.isfinite(value) for value in losses.values()):raise ValueError('nonfinite training loss')
            count=runtime['kml_gemm_calls']-calls
            if count!=reference['steps'][step]['kml_calls']:raise ValueError('actual KML calls differ from baseline first5')
            if profile_record['sampled'] and profile_record['kml_markers']!=count:raise ValueError('missing bounded KML markers')
            replay_metrics=[]
            for name,value in losses.items():
                accepted.compare(torch,'baseline_step_'+str(step+1)+'.'+name,
                    torch.tensor(reference['steps'][step]['losses'][name],dtype=torch.float32),value,'tensor',replay_metrics)
            step+=1;cursor+=len(indices);result['completed_updates']=step;result['consumed_frames']=cursor
            cpu36_guard.checkpoint(result['cpu36'],f'after_train_{step}',torch)
            diagnostic_seconds=pre_diagnostic+time.perf_counter()-diagnostic_start
            result['timing']['training_step_seconds']+=elapsed
            result['timing']['diagnostic_seconds']+=diagnostic_seconds
            record=dict(profile=profile_record,profiled_call_wall_seconds=profiled_call_wall,baseline_loss_metrics=replay_metrics,diagnostic_seconds=diagnostic_seconds,step=step,batch_size=len(indices),frame_indices=indices,
                frame_ids=[loaded['train']['frame_ids'][i] for i in indices],masked_elements=int(mask.sum()),
                mask_sha256=hashlib.sha256(mask.numpy().tobytes()).hexdigest(),
                losses={name:value.item() for name,value in losses.items()},loader_seconds=loader_seconds,
                step_seconds=elapsed,rss_before=rss_before,rss_after=rss_after,rss_peak_scope='process_lifetime',
                kml_calls=count,adamw_step=step,cursor=cursor)
            log.write(json.dumps(record)+'\n');log.flush();ledger.confirm(step);records.append(record)
    if step==5:stop='profile_update_cap_5'
    result.update(stop_reason=stop,steps=records,consumed_frames=cursor,elapsed_seconds=time.monotonic()-started)
    result['val_final']=dict(status='NOT_RUN_NO_FORMAL_SPLIT')
    cpu36_guard.checkpoint(result['cpu36'],'final_val',torch)
    if source_identity()!=result['source']:raise ValueError('pilot source changed during execution')
    engineering_data.load_descriptor(args.descriptor,args.descriptor_sha256)
    for items in metadata['units'].values():
        for item in items:
            engineering_data.unchanged(real_data.sha(item['path'])==item['npz_sha256'] and
                real_data.sha(item['sidecar_path'])==item['sidecar_sha256'],'input source changed during execution')
    result['source_and_data_after']='PASS_SAME_FROZEN_IDENTITIES'
    progress=dict(epoch_completed=cursor==frames,epoch_order=order,cursor=cursor,optimizer_updates=step,
                  planned_updates=planned,stop_reason=stop,order_seed=0,
                  order_method='Python_Random_shuffle_once',cursor_unit='frame_offset')
    identity=dict(source=result['source'],data=result['data_identity'],config=result['config'],
                  initialization=result['initialization'])
    checkpoint_start=time.perf_counter()
    result['checkpoint']=training.save_checkpoint(torch,args.output_dir/'checkpoints/final.pt',model,opt,
                                                  identity,progress,result['normalization'])
    cpu36_guard.checkpoint(result['cpu36'],'checkpoint_saved',torch)
    if STOP_REQUESTED:
        result['recovery']=dict(status='NOT_RUN_BUDGET',extra_updates=0)
    else:
        ledger.value['recovery_probe']=dict(status='POSSIBLY_USED_IN_RECOVERY_PROBE',
            frame_ids=loaded['train']['frame_ids'][:min(2,frames)],extra_updates=0)
        ledger.save()
        probe_values=training.batch(torch,loaded['train'],list(range(min(2,frames))),angles)
        result['recovery']=training.verify_restore(torch,result['checkpoint'],model,opt,factory,identity,
            progress,result['normalization'],probe_values,accepted.compare)
        ledger.value['recovery_probe']['status']='RECOVERY_PROBE_CONFIRMED_NO_UPDATE';ledger.save()
        cpu36_guard.checkpoint(result['cpu36'],'restore_verified',torch)
    result['timing']['checkpoint_and_recovery_seconds']=time.perf_counter()-checkpoint_start
    finish_backend(runtime,expected)
    cpu36_guard.checkpoint(result['cpu36'],'publish',torch)
    names=['before_framework','after_framework','after_backend','initialized','initial_val']
    for i in range(1,step+1):names += [f'before_train_{i}',f'after_train_{i}']
    names += ['final_val','checkpoint_saved']+(['restore_verified'] if not STOP_REQUESTED else [])+['publish']
    if result['cpu36']['errors'] or [x['name'] for x in result['cpu36']['checkpoints']]!=names:raise ValueError('missing pilot CPU36 evidence')
    incomplete=stop=='BUDGET_INCOMPLETE' or STOP_REQUESTED or step<planned
    result['status']='INCOMPLETE' if incomplete else 'PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'
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
    if args.batch_size!=64:parser.error('fixed baseline batch64, no accumulation')
    if any((args.output_dir/name).exists() for name in ('result.json','steps.jsonl','checkpoints/final.pt')):
        parser.error('refuse existing pilot outputs')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    signal.signal(signal.SIGTERM,request_stop)
    result=dict(status='STARTED',started_utc=datetime.now(timezone.utc).isoformat(),protocol=profile_contract.PROTOCOL,data_protocol=engineering_data.PROTOCOL,baseline_job='2043445',**engineering_data.FLAGS,
        timing=dict(data_loading_seconds=0.,batch_materialization_seconds=0.,training_step_seconds=0.,diagnostic_seconds=0.,checkpoint_and_recovery_seconds=0.,profiler_outside_step_seconds=0.),
        config=dict(belt='16_adjacent',part='pre',precision='fp32',checkpoint=False,compile=False,hbm=False,
            attention='original_native_SDPA',linear='existing_KML_fp32',batch_size=args.batch_size,
            max_epochs=1,max_updates=5,gradient_accumulation=False,train_seed=0,subset_seed=2026,
            lr=1e-4,betas=[0.9,0.999],eps=1e-8,weight_decay=0.01,threads=36))
    wall_start=time.perf_counter()
    try:code=main(args,result)
    except profile_probe.UnsupportedProfiler as exc:result.update(status='UNSUPPORTED_PROFILER',error=str(exc));code=2
    except profile_probe.ProfileLimit as exc:result.update(status='PROFILE_LIMIT_EXCEEDED',error=str(exc));code=2
    except engineering_data.SourceChanged as exc:result.update(status='SOURCE_CHANGED',error=str(exc));code=2
    except real_data.DataNotReady as exc:result.update(status='DATA_NOT_READY',error=str(exc));code=2
    except Exception as exc:result.update(status='ERROR_RUNTIME_OR_STATE',error=repr(exc),traceback=traceback.format_exc());code=2
    wall=time.perf_counter()-wall_start
    measured=sum(result['timing'].values())
    result['timing'].update(wall_seconds=wall,unattributed_seconds=wall-measured,
        diagnostic_scope='mask/exposure-before-update/CPU-before-and-after/state-validation; other setup/logging in unattributed')
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    write_json(args.output_dir/'result.json',result)
    print(json.dumps({k:result[k] for k in ('status','completed_updates','stop_reason','error') if k in result},indent=2))
    sys.exit(code)
