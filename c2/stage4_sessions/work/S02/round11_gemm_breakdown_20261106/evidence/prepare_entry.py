"""Copy the frozen R9 entry, replacing profiler scopes only with GEMM hooks."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'reference/train_profile5.py').read_text()
s=s.replace('import engineering_data','from data_gate import engineering_data').replace('import profile_probe','import gemm_observer')
s=s.replace('import argparse\n','import argparse\nimport ctypes\n')
s=s.replace("startswith('S02_PROFILE5_')","startswith('S02_GEMM5_')").replace('S00/S02_PROFILE5_*/payload','S00/S02_GEMM5_*/payload')
s=s.replace("'profile_'+os.environ", "'gemm_'+os.environ")
s=s.replace('new owned profile job output path required','new owned GEMM job output path required')
s=s.replace("'profile ledger in fresh job outputs;", "'GEMM ledger in fresh job outputs;")
start=s.index('    probe=profile_probe.Probe')
end=s.index('    tick=time.perf_counter()',start)
s=s[:start]+'''    baseline_path=ROOT/'baseline/kml_ops.py'
    if real_data.sha(baseline_path)!='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26':raise ValueError('unmodified baseline KML source required; R10 forbidden')
    if not isinstance(kml_ops._sgemm,ctypes._CFuncPtr):raise gemm_observer.UnsupportedObservation('original _sgemm must be a ctypes native function, not a Python substitute')
    if Path(gemm_observer.__file__).resolve()!=ROOT/'gemm_observer.py':raise gemm_observer.UnsupportedObservation('wrong observer module origin')
    observer=gemm_observer.Observer(kml_ops,args.output_dir)
    result['gemm_observation']=dict(baseline_kml_sha256=real_data.sha(baseline_path),
        baseline_import=dict(path=kml_ops.__file__,sha256=real_data.sha(kml_ops.__file__)),
        observer_import=dict(path=gemm_observer.__file__,sha256=real_data.sha(gemm_observer.__file__)),
        original_sgemm_type=type(kml_ops._sgemm).__name__,
        observer_source_sha256=real_data.sha(ROOT/'gemm_observer.py'),detailed_steps=[3,4,5],samples=observer.samples,
        timing_scope='GEMM envelope and same-thread ctypes wall; outer-minus-ctypes includes prep/counter/alloc/observer; neither is pure microkernel time')
'''+s[end:]
s=s.replace("stop='profile_update_cap_5'","stop='gemm_update_cap_5'")
s=s.replace("tick=time.perf_counter();losses,profile_record=probe.run(step+1,model,opt,values,mask)\n            profiled_call_wall=time.perf_counter()-tick;elapsed=profile_record['instrumented_step_seconds'];rss_after=memory_metrics.rss()\n            result['timing']['profiler_outside_step_seconds']+=profile_record['profiler_outside_step_seconds']",'''tick=time.perf_counter()
            if step+1>=3:
                with observer.sample(step+1) as sample:
                    train_tick=time.perf_counter();losses=training.train_step(torch,model,opt,values,mask)
                    elapsed=time.perf_counter()-train_tick
                call_wall=time.perf_counter()-tick
                result['timing']['observation_export_and_hook_seconds']+=call_wall-elapsed
            else:
                losses=training.train_step(torch,model,opt,values,mask);elapsed=time.perf_counter()-tick
                sample=None;call_wall=elapsed
            rss_after=memory_metrics.rss()''')
s=s.replace("            if profile_record['sampled'] and profile_record['kml_markers']!=count:raise ValueError('missing bounded KML markers')", "            if sample is not None and (sample['records']!=count or sample['native_calls']!=count):raise gemm_observer.ObservationError('GEMM/native sample count differs from actual KML calls')")
s=s.replace('record=dict(profile=profile_record,profiled_call_wall_seconds=profiled_call_wall,','record=dict(gemm_sample=sample,observed_call_wall_seconds=call_wall,')
s=s.replace("'PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'", "'GEMM5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE'")
s=s.replace('protocol=profile_contract.PROTOCOL','protocol=gemm_observer.PROTOCOL')
s=s.replace('profiler_outside_step_seconds=0.','observation_export_and_hook_seconds=0.')
start=s.index('    except profile_probe.UnsupportedProfiler')
end=s.index('    except engineering_data.SourceChanged',start)
s=s[:start]+'''    except gemm_observer.UnsupportedObservation as exc:result.update(status='UNSUPPORTED_GEMM_OBSERVATION',error=str(exc));code=2
    except gemm_observer.ObservationLimit as exc:result.update(status='GEMM_LIMIT_EXCEEDED',error=str(exc));code=2
    except gemm_observer.ObservationError as exc:result.update(status='GEMM_OBSERVATION_ERROR',error=str(exc));code=2
'''+s[end:]
# No observer active during validation, save, recovery or publication.
needle="    finish_backend(runtime,expected)"
s=s.replace(needle,"    if observer.active or [x['step'] for x in observer.samples] != list(range(3,step+1)):raise gemm_observer.ObservationError('sample lifecycle mismatch')\n    if any(x['status']!='COMPLETE' for x in observer.samples):raise gemm_observer.ObservationError('incomplete sample records')\n"+needle)
s=s.replace('"""Bounded CPU profile: same first5 updates, warmup2/sample3, no performance acceptance."""','"""Unmodified baseline,5 updates: warmup2, GEMM/ctypes scalar records3..5."""')
(ROOT/'train_gemm5.py').write_text(s,encoding='utf-8',newline='\n')
s=(ROOT/'reference/run_profile5.sh').read_text().replace('S02_PROFILE5_','S02_GEMM5_').replace('profile_${CCS_JOB_ID}','gemm_${CCS_JOB_ID}').replace('train_profile5.py','train_gemm5.py')
s=s.replace('[[ "$CCS_JOB_ID" != 2043445 ]]','[[ "$CCS_JOB_ID" != 2043445 && "$CCS_JOB_ID" != 2048959 ]]')
s=s.replace('# Preparation only: requires NEW coordination authorization/S01 review/S00 deployment; old job marker is invalid.', '# R11 task-card authorization: new S00 deployment/marker and SHA-bound S01 PASS required; old jobs invalid.')
(ROOT/'run_gemm5.sh').write_text(s,encoding='utf-8',newline='\n')
old=ROOT.parent/'overnight_engineering_20261105'
s=(old/'inspect_engineering.py').read_text().replace('import engineering_data as data','from data_gate import engineering_data as data')
(ROOT/'inspect_engineering.py').write_text(s,encoding='utf-8',newline='\n')
