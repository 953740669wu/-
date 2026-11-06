"""Read scalar GEMM5 evidence only; never mutate, truncate or replay an operation."""
import hashlib
import json
import math

PROTOCOL='ENGINEERING_REAL_CORPUS_GEMM5_V1'
SUCCESS='GEMM5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'
BASELINE='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'


def inspect(root,job):
    run=root/'payload/outputs'/('gemm_'+str(job))
    output=dict(application_status=None,gemm5_complete=False,errors=[],missing_outputs=[],samples=[])
    required=['result.json','steps.jsonl','EXPOSURE_LEDGER.json']+['gemm_step_'+str(i)+'.json' for i in (3,4,5)]
    output['missing_outputs']=[n for n in required if not (run/n).is_file()]
    try:
        app=json.loads((run/'result.json').read_text(encoding='utf-8'))
        output.update(application_status=app.get('status'),application_error=app.get('error'))
        if app.get('status')!=SUCCESS:return output
        def require(ok,message):
            if not ok:raise ValueError(message)
        require(app.get('protocol')==PROTOCOL and app.get('engineering_only') is True,'new GEMM5 protocol required')
        require(app.get('completed_updates')==app.get('planned_updates')==5 and app.get('consumed_frames')==320,'exactly five updates/320 frames required')
        recovery=app.get('recovery',{})
        require(recovery.get('status')=='PASS_NO_EXTRA_UPDATE' and recovery.get('extra_updates')==0,'restore evidence missing')
        require(all(recovery.get(k) is True for k in ('parameters_exact','optimizer_exact','rng_exact','cursor_exact','identity_exact')),'recovery state mismatch')
        require(app.get('source_and_data_after')=='PASS_SAME_FROZEN_IDENTITIES','final source gate missing')
        require(app.get('cpu36',{}).get('errors')==[] and len(app.get('cpu36',{}).get('checkpoints',[]))==19,'19 CPU checkpoints required')
        require(app.get('runtime',{}).get('kml_gemm_calls',0)>0 and app.get('checkpoint',{}).get('sha256'),'KML/checkpoint missing')
        observation=app['gemm_observation']
        require(observation['baseline_kml_sha256']==observation['baseline_import']['sha256']==BASELINE,'unmodified baseline import required; R10 forbidden')
        samples=observation['samples'];require([s['step'] for s in samples]==[3,4,5] and observation['detailed_steps']==[3,4,5],'three detailed samples required')
        steps=[json.loads(x) for x in (run/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
        require(len(steps)==5 and not output['missing_outputs'],'missing five-step/ledger evidence')
        require(len(list(run.glob('gemm_step_*.json')))==3,'exactly three detail files required')
        require(not list(run.glob('trace_step_*.json')) and not list(run.glob('events_step_*.json')),'R9 profiler captures are outside GEMM5 scope')
        for step,item in enumerate(steps,1):
            require(item['step']==item['adamw_step']==step and item['cursor']==64*step and item['batch_size']==64,'step/B64 continuity mismatch')
            require(item['kml_calls']==149,'original149 calls per update required')
            metrics=item.get('baseline_loss_metrics',[])
            require(len(metrics)==3 and all(m.get('passed') is True for m in metrics),'original loss gate missing')
            if step<=2:
                require(item.get('gemm_sample') is None,'warmup must not record detail');continue
            sample=samples[step-3]
            require(item['gemm_sample']==sample and sample['status']=='COMPLETE' and sample['records']==sample['native_calls']==149,'native/outer sample summary mismatch')
            path=run/('gemm_step_'+str(step)+'.json');size=path.stat().st_size
            require(size<=1048576,'detail exceeds1MiB; do not truncate')
            raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
            require(sample['bytes']==size and sample['sha256']==digest,'detail bytes/SHA mismatch')
            body=json.loads(raw)
            require(body['protocol']==PROTOCOL and body['step']==step and body['status']=='COMPLETE' and body['records']==149,'detail identity/status mismatch')
            calls=body['calls'];require(len(calls)==149 and len(calls)<=256,'record cap/count mismatch')
            require([c['call_index'] for c in calls]==list(range(1,150)),'missing/duplicate call sequence')
            by_index={c['call_index']:c for c in calls}
            for call in calls:
                require(call['step']==step and call['status']=='COMPLETE' and call['native_calls']==1,'GEMM must pair with one native call')
                require(type(call['thread_id']) is int and call['thread_id']>0,'missing thread identity')
                require(type(call['ta']) is bool and type(call['tb']) is bool and math.isfinite(call['beta']),'invalid transpose/beta metadata')
                for name in ('a','b','output'):
                    tensor=call[name]
                    require(len(tensor['shape'])==len(tensor['stride'])==2 and all(type(x) is int and x>0 for x in tensor['shape']) and all(type(x) is int and x>=0 for x in tensor['stride']),'invalid scalar tensor metadata')
                    require(tensor['dtype'] in ('torch.float32','float32') and tensor['contiguous'] is True,'original contiguous fp32 operands/output required')
                a,b=call['a']['shape'],call['b']['shape'];m,k=(a[1],a[0]) if call['ta'] else a;n=b[0] if call['tb'] else b[1]
                require(k==(b[1] if call['tb'] else b[0]) and [call['m'],call['n'],call['k']]==[m,n,k] and call['output']['shape']==[m,n],'actual m/n/k/output differs from shape/flags')
                for name in ('aliases_a_storage','aliases_b_storage','is_given_out'):require(type(call['output'][name]) is bool,'output alias metadata missing')
                native=dict(layout=101,transa=112 if call['ta'] else 111,transb=112 if call['tb'] else 111,m=m,n=n,k=k,
                    alpha=1.,lda=a[1],ldb=b[1],beta=call['beta'] if call['output']['is_given_out'] else 0.,ldc=n)
                require(call['sgemm']==native and call['ctypes_thread_id']==call['thread_id'],'actual native arguments/thread differ from outer contract')
                require(call['role'] in ('forward','dX','dW','UNKNOWN'),'unknown role label')
                if call['role']!='UNKNOWN':
                    context,ta,tb={'forward':('forward',False,True),'dX':('backward',False,False),'dW':('backward',True,False)}[call['role']]
                    require((call['linear_context'],call['ta'],call['tb'])==(context,ta,tb),'role not confirmed by context/flags')
                gs,ge,cs,ce=[call[k] for k in ('gemm_start_ns','gemm_end_ns','ctypes_start_ns','ctypes_end_ns')]
                require(all(type(x) is int for x in (gs,ge,cs,ce)) and gs<=cs<=ce<=ge,'same-call native/outer intervals do not nest')
                require(call['gemm_wall_ns']==ge-gs and call['ctypes_wall_ns']==ce-cs and call['outer_minus_ctypes_ns']==(ge-gs)-(ce-cs),'duration/difference metadata mismatch')
                require(all(type(call[k]) is int and call[k]>=0 for k in ('observer_before_ns','observer_after_ns','observer_sgemm_bookkeeping_ns')),'observer bookkeeping evidence missing')
                parent=call['parent_call_index']
                if parent is not None:
                    require(parent in by_index and parent<call['call_index'],'invalid parent sequence')
                    p=by_index[parent];require(p['thread_id']==call['thread_id'] and p['gemm_start_ns']<=gs<=ge<=p['gemm_end_ns'],'parent/thread interval mismatch')
            output['samples'].append(dict(step=step,records=len(calls),native_calls=sum(c['native_calls'] for c in calls),bytes=size,sha256=digest,thread_ids=sorted({c['thread_id'] for c in calls})))
        output['gemm5_complete']=True
    except (OSError,ValueError,KeyError,TypeError) as exc:output['errors'].append(repr(exc))
    return output
