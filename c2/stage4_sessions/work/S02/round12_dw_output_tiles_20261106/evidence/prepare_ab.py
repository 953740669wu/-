"""Reuse comparison logic only, never the R10 view candidate."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'reference/train_linear_ab_r10.py').read_text()
s=s.replace('import engineering_data as data','from data_gate import engineering_data as data')
s=s.replace('from screen_linear import source_identity','from runtime_counts import source_identity,attach_native,verify_step,TARGET_KEY')
s=s.replace('S02_LINEAR_R10_','S02_DW_R12_').replace("(None,'2043445','2048959')","(None,'2043445','2048959','2049454')")
s=s.replace('s02_r10_candidate_kml','s02_r12_candidate_kml').replace('ENGINEERING_LINEAR_R10_AB_V1','ENGINEERING_DW_TILES_R12_AB_V1')
s=s.replace("    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())", "    reference=json.loads((ROOT/'REFERENCE_FIRST5.json').read_text())\n    epoch_reference=json.loads((ROOT/'REFERENCE_EPOCH25.json').read_text())\n    planned=5 if args.phase=='strict' else 25\n    result['planned_updates']=planned\n    result['warmup_updates']=0 if args.phase=='strict' else 5")
s=s.replace("    if args.phase=='perf':\n        if not args.strict_receipt", """    if args.phase=='strict':
        if not args.target_screen or data.sha(args.target_screen)!=args.target_screen_sha256:raise ValueError('actual KML target screen receipt/SHA required')
        prior=json.loads(args.target_screen.read_text())
        if prior.get('status')!='PASS_ACTUAL_KML_TARGET_ONLY' or any(prior.get(k)!=result[k] for k in ('source_manifest_sha256','host','job_id')):
            raise ValueError('target screen source/node/job differs or failed')
        if prior.get('cpu36',{}).get('receipt',{}).get('selected')!=[int(v) for v in args.expected_cpus.split(',')]:raise ValueError('target screen CPUs differ')
        result['target_screen_sha256']=args.target_screen_sha256
    if args.phase=='perf':
        if not args.strict_receipt""")
s=s.replace("        check_receipt(json.loads(args.strict_receipt.read_text()),", "        prior=json.loads(args.strict_receipt.read_text())\n        check_receipt(prior,")
s=s.replace("    baseline=sys.modules['kml_ops'];modules=dict(baseline=baseline,candidate=candidate)", """    if runtime['libraries']!=prior['runtime']['libraries'] or any(runtime.get(k)!=prior['runtime'].get(k) for k in ('torch','torch_file','numpy','numpy_file','env')):
        raise ValueError('same-job library/framework/environment drift')
    baseline=sys.modules['kml_ops'];modules=dict(baseline=baseline,candidate=candidate)
    native_states={role:attach_native(module) for role,module in modules.items()};result['native_counts']=native_states""")
s=s.replace('        for step in range(1,6):','        for step in range(1,planned+1):')
s=s.replace("            profile_contract.check_step_identity(step,indices,profile_contract.identity(frame_ids),mask_sha,reference)","""            if step<=5:profile_contract.check_step_identity(step,indices,profile_contract.identity(frame_ids),mask_sha,reference)
            expected_frame=epoch_reference['steps'][step-1]
            if indices!=expected_frame['frame_indices'] or profile_contract.identity(frame_ids)!=expected_frame['frame_ids_sha256'] or mask_sha!=expected_frame['mask_sha256']:
                raise ValueError('epoch frame/order/mask identity drift')""")
s=s.replace("                rss_before=memory_metrics.rss();calls=runtime['kml_gemm_calls'];pre_diag=time.perf_counter()-diagnostic_start", """                rss_before=memory_metrics.rss();calls=runtime['kml_gemm_calls'];logical_target=runtime['kml_shapes'].get(TARGET_KEY,0)
                native_before={k:native_states[role][k] for k in ('native_calls','target_full','target_tiles')}
                pre_diag=time.perf_counter()-diagnostic_start""")
s=s.replace("                if actual_calls!=reference['steps'][step-1]['kml_calls']:raise ValueError('KML call count differs')\n                for key,value in losses.items():accepted.compare(torch,f'{role}.{step}.baseline_loss.{key}',\n                    torch.tensor(reference['steps'][step-1]['losses'][key],dtype=torch.float32),value,'tensor',result['metrics'])", """                native_delta={k:native_states[role][k]-native_before[k] for k in native_before}
                target_delta=runtime['kml_shapes'].get(TARGET_KEY,0)-logical_target
                verify_step(role,actual_calls,target_delta,native_delta['native_calls'],native_delta['target_full'],native_delta['target_tiles'])
                if step<=5:
                    for key,value in losses.items():accepted.compare(torch,f'{role}.{step}.baseline_loss.{key}',
                        torch.tensor(reference['steps'][step-1]['losses'][key],dtype=torch.float32),value,'tensor',result['metrics'])
                elif any(not torch.isfinite(value) for value in losses.values()):raise ValueError('nonfinite epoch loss')""")
s=s.replace("                    kml_calls=actual_calls,adamw_step=step,sampled=step>=3,", "                    kml_calls=actual_calls,native_sgemm_calls=native_delta['native_calls'],target_logical_gemm=target_delta,\n                    target_native_full=native_delta['target_full'],target_native_tiles=native_delta['target_tiles'],dispatch_hits=native_delta['target_tiles']//2,\n                    adamw_step=step,sampled=args.phase=='perf' and step>=6,")
s=s.replace('cursor=320,optimizer_updates=5,planned_updates=5,epoch_completed=False','cursor=1600,optimizer_updates=25,planned_updates=25,epoch_completed=True')
s=s.replace("'PERF5_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE'","'PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE'")
s=s.replace("    p.add_argument('--strict-receipt',type=Path);", "    p.add_argument('--target-screen',type=Path);p.add_argument('--target-screen-sha256');\n    p.add_argument('--strict-receipt',type=Path);")
s=s.replace("    except Exception as exc:result.update(status='FAIL_STOP_NO_RETRY'", "    except TimeoutError as exc:result.update(status='INCOMPLETE_STOP_NO_RETRY',error=repr(exc),traceback=traceback.format_exc());code=3\n    except Exception as exc:result.update(status='FAIL_STOP_NO_RETRY'")
s=s.replace("    if normalization!=reference['normalization']:raise ValueError('normalization differs')", "    if normalization!=reference['normalization']:raise ValueError('normalization differs')\n    result['normalization']=normalization")
s=s.replace("    for role in roles:\n        torch.manual_seed", "    result['initialization']={}\n    for role in roles:\n        torch.manual_seed")
s=s.replace("        if sum(p.numel() for p in models[role].parameters())!=37995777 or training.model_sha(models[role])!=reference['initialization']['initial_weights_sha256']:", "        digest=training.model_sha(models[role])\n        result['initialization'][role]=dict(initial_weights_sha256=digest,parameters=sum(p.numel() for p in models[role].parameters()),train_seed=0)\n        if result['initialization'][role]['parameters']!=37995777 or digest!=reference['initialization']['initial_weights_sha256']:")
s=s.replace("    result['timing']=dict(", "    result['optimizer_updates_total']=len(result['steps'])\n    result['timing']=dict(")
s=s.replace("result=dict(status='STARTED',protocol=", "result=dict(status='STARTED',pid=os.getpid(),argv=list(sys.argv),protocol=")
(ROOT/'train_dw_ab.py').write_text(s,encoding='utf-8',newline='\n')
