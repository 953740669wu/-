"""Read-only PROFILE5 completion evidence; preserve unsupported/limit/failure states."""
import hashlib
import json

PROTOCOL='ENGINEERING_REAL_CORPUS_PROFILE5_V1'
SUCCESS='PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'
PHASES=('zero_grad_before','forward_loss','zero_grad_after','backward','optimizer')


def inspect(root,job):
    run=root/'payload/outputs'/('profile_'+str(job))
    result=dict(application_status=None,profile5_complete=False,errors=[],missing_outputs=[],captures=[])
    names=['result.json','steps.jsonl','EXPOSURE_LEDGER.json']
    names += [prefix+'_step_'+str(i)+'.json' for prefix in ('trace','events') for i in (3,4,5)]
    result['missing_outputs']=[n for n in names if not (run/n).is_file()]
    try:
        app=json.loads((run/'result.json').read_text(encoding='utf-8'))
        result.update(application_status=app.get('status'),application_error=app.get('error'))
        if app.get('status')!=SUCCESS:return result
        def require(ok,message):
            if not ok:raise ValueError(message)
        require(app.get('protocol')==PROTOCOL and app.get('engineering_only') is True,'new PROFILE5 protocol required')
        require(app.get('completed_updates')==app.get('planned_updates')==5 and app.get('consumed_frames')==320,'five updates/320 frames required')
        recovery=app.get('recovery',{})
        require(recovery.get('status')=='PASS_NO_EXTRA_UPDATE' and recovery.get('extra_updates')==0,'restore/no-extra-update evidence missing')
        for key in ('parameters_exact','optimizer_exact','rng_exact','cursor_exact','identity_exact'):
            require(recovery.get(key) is True,'recovery state missing: '+key)
        require(app.get('source_and_data_after')=='PASS_SAME_FROZEN_IDENTITIES','final source/data evidence missing')
        require(app.get('cpu36',{}).get('errors')==[] and len(app.get('cpu36',{}).get('checkpoints',[]))==19,'19 original CPU checkpoints required')
        require(app.get('runtime',{}).get('kml_gemm_calls',0)>0 and app.get('checkpoint',{}).get('sha256'),'KML/checkpoint identity missing')
        steps=[json.loads(x) for x in (run/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
        require(len(steps)==5,'exactly five step records required')
        require(len(list(run.glob('trace_step_*.json')))==len(list(run.glob('events_step_*.json')))==3,'exactly three traces/events required')
        require(not result['missing_outputs'],'required output missing')
        for i,step in enumerate(steps,1):
            require(step.get('step')==step.get('adamw_step')==i and step.get('cursor')==i*64 and step.get('batch_size')==64,'continuous state/B64 required')
            metrics=step.get('baseline_loss_metrics',[])
            require(len(metrics)==3 and all(x.get('passed') is True for x in metrics),'original three loss comparisons required')
            profile=step['profile'];sampled=i>=3
            require(profile.get('sampled') is sampled and profile.get('step')==i,'warmup/sample order changed')
            require(profile.get('status')==('CAPTURED' if sampled else 'WARMUP_NO_CPU_CAPTURE'),'capture status missing')
            if not sampled:continue
            count=profile.get('events',0);markers=profile.get('kml_markers',0)
            require(0<count<=50000 and 0<markers<=256 and markers==step.get('kml_calls'),'event/KML count limit or identity mismatch')
            capture=dict(step=i,events=count,kml_markers=markers)
            objects={}
            for key,prefix,limit in [('trace','trace',8388608),('summary','events',1048576)]:
                path=run/(prefix+'_step_'+str(i)+'.json');size=path.stat().st_size
                require(size<=limit,'raw output exceeds byte limit: '+path.name)
                raw=path.read_bytes();asset=profile[key]
                require(asset['bytes']==size and asset['sha256']==hashlib.sha256(raw).hexdigest(),'profile output SHA/bytes mismatch')
                objects[key]=json.loads(raw);capture[key]=dict(bytes=size,sha256=asset['sha256'])
            events=objects['trace']['traceEvents'];event_names=[x['name'] for x in events]
            require(len(events)==count and all('S02/'+n in event_names for n in PHASES),'required phase events missing')
            require(event_names.count('S02/KML_python_gemm_envelope')==markers,'KML envelope events missing')
            summary=objects['summary']
            require(summary['events']==count and len(summary['top_self_cpu'])<=80,'event summary identity/limit mismatch')
            result['captures'].append(capture)
        result['profile5_complete']=True
    except (OSError,ValueError,KeyError,TypeError) as exc:result['errors'].append(repr(exc))
    return result
