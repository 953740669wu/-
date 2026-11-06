"""Narrow changes to a copy of the frozen real engineering entry."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'train_engineering.py').read_text()
s=s.replace('import real_data\n','import real_data\nimport profile_probe\nimport profile_contract\n')
s=s.replace('import random\n','import os\nimport random\n')
s=s.replace("    ledger=engineering_data.Exposure(metadata['description']['runtime_exposure_ledger_path'],metadata['description'])", """    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())
    if args.descriptor_sha256!=reference['descriptor_sha256']:raise ValueError('exact baseline descriptor bytes required')
    profile_contract.check_data(metadata['description'],reference)
    if ROOT.name!='payload' or not ROOT.parent.name.startswith('S02_PROFILE5_') or ROOT.parent.parent!=Path('/home/share/dengqingtian/opt/stage4_sessions/S00'):
        raise ValueError('new S00/S02_PROFILE5_*/payload required; never reuse baseline deployment')
    if args.output_dir.resolve().parent!=ROOT/'outputs' or args.output_dir.name!='profile_'+os.environ.get('CCS_JOB_ID',''):
        raise ValueError('new owned profile job output path required')
    ledger=engineering_data.Exposure(args.output_dir/'EXPOSURE_LEDGER.json',metadata['description'])
    result['exposure_path_policy']='profile ledger in fresh job outputs; original descriptor runtime ledger is read-only and NOT USED as output'""")
s=s.replace("    cpu36_guard.checkpoint(result['cpu36'],'after_backend',torch)","""    cpu36_guard.checkpoint(result['cpu36'],'after_backend',torch)
    import kml_ops
    probe=profile_probe.Probe(torch,args.output_dir,kml_ops)
    result['profiling']=dict(warmup_updates=[1,2],sampled_updates=[3,4,5],updates=probe.records,
        activity='CPU',record_shapes=False,profile_memory=False,with_stack=False,with_flops=False,
        event_limit_per_sample=profile_probe.MAX_EVENTS,kml_markers_per_sample=profile_probe.MAX_KML_MARKERS,
        trace_limit_per_sample_bytes=profile_probe.TRACE_BYTES,summary_limit_per_sample_bytes=profile_probe.SUMMARY_BYTES,
        maximum_traces=3,maximum_summaries=3,
        overhead_scope='setup/start/stop/postprocess/export separately measured; event/marker overhead inside instrumented steps is UNKNOWN without matched unprofiled control; no throughput acceptance',
        trace_scope='CPU spans including nested events; do not sum inclusive totals or compare CPU time to wall as a percentage',
        kml_scope='Python GEMM envelope, not precise native kernel duration')""")
s=s.replace("    real_data.require(frames>args.batch_size,'pilot needs multiple real batches; never duplicate/pad frames')", "    real_data.require(frames==1600 and args.batch_size==64,'same1600 frames/B64 required; no padding or scope changes')")
s=s.replace("    opt=training.optimizer(torch,model);angles=definitions['protocol_angles'](16,1)","    opt=training.optimizer(torch,model);angles=definitions['protocol_angles'](16,1)")
s=s.replace("    order=list(range(frames));", "    if result['initialization']!=reference['initialization'] or result['normalization']!=reference['normalization']:raise ValueError('baseline initialization/normalization drift')\n    order=list(range(frames));")
s=s.replace('planned=min(200,math.ceil(frames/args.batch_size))','planned=5')
s=s.replace("stop='epoch_complete'","stop='profile_update_cap_5'")
s=s.replace('while cursor<frames and step<200:', 'while cursor<frames and step<5:')
s=s.replace("            ledger.attempt(step+1,indices,", "            profile_contract.check_step_identity(step+1,indices,profile_contract.identity([loaded['train']['frame_ids'][i] for i in indices]),hashlib.sha256(mask.numpy().tobytes()).hexdigest(),reference)\n            ledger.attempt(step+1,indices,")
s=s.replace("tick=time.perf_counter();losses=training.train_step(torch,model,opt,values,mask)\n            elapsed=time.perf_counter()-tick;rss_after=memory_metrics.rss()", "tick=time.perf_counter();losses,profile_record=probe.run(step+1,model,opt,values,mask)\n            profiled_call_wall=time.perf_counter()-tick;elapsed=profile_record['instrumented_step_seconds'];rss_after=memory_metrics.rss()\n            result['timing']['profiler_outside_step_seconds']+=profile_record['profiler_outside_step_seconds']")
s=s.replace("            if count<=0:raise ValueError('no actual KML in training step')", """            if count!=reference['steps'][step]['kml_calls']:raise ValueError('actual KML calls differ from baseline first5')
            if profile_record['sampled'] and profile_record['kml_markers']!=count:raise ValueError('missing bounded KML markers')
            replay_metrics=[]
            for name,value in losses.items():
                accepted.compare(torch,'baseline_step_'+str(step+1)+'.'+name,
                    torch.tensor(reference['steps'][step]['losses'][name],dtype=torch.float32),value,'tensor',replay_metrics)""")
s=s.replace('record=dict(diagnostic_seconds=', 'record=dict(profile=profile_record,profiled_call_wall_seconds=profiled_call_wall,baseline_loss_metrics=replay_metrics,diagnostic_seconds=')
s=s.replace("if cursor<frames and step==200:stop='update_cap_200'", "if step==5:stop='profile_update_cap_5'")
s=s.replace("'ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE'", "'PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'")
s=s.replace('protocol=engineering_data.PROTOCOL,**engineering_data.FLAGS,','protocol=profile_contract.PROTOCOL,data_protocol=engineering_data.PROTOCOL,baseline_job=\'2043445\',**engineering_data.FLAGS,')
s=s.replace('checkpoint_and_recovery_seconds=0.),','checkpoint_and_recovery_seconds=0.,profiler_outside_step_seconds=0.),')
s=s.replace('max_epochs=1,max_updates=200,','max_epochs=1,max_updates=5,')
s=s.replace("    if not 1<=args.batch_size<=64:parser.error('batch size must be1..64, no accumulation')", "    if args.batch_size!=64:parser.error('fixed baseline batch64, no accumulation')")
s=s.replace("    except engineering_data.SourceChanged", "    except profile_probe.UnsupportedProfiler as exc:result.update(status='UNSUPPORTED_PROFILER',error=str(exc));code=2\n    except profile_probe.ProfileLimit as exc:result.update(status='PROFILE_LIMIT_EXCEEDED',error=str(exc));code=2\n    except engineering_data.SourceChanged")
s=s.replace('import math\n','')
s=s.replace('"""Engineering-only real samples; no formal split or scientific acceptance."""','"""Bounded CPU profile: same first5 updates, warmup2/sample3, no performance acceptance."""')
(ROOT/'train_profile5.py').write_text(s,encoding='utf-8',newline='\n')
s=(ROOT/'run_engineering.sh').read_text().replace('engineering_${CCS_JOB_ID}','profile_${CCS_JOB_ID}').replace('train_engineering.py','train_profile5.py')
s=s.replace("[[ \"$(hostname)\" != login* ]]", "[[ \"$CCS_JOB_ID\" != 2043445 ]] || fail 'original authorization/job already consumed; new reviewed job required'\n[[ \"$(hostname)\" != login* ]]")
s=s.replace("case \"$HERE\" in /home/share/dengqingtian/*)","case \"$HERE\" in /home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_*/payload)")
s=s.replace('# Called only for the unique approved real pilot; no login profile on compute.', '# Preparation only: requires NEW coordination authorization/S01 review/S00 deployment; old job marker is invalid.')
s=s.replace("  --descriptor-sha256 \"$S02_ENGINEERING_DESCRIPTOR_SHA256\" --output", "  --descriptor-sha256 \"$S02_ENGINEERING_DESCRIPTOR_SHA256\" --output")
# Reuse the unchanged engineering metadata inspector, included with its formal isolation gate.
(ROOT/'run_profile5.sh').write_text(s,encoding='utf-8',newline='\n')
