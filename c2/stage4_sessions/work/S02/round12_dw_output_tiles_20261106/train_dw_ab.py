"""Proposed NEW same-node gate then isolated baseline/candidate perf; no profiler."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import signal
import sys
import time
import traceback
import cpu36_guard
from diagnostic_common import configure_backend,finish_backend
from data_gate import engineering_data as data
import engineering_training as training
import memory_metrics
import profile_contract
from runtime_counts import source_identity,attach_native,verify_step,TARGET_KEY

ROOT=Path(__file__).resolve().parent
STOP=False


def stop(_sig,_frame):
    global STOP
    STOP=True


def check_receipt(receipt,source,descriptor,host,job,cpus):
    if receipt.get('status')!='PASS_STRICT_ENCODER5' or receipt.get('phase')!='strict' or receipt.get('completed_updates')!=5:
        raise ValueError('new complete full-encoder strict5 receipt required before perf')
    expected=dict(source_manifest_sha256=source,descriptor_sha256=descriptor,host=host,job_id=job)
    if any(receipt.get(k)!=v for k,v in expected.items()):raise ValueError('strict receipt source/data/node/job differs')
    if receipt.get('cpu36',{}).get('receipt',{}).get('selected')!=cpus:raise ValueError('strict receipt selected36 differs')


def compare_models(torch,accepted,left,right,opts,initial,metrics,prefix):
    a=dict(left.named_parameters());b=dict(right.named_parameters())
    if set(a)!=set(b):raise ValueError('model parameter keys differ')
    for name,p in a.items():
        q=b[name]
        for key,x,y in [('grad',p.grad,q.grad),('param',p.detach(),q.detach()),
                        ('delta',p.detach()-initial[name],q.detach()-initial[name])]:
            accepted.compare(torch,prefix+key+'.'+name,x,y,'tensor',metrics)
        sa,sb=opts[0].state[p],opts[1].state[q]
        if set(sa)!=set(sb) or set(sa)!={'step','exp_avg','exp_avg_sq'}:raise ValueError('optimizer keys differ')
        for key,value in sa.items():accepted.compare(torch,prefix+'state.'+name+'.'+key,value,sb[key],
                                                   'exact' if key=='step' else 'state',metrics)
    aa,bb=left.state_dict(),right.state_dict()
    if set(aa)!=set(bb):raise ValueError('model state keys differ')
    for name in set(aa)-set(a):accepted.compare(torch,prefix+'buffer.'+name,aa[name],bb[name],'tensor',metrics)


def main(args,result):
    started=time.perf_counter();source=source_identity()
    result.update(source_manifest_sha256=source,descriptor_sha256=args.descriptor_sha256,
                  host=platform.node(),job_id=os.environ.get('CCS_JOB_ID'),phase=args.phase)
    if ROOT.name!='payload' or ROOT.parent.parent!=Path('/home/share/dengqingtian/opt/stage4_sessions/S00') or not ROOT.parent.name.startswith('S02_DW_R12_'):
        raise ValueError('new reviewed S00/S02_DW_R12_*/payload required')
    if result['job_id'] in (None,'2043445','2048959','2049454'):raise ValueError('new reviewed job required; old authorization consumed')
    if args.output_dir.resolve().parent!=ROOT/'outputs':raise ValueError('fresh owned payload outputs directory required')
    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())
    epoch_reference=json.loads((ROOT/'REFERENCE_EPOCH25.json').read_text())
    planned=5 if args.phase=='strict' else 25
    result['planned_updates']=planned
    result['warmup_updates']=0 if args.phase=='strict' else 5
    if args.descriptor_sha256!=reference['descriptor_sha256']:raise ValueError('same original descriptor bytes required')
    if args.phase=='strict':
        if not args.target_screen or data.sha(args.target_screen)!=args.target_screen_sha256:raise ValueError('actual KML target screen receipt/SHA required')
        prior=json.loads(args.target_screen.read_text())
        if prior.get('status')!='PASS_ACTUAL_KML_TARGET_ONLY' or any(prior.get(k)!=result[k] for k in ('source_manifest_sha256','host','job_id')):
            raise ValueError('target screen source/node/job differs or failed')
        if prior.get('cpu36',{}).get('receipt',{}).get('selected')!=[int(v) for v in args.expected_cpus.split(',')]:raise ValueError('target screen CPUs differ')
        result['target_screen_sha256']=args.target_screen_sha256
    if args.phase=='perf':
        if not args.strict_receipt or data.sha(args.strict_receipt)!=args.strict_receipt_sha256:raise ValueError('strict receipt SHA missing/different')
        prior=json.loads(args.strict_receipt.read_text())
        check_receipt(prior,source,args.descriptor_sha256,result['host'],result['job_id'],
                      [int(v) for v in args.expected_cpus.split(',')])
    metadata=data.load_descriptor(args.descriptor,args.descriptor_sha256);profile_contract.check_data(metadata['description'],reference)
    ledger=data.Exposure(args.output_dir/'EXPOSURE_LEDGER.json',metadata['description'])
    result['cpu36']={};cpus=[int(v) for v in args.expected_cpus.split(',')]
    cpu36_guard.prepare(cpus,args.cpu_contract,result['cpu36'])
    import numpy as np
    import torch
    cpu36_guard.checkpoint(result['cpu36'],'after_framework',torch)
    # Load candidate before patch_linear so its tiny/native fallback is the original F.linear.
    spec=importlib.util.spec_from_file_location('s02_r12_candidate_kml',ROOT/'candidate/kml_ops.py')
    candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    runtime,expected=configure_backend(torch,'kml',cpus);result['runtime']=runtime
    if runtime['libraries']!=prior['runtime']['libraries'] or any(runtime.get(k)!=prior['runtime'].get(k) for k in ('torch','torch_file','numpy','numpy_file','env')):
        raise ValueError('same-job library/framework/environment drift')
    baseline=sys.modules['kml_ops'];modules=dict(baseline=baseline,candidate=candidate)
    native_states={role:attach_native(module) for role,module in modules.items()};result['native_counts']=native_states
    original=candidate.gemm
    def counted(a,b,*args,**kwargs):
        runtime['kml_gemm_calls']+=1
        key=str((list(a.shape),list(b.shape),args,kwargs.get('ta',False),kwargs.get('tb',False)))
        runtime['kml_shapes'][key]=runtime['kml_shapes'].get(key,0)+1
        return original(a,b,*args,**kwargs)
    candidate.gemm=counted
    result['imports']={role:dict(path=str(Path(m.__file__).resolve()),sha256=data.sha(m.__file__),
                                linear_dtype=str(m.LINEAR_DTYPE),actual_kml=m._lib is not None) for role,m in modules.items()}
    if not all(m._lib is not None and m.LINEAR_DTYPE==torch.float32 for m in modules.values()):raise ValueError('actual fp32 KML only')
    cpu36_guard.checkpoint(result['cpu36'],'after_backend',torch)
    tick=time.perf_counter();loaded=data.load_arrays(metadata,ledger)
    result['data_loading_seconds']=time.perf_counter()-tick
    if len(loaded['train']['v'])!=1600:raise ValueError('same1600 frames required')
    normalization=dict(image_scale=loaded['image_scale'],scope=loaded['normalization_scope'],fit_partition='train',
                       train_units=[x['unit'] for x in metadata['units']['train']])
    if normalization!=reference['normalization']:raise ValueError('normalization differs')
    result['normalization']=normalization
    sys.path.insert(0,str(ROOT/'tests'));import check_equivalence as accepted
    definitions=accepted.model_definitions(torch);factory=definitions['Encoder'];angles=definitions['protocol_angles'](16,1)
    roles=['baseline','candidate'] if args.phase=='strict' else [args.variant];models={};opts={};initial=None
    result['initialization']={}
    for role in roles:
        torch.manual_seed(0);np.random.seed(0);random.seed(0)
        models[role]=factory();opts[role]=training.optimizer(torch,models[role])
        digest=training.model_sha(models[role])
        result['initialization'][role]=dict(initial_weights_sha256=digest,parameters=sum(p.numel() for p in models[role].parameters()),train_seed=0)
        if result['initialization'][role]['parameters']!=37995777 or digest!=reference['initialization']['initial_weights_sha256']:
            raise ValueError('full encoder/init differs')
    if args.phase=='strict':initial={n:p.detach().clone() for n,p in models['baseline'].named_parameters()}
    order=list(range(1600));random.Random(0).shuffle(order);result['steps']=[];result['metrics']=[]
    result['completed_updates']=0;result['consumed_frames']=0
    result['pre_update_evidence_seconds']=0.
    with (args.output_dir/'steps.jsonl').open('x') as log:
        for step in range(1,planned+1):
            if STOP or time.perf_counter()-started>=720:raise TimeoutError('stop new update; no retry')
            evidence_start=time.perf_counter()
            indices=order[(step-1)*64:step*64];mask=torch.rand(64,208)<.5
            frame_ids=[loaded['train']['frame_ids'][i] for i in indices]
            mask_sha=__import__('hashlib').sha256(mask.numpy().tobytes()).hexdigest()
            if step<=5:profile_contract.check_step_identity(step,indices,profile_contract.identity(frame_ids),mask_sha,reference)
            expected_frame=epoch_reference['steps'][step-1]
            if indices!=expected_frame['frame_indices'] or profile_contract.identity(frame_ids)!=expected_frame['frame_ids_sha256'] or mask_sha!=expected_frame['mask_sha256']:
                raise ValueError('epoch frame/order/mask identity drift')
            ledger.attempt(step,indices,frame_ids);captures={};values_by_role={};losses_by_role={};records=[]
            result['pre_update_evidence_seconds']+=time.perf_counter()-evidence_start
            for role in roles:
                modules[role].patch_linear();model=models[role];handles=[];captures[role]={}
                if args.phase=='strict':
                    def capture(key,store):
                        def hook(_module,_args,output):store[key]=output.detach().clone()
                        return hook
                    for key,module in [('h',model),('v',model.head_v),('coarse',model.head_coarse)]:
                        handles.append(module.register_forward_hook(capture(key,captures[role])))
                tick=time.perf_counter();values=training.batch(torch,loaded['train'],indices,angles);loader=time.perf_counter()-tick
                diagnostic_start=time.perf_counter();cpu36_guard.checkpoint(result['cpu36'],f'before_{role}_{step}',torch)
                rss_before=memory_metrics.rss();calls=runtime['kml_gemm_calls'];logical_target=runtime['kml_shapes'].get(TARGET_KEY,0)
                native_before={k:native_states[role][k] for k in ('native_calls','target_full','target_tiles')}
                pre_diag=time.perf_counter()-diagnostic_start
                tick=time.perf_counter()
                try:losses=training.train_step(torch,model,opts[role],values,mask)
                finally:
                    for handle in handles:handle.remove()
                elapsed=time.perf_counter()-tick;rss_after=memory_metrics.rss();tick=time.perf_counter()
                training.validate_update(torch,model,opts[role],values,step)
                actual_calls=runtime['kml_gemm_calls']-calls
                native_delta={k:native_states[role][k]-native_before[k] for k in native_before}
                target_delta=runtime['kml_shapes'].get(TARGET_KEY,0)-logical_target
                verify_step(role,actual_calls,target_delta,native_delta['native_calls'],native_delta['target_full'],native_delta['target_tiles'])
                if step<=5:
                    for key,value in losses.items():accepted.compare(torch,f'{role}.{step}.baseline_loss.{key}',
                        torch.tensor(reference['steps'][step-1]['losses'][key],dtype=torch.float32),value,'tensor',result['metrics'])
                elif any(not torch.isfinite(value) for value in losses.values()):raise ValueError('nonfinite epoch loss')
                cpu36_guard.checkpoint(result['cpu36'],f'after_{role}_{step}',torch)
                diagnostic_seconds=pre_diag+time.perf_counter()-tick
                values_by_role[role]=values;losses_by_role[role]=losses
                records.append(dict(role=role,step=step,batch_size=64,frame_indices=indices,frame_ids=frame_ids,mask_sha256=mask_sha,
                    losses={k:v.item() for k,v in losses.items()},step_seconds=elapsed,loader_seconds=loader,
                    diagnostic_seconds=diagnostic_seconds,rss_before=rss_before,rss_after=rss_after,rss_peak_scope='process_lifetime',
                    kml_calls=actual_calls,native_sgemm_calls=native_delta['native_calls'],target_logical_gemm=target_delta,
                    target_native_full=native_delta['target_full'],target_native_tiles=native_delta['target_tiles'],dispatch_hits=native_delta['target_tiles']//2,
                    adamw_step=step,sampled=args.phase=='perf' and step>=6,timing_scope='strict gate hooks included; perf mode has no hooks/profiler'))
            if args.phase=='strict':
                tick=time.perf_counter()
                for key in captures['baseline']:accepted.compare(torch,f'{step}.output.{key}',captures['baseline'][key],captures['candidate'][key],'tensor',result['metrics'])
                for key in losses_by_role['baseline']:accepted.compare(torch,f'{step}.loss.{key}',losses_by_role['baseline'][key],losses_by_role['candidate'][key],'tensor',result['metrics'])
                for i in (0,1):accepted.compare(torch,f'{step}.input_grad.{i}',values_by_role['baseline'][i].grad,values_by_role['candidate'][i].grad,'tensor',result['metrics'])
                compare_models(torch,accepted,models['baseline'],models['candidate'],[opts['baseline'],opts['candidate']],initial,result['metrics'],str(step)+'.')
                result['strict_comparison_seconds']=result.get('strict_comparison_seconds',0.)+time.perf_counter()-tick
            for record in records:log.write(json.dumps(record)+'\n');result['steps'].append(record)
            log.flush();ledger.confirm(step);result['completed_updates']=step;result['consumed_frames']=step*64
    if args.phase=='perf':
        role=args.variant;modules[role].patch_linear();progress=dict(epoch_order=order,cursor=1600,optimizer_updates=25,planned_updates=25,epoch_completed=True)
        tick=time.perf_counter();identity=dict(source_manifest_sha256=source,data=metadata['identity'],variant=role,imports=result['imports'])
        result['checkpoint']=training.save_checkpoint(torch,args.output_dir/'checkpoints/final.pt',models[role],opts[role],identity,progress,normalization)
        ledger.value['recovery_probe']=dict(status='POSSIBLY_USED_IN_RECOVERY_PROBE',frame_ids=loaded['train']['frame_ids'][:2]);ledger.save()
        result['recovery']=training.verify_restore(torch,result['checkpoint'],models[role],opts[role],factory,identity,progress,normalization,
            training.batch(torch,loaded['train'],[0,1],angles),accepted.compare)
        ledger.value['recovery_probe']['status']='RECOVERY_PROBE_CONFIRMED_NO_UPDATE';ledger.save()
        result['checkpoint_recovery_seconds']=time.perf_counter()-tick
    data.load_descriptor(args.descriptor,args.descriptor_sha256)
    if source_identity()!=source:raise ValueError('source changed during run')
    finish_backend(runtime,expected);cpu36_guard.checkpoint(result['cpu36'],'publish',torch)
    if result['cpu36']['errors']:raise ValueError('CPU36 failed')
    result.update(status='PASS_STRICT_ENCODER5' if args.phase=='strict' else 'PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE',
                  wall_seconds=time.perf_counter()-started)
    result['optimizer_updates_total']=len(result['steps'])
    result['timing']=dict(wall_seconds=result['wall_seconds'],data_loading_seconds=result['data_loading_seconds'],
        training_step_seconds=sum(r['step_seconds'] for r in result['steps']),
        batch_materialization_seconds=sum(r['loader_seconds'] for r in result['steps']),
        diagnostic_seconds=sum(r['diagnostic_seconds'] for r in result['steps']),
        mask_and_attempt_ledger_seconds=result['pre_update_evidence_seconds'],
        strict_comparison_seconds=result.get('strict_comparison_seconds',0.),
        checkpoint_recovery_seconds=result.get('checkpoint_recovery_seconds',0.))
    result['timing']['unattributed_seconds']=result['wall_seconds']-sum(v for k,v in result['timing'].items() if k!='wall_seconds')
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=['strict','perf'],required=True)
    p.add_argument('--variant',choices=['baseline','candidate']);p.add_argument('--descriptor',type=Path,required=True)
    p.add_argument('--descriptor-sha256',required=True);p.add_argument('--expected-cpus',required=True)
    p.add_argument('--cpu-contract',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--target-screen',type=Path);p.add_argument('--target-screen-sha256');
    p.add_argument('--strict-receipt',type=Path);p.add_argument('--strict-receipt-sha256');a=p.parse_args()
    if a.phase=='perf' and not a.variant:p.error('perf requires variant')
    a.output_dir.mkdir(parents=True,exist_ok=False);signal.signal(signal.SIGTERM,stop)
    result=dict(status='STARTED',pid=os.getpid(),argv=list(sys.argv),protocol='ENGINEERING_DW_TILES_R12_AB_V1',engineering_only=True,formal_split_status='UNKNOWN',
                subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',variant=a.variant,new_jobs=0)
    try:code=main(a,result)
    except TimeoutError as exc:result.update(status='INCOMPLETE_STOP_NO_RETRY',error=repr(exc),traceback=traceback.format_exc());code=3
    except Exception as exc:result.update(status='FAIL_STOP_NO_RETRY',error=repr(exc),traceback=traceback.format_exc());code=2
    (a.output_dir/'result.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(code)
