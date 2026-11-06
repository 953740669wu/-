"""Read all four original phase results; never turn partial execution into A/B."""
import hashlib
import json
import math

PROTOCOL='ENGINEERING_DW_TILES_R12_AB_V1'
TARGET_PROTOCOL='ENGINEERING_DW_TILES_R12_V1'
TARGET_SUCCESS='PASS_ACTUAL_KML_TARGET_ONLY'
STRICT_SUCCESS='PASS_STRICT_ENCODER5'
PERF_SUCCESS='PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE'
SUCCESS='R12_COMPLETE_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE'
IMPORTS=dict(baseline='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26',candidate='8955f1c0bdf8b2b5d233b3eafb321d30ae0dbd184ba595959680434aedafd6ea')
ORDER=('target','strict','perf_baseline','perf_candidate')
STATUSES=(TARGET_SUCCESS,STRICT_SUCCESS,PERF_SUCCESS,PERF_SUCCESS)

def require(ok,message):
    if not ok:raise ValueError(message)

def validate(phases):
    result=dict(complete=False,full_model_updates=0,failure_stage=None,missing=[s for s in ORDER if s not in phases],phase_status={s:p.get('status') for s,p in phases.items()},errors=[])
    try:
        for i,name in enumerate(ORDER):
            app=phases.get(name)
            if app is None or app.get('status')!=STATUSES[i]:
                result['failure_stage']=name
                require(not any(s in phases for s in ORDER[i+1:]),'later phase exists after missing/failed '+name)
                return result
            target=phases['target']
            require(app['protocol']==(TARGET_PROTOCOL if name=='target' else PROTOCOL),'phase protocol mismatch')
            require(all(app[k]==target[k] for k in ('source_manifest_sha256','host','job_id')),'source/host/job mismatch')
            cpu=app['cpu36'];require(cpu['errors']==[] and len(cpu['receipt']['selected'])==36 and cpu['receipt']['selected']==target['cpu36']['receipt']['selected'],'actual selected36 differs')
            runtime=app['runtime'];require(runtime['backend']=='kml' and runtime['libraries']==runtime['libraries_after']==target['runtime']['libraries'],'KML/library identity mismatch')
            require(all(runtime.get(k)==target['runtime'].get(k) for k in ('torch','torch_file','numpy','numpy_file','env')),'framework/environment drift')
            require(all(app['imports'][r]['sha256']==h for r,h in IMPORTS.items()),'actual baseline/candidate import identity mismatch')
            require(app.get('metrics') and all(m.get('passed') is True for m in app['metrics']),'original comparison failed/missing')
            if name=='target':
                for role,count,full,tiles in [('baseline',1,1,0),('candidate',2,0,2)]:
                    native=app['native'][role]
                    require((native['native_calls'],native['target_full'],native['target_tiles'])==(count,full,tiles) and native['original_type']=='_FuncPtr','actual target native ABI counts missing')
                continue
            strict=name=='strict';count=5 if strict else 25;roles=['baseline','candidate'] if strict else [name[5:]]
            require(app['engineering_only'] is True and app['phase']==('strict' if strict else 'perf') and app['variant']==(None if strict else roles[0]),'phase/variant mismatch')
            require(app['completed_updates']==app['planned_updates']==count and app['consumed_frames']==count*64,'required update count/frames incomplete')
            require(app['descriptor_sha256']==phases['strict']['descriptor_sha256'] and app['normalization']==phases['strict']['normalization'],'descriptor/scale mismatch')
            steps=app['steps'];require(len(steps)==count*len(roles)==app['optimizer_updates_total'],'step record count mismatch')
            for role in roles:
                require(app['initialization'][role]==phases['strict']['initialization']['baseline'],'same full model initialization required')
            for step in range(1,count+1):
                rows=steps[(step-1)*len(roles):step*len(roles)]
                for role,row in zip(roles,rows):
                    require(row['role']==role and row['step']==row['adamw_step']==step and row['batch_size']==64,'step/role/AdamW continuity mismatch')
                    require(len(row['frame_indices'])==len(row['frame_ids'])==64 and all(math.isfinite(v) for v in row['losses'].values()),'batch/nonfinite loss')
                    require(row['sampled']==(not strict and step>=6),'warmup/observe phase mismatch')
                    expected=(149,149,12,12,0,0) if role=='baseline' else (149,161,12,0,24,12)
                    require(tuple(row[k] for k in ('kml_calls','native_sgemm_calls','target_logical_gemm','target_native_full','target_native_tiles','dispatch_hits'))==expected,'logical/native/target/dispatch counts differ')
                    if strict:
                        ref=rows[0]
                    else:
                        ref=phases['perf_baseline']['steps'][step-1]
                    require(all(row[k]==ref[k] for k in ('frame_indices','frame_ids','mask_sha256')),'paired frame/mask mismatch')
                if not strict and step<=5:
                    ref=phases['strict']['steps'][(step-1)*2]
                    require(all(rows[0][k]==ref[k] for k in ('frame_indices','frame_ids','mask_sha256')),'strict/performance first5 identity mismatch')
            for role in roles:
                indices=[n for row in steps if row['role']==role for n in row['frame_indices']]
                require(len(indices)==len(set(indices))==count*64,'padding/repeated frame indices')
            if not strict:
                recovery=app['recovery'];require(recovery['status']=='PASS_NO_EXTRA_UPDATE' and recovery['extra_updates']==0,'zero-update restore missing')
                require(all(recovery.get(k) is True for k in ('parameters_exact','optimizer_exact','rng_exact','cursor_exact','identity_exact')) and app['checkpoint']['sha256'],'restore state/checkpoint missing')
            result['full_model_updates']+=len(steps)
        require(result['full_model_updates']==60,'maximum/exact complete chain60 updates required')
        result['complete']=True
    except (ValueError,KeyError,TypeError) as exc:result['errors'].append(repr(exc))
    return result

def inspect(root,job):
    paths=dict(target=root/'payload/outputs'/('target_'+str(job))/'screen_result.json')
    for phase in ORDER[1:]:paths[phase]=root/'payload/outputs'/(phase+'_'+str(job))/'result.json'
    phases={};errors=[]
    for name,path in paths.items():
        if path.is_file():
            try:phases[name]=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError) as exc:errors.append(name+': '+repr(exc))
    result=validate(phases)
    try:
        for name,app in phases.items():
            if name=='target':continue
            steps=paths[name].parent/'steps.jsonl'
            if app.get('status') in (STRICT_SUCCESS,PERF_SUCCESS):
                require([json.loads(line) for line in steps.read_text(encoding='utf-8').splitlines()]==app['steps'],'result/step log mismatch '+name)
                ledger=json.loads((paths[name].parent/'EXPOSURE_LEDGER.json').read_text(encoding='utf-8'))
                count=5 if name=='strict' else 25
                require(ledger['in_flight'] is None and len(ledger['confirmed_updates'])==count,'incomplete exposure ledger '+name)
                if name=='strict':require(app['target_screen_sha256']==hashlib.sha256(paths['target'].read_bytes()).hexdigest(),'target receipt SHA mismatch')
                else:
                    argv=app['argv'];require(argv[argv.index('--strict-receipt-sha256')+1]==hashlib.sha256(paths['strict'].read_bytes()).hexdigest(),'strict receipt SHA mismatch')
    except (OSError,ValueError,KeyError,TypeError) as exc:errors.append(repr(exc))
    result['errors'].extend(errors)
    if errors:result['complete']=False
    return result
