"""Fixed full B64 CKPT0 versus full B64 CKPT1, unchanged mean and thresholds.

Native Windows diagnosis and actual C2/KML share this entry. No memory benchmark.
Exit 1 means original numerical criteria failed; exit 2 means runtime/input error.
"""
import argparse
import copy
import gc
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import traceback
torch = None
F = None

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from diagnostic_common import configure_backend, finish_backend, errors, first_update, sha_file, tensor_sha
sys.path.insert(0, str(ROOT / 'candidate'))
candidate = None

spec = importlib.util.spec_from_file_location('accepted_check', ROOT / 'tests' / 'check_equivalence.py')
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)
MODES = ['reference_repeat', 'candidate_repeat', 'strict', 'full_sum', 'split_full',
         'pinned_full', 'pinned_micro', 'optimizer_same_gradient', 'reduction_trace']


def initial_case(models, definitions):
    from paired_fixture import write_fixture
    from paired_inputs import load_belt_inputs
    with tempfile.TemporaryDirectory(dir=ROOT / 'evidence', prefix='paired_') as directory:
        sources = write_fixture(directory)
        paired = load_belt_inputs(sources['16_adjacent'], '16_adjacent')
    idx = torch.randint(0, len(paired['v']), (64,))
    v = torch.from_numpy(paired['v'])[idx].clone()
    image = torch.from_numpy(paired['y0'])[idx].clone()
    angles = definitions['protocol_angles'](16, 1).expand(64, 208, 4)
    belt = torch.full((64, 208), 0.)
    mask = torch.rand(64, 208) < 0.8
    mask[:16] = False
    mask[16:32] = torch.rand(16, 208) < 0.2
    t, noise = torch.randint(0, 1000, (64,)), torch.randn_like(image)
    abar = torch.cumprod(1-torch.linspace(1e-4, 0.02, 1000), 0)
    return dict(initial=copy.deepcopy(models.state_dict()), v=v, y0=image, idx=idx,
                angles=angles, belt=belt, mask=mask, t=t, noise=noise, abar=abar,
                input_protocol='S02_PAIRED_BELT_V1', scale=paired['scale'],
                frame_ids=[paired['frame_ids'][i] for i in idx.tolist()])


def case_identity(case):
    import hashlib
    digest = hashlib.sha256()
    for name, value in case['initial'].items():
        digest.update(name.encode())
        digest.update(value.contiguous().numpy().tobytes())
    return dict(initial_weights_sha256=digest.hexdigest(), fixed_tensor_sha256={
        name: tensor_sha(case[name]) for name in ('v', 'y0', 'idx', 'mask', 't', 'noise')})


def compare_snapshots(ref, got):
    metrics, failures = [], []
    if set(ref) != set(got):
        raise AssertionError('snapshot keys differ')
    for name in ref:
        category = 'exact' if name.endswith('.step') else 'state' if name.startswith('state.') else 'tensor'
        try:
            accepted.compare(torch, name, ref[name], got[name], category, metrics)
        except AssertionError as exc:
            failures.append(dict(name=name, reason=str(exc)))
    return metrics, failures


def optimizer_details(ref, got, initial):
    records, key_biases = [], []
    for name in initial:
        gr, gc = ref['grad.'+name], got['grad.'+name]
        if gr is None:
            continue
        dr, dc = ref['delta.'+name], got['delta.'+name]
        index = (dc-dr).abs().flatten().argmax().item()
        g0, g1 = gr.flatten()[index].item(), gc.flatten()[index].item()
        p0 = initial[name].flatten()[index].item()
        records.append(dict(name=name, flat_index=index, ref_gradient=g0, got_gradient=g1,
            ref_delta=dr.flatten()[index].item(), got_delta=dc.flatten()[index].item(),
            delta_max_abs=(dc-dr).abs().max().item(), ref_gradient_over_eps=g0/1e-8,
            got_gradient_over_eps=g1/1e-8, ref_first_step_float64_formula=first_update(p0,g0),
            got_first_step_float64_formula=first_update(p0,g1)))
        if name.endswith('self_attn.in_proj_bias'):
            # Q/K/V packed order, frozen width512. K bias adds a common softmax shift.
            key_biases.append(dict(name=name, blocks={label: dict(
                reference_gradient_max_abs=gr[i*512:(i+1)*512].abs().max().item(),
                candidate_gradient_max_abs=gc[i*512:(i+1)*512].abs().max().item(),
                delta_error_max_abs=(dc-dr)[i*512:(i+1)*512].abs().max().item())
                for i,label in enumerate(('Q','K','V'))}))
    return dict(worst_update_coordinates=sorted(records, key=lambda x:x['delta_max_abs'], reverse=True)[:20],
                packed_bias_blocks=key_biases)


def run(models, case, variant, reference=None, upstream=None, projection_records=None):
    enc, dec = models['enc'], models['dec']
    models.load_state_dict(case['initial'], strict=True)
    models.zero_grad(set_to_none=True)
    opt = torch.optim.AdamW(models.parameters(), lr=1e-4, betas=(0.9,0.999), eps=1e-8, weight_decay=0.01)
    calls = []
    step_hook = opt.register_step_post_hook(lambda *_: calls.append(1))
    v, image = case['v'].clone().requires_grad_(), case['y0'].clone().requires_grad_()
    mask, a, belt = case['mask'], case['angles'], case['belt']
    captured = {}
    handles = []
    linear_before = None
    if projection_records is not None:
        import projection_trace
        linear_before = projection_trace.install(models,projection_records)
    def hook(name):
        def capture(_module, _inputs, value):
            record = dict(value=value.detach().clone(), grad=None)
            captured.setdefault(name, []).append(record)
            def backward(grad):
                record['grad'] = grad.detach().clone()
            value.register_hook(backward)
        return capture
    for name, module in {'h':enc.tf, 'voltage':enc.head_v, 'coarse':enc.head_coarse}.items():
        handles.append(module.register_forward_hook(hook(name)))
    try:
        if variant == 'mean':
            from full_batch_step import training_step
            loss = training_step(enc,dec,opt,v,a,belt,image,mask)
        elif variant in ('candidate', 'full_sum'):
            loss = candidate.training_step(enc,dec,opt,v,a,belt,image,part='pre',
                microbatch=32 if variant=='candidate' else 64,mask=mask,
                t=case['t'],noise=case['noise'],abar=case['abar'])
        elif variant == 'split_full':
            h = enc(v,a,belt,mask)
            pv, pc = enc.head_v(h)[...,0], enc.head_coarse(h.mean(1))
            target = F.adaptive_avg_pool2d(image,16).flatten(1)
            loss = v.new_zeros(())
            for start in (0,32):
                s = slice(start,start+32)
                loss = loss + F.mse_loss(pv[s][mask[s]],v[s][mask[s]],reduction='sum')/int(mask.sum())
                loss = loss + F.mse_loss(pc[s],target[s],reduction='sum')/(64*256)
            opt.zero_grad()
            loss.backward()
            opt.step()
        elif variant in ('pinned_full', 'pinned_micro'):
            loss = v.new_zeros(())
            opt.zero_grad()
            for start in range(0,64,64 if variant=='pinned_full' else 32):
                s = slice(start,start+(64 if variant=='pinned_full' else 32))
                h = enc(v[s],a[s],belt[s],mask[s])
                pv, pc = enc.head_v(h), enc.head_coarse(h.mean(1))
                vt, ct = v[s][mask[s]], F.adaptive_avg_pool2d(image[s],16).flatten(1)
                part = F.mse_loss(pv[...,0][mask[s]],vt,reduction='sum')/int(mask.sum())
                part = part + F.mse_loss(pc,ct,reduction='sum')/(64*256)
                loss += part.detach()
                torch.autograd.backward((pv,pc,vt,ct), (upstream['voltage'][s],upstream['coarse'][s],
                    -upstream['voltage'][s][...,0][mask[s]],-upstream['coarse'][s]))
            opt.step()
        elif variant == 'optimizer_copy':
            for name,p in models.named_parameters():
                gradient = reference['grad.'+name]
                p.grad = None if gradient is None else gradient.clone()
            opt.step()
            loss = reference['loss']
        else:
            raise ValueError('unknown diagnostic variant')
    finally:
        if linear_before is not None:F.linear = linear_before
        for handle in handles:handle.remove()
        step_hook.remove()
    assert len(calls)==1, 'expected exactly one AdamW step'
    snapshot = dict(loss=loss.detach().clone(), input_v=v.grad, input_y0=image.grad)
    adjoints = {}
    for name,chunks in captured.items():
        snapshot['output.'+name] = torch.cat([x['value'] for x in chunks])
        adjoints[name] = torch.cat([x['grad'] for x in chunks])
    for name,p in models.named_parameters():
        active = accepted.expected_gradient(name,'pre')
        assert (p.grad is not None)==active, name+': missing/unexpected gradient'
        snapshot['grad.'+name] = None if p.grad is None else p.grad.detach().clone()
        snapshot['param.'+name] = p.detach().clone()
        snapshot['delta.'+name] = p.detach()-case['initial'][name]
        state = opt.state.get(p,{})
        assert set(state)==({'step','exp_avg','exp_avg_sq'} if active else set())
        for key,value in state.items():
            if key=='step':assert value.item()==1
            snapshot['state.'+name+'.'+key] = value.detach().clone()
        if not active:assert torch.equal(p,case['initial'][name])
    assert set(models.state_dict())==set(case['initial'])
    if variant=='optimizer_copy':
        snapshot={k:v for k,v in snapshot.items() if k.startswith(('grad.','param.','delta.','state.'))}
    if captured:
        pv, pc = snapshot['output.voltage'][...,0], snapshot['output.coarse']
        target = F.adaptive_avg_pool2d(case['y0'],16).flatten(1)
        # Common detached float64 score is a diagnostic, not the training loss.
        score=((pv.double()-case['v'].double())[mask].square().mean() +
               (pc.double()-target.double()).square().mean()).item()
    else:score=None
    return snapshot,adjoints,score


def main(args, result):
    global torch, F, candidate
    if args.backend == 'kml':
        import cpu36_guard
        result['cpu36'] = {}
        cpu36_guard.prepare(args.expected_cpus, args.cpu_contract, result['cpu36'])
    import torch
    import torch.nn.functional as F
    import training_step as candidate
    if args.backend == 'kml':
        cpu36_guard.checkpoint(result['cpu36'], 'after_framework', torch)
    runtime, expected = configure_backend(torch,args.backend,args.expected_cpus)
    result['runtime']=runtime
    if args.backend == 'kml':
        cpu36_guard.checkpoint(result['cpu36'], 'after_backend', torch)
    torch.manual_seed(0)
    result['small_autograd_control']=accepted.loss_unit_checks(torch)
    definitions=accepted.model_definitions(torch)
    models=torch.nn.ModuleDict({'enc':definitions['Encoder'](),'dec':definitions['UNet']()})
    counts={name:sum(p.numel() for p in model.parameters()) for name,model in models.items()}
    assert counts==dict(enc=37995777,dec=29416449)
    if args.export_case:
        if args.backend!='native':raise RuntimeError('export fixed case once in native environment')
        case=initial_case(models,definitions)
        torch.save(case,args.export_case)
        result.update(status='CASE_EXPORTED_NOT_A_NUMERICAL_TEST',case_identity=case_identity(case),
                      case_file_sha256=sha_file(args.export_case),case_file_bytes=args.export_case.stat().st_size)
        return 0
    if not args.case_file:raise RuntimeError('provide the frozen --case-file; do not regenerate cross-backend inputs')
    manifest = json.loads((ROOT / 'CASE_MANIFEST.json').read_text())
    if sha_file(args.case_file) != manifest['sha256'] or args.case_file.stat().st_size != manifest['bytes']:
        raise RuntimeError('frozen case file identity mismatch')
    case=torch.load(args.case_file,map_location='cpu',weights_only=True)
    assert case['input_protocol']=='S02_PAIRED_BELT_V1'
    assert case['v'].shape==(64,208) and case['y0'].shape==(64,1,64,64)
    result.update(case_identity=case_identity(case),case_file_sha256=sha_file(args.case_file))
    if result['case_identity'] != manifest['identity']:
        raise RuntimeError('loaded fixed tensor/initial weight identity mismatch')
    left='candidate' if args.mode=='candidate_repeat' else 'mean'
    traces_ref,traces_got=({}, {}) if args.mode=='reduction_trace' else (None,None)
    if args.backend == 'kml':
        cpu36_guard.checkpoint(result['cpu36'], 'before_reference', torch)
    before_calls = runtime.get('kml_gemm_calls', 0)
    ref,up_ref,score_ref=run(models,case,left,projection_records=traces_ref)
    reference_calls = runtime.get('kml_gemm_calls', 0) - before_calls
    if args.backend == 'kml':
        cpu36_guard.checkpoint(result['cpu36'], 'after_reference', torch)
    choices=dict(reference_repeat='mean',candidate_repeat='candidate',strict='candidate',full_sum='full_sum',
                 split_full='split_full',pinned_full='pinned_full',pinned_micro='pinned_micro',
                 optimizer_same_gradient='optimizer_copy',reduction_trace='candidate')
    if args.mode == 'checkpoint_strict':
        del models
        gc.collect()
        models=torch.nn.ModuleDict({'enc':definitions['Encoder'](),'dec':definitions['UNet']()})
        from full_batch_step import enable_checkpoint
        enable_checkpoint(models['enc'])
        result['checkpoint_pair'] = dict(reference=False, candidate=True,
            wrapped_encoder_layers=len(models['enc'].tf.layers), independent_model_instances=True,
            batch=64, loss='unchanged_original_mean', use_reentrant=False)
        choices[args.mode] = 'mean'
    before_calls = runtime.get('kml_gemm_calls', 0)
    got,up_got,score_got=run(models,case,choices[args.mode],ref,up_ref,traces_got)
    result['kml_calls_by_side'] = dict(reference=reference_calls,
        candidate=runtime.get('kml_gemm_calls', 0) - before_calls)
    if args.backend == 'kml':
        cpu36_guard.checkpoint(result['cpu36'], 'after_candidate', torch)
    if args.mode=='optimizer_same_gradient':ref={k:v for k,v in ref.items() if k in got}
    metrics,failures=compare_snapshots(ref,got)
    result.update(metrics=metrics,failures=failures,comparison_failures=len(failures),
                  adjoint_differences={k:errors(up_ref[k],up_got[k]) for k in up_got},
                  detached_common_float64_score=dict(reference=score_ref,candidate=score_got),
                  optimizer_details=optimizer_details(ref,got,case['initial']),
                  parameter_counts=counts)
    summary={}
    for item in metrics:
        family=item['name'].split('.')[0]
        group=summary.setdefault(family,dict(tensors=0,failed=0,max_abs=0.,max_relative=0.))
        group['tensors']+=1;group['failed']+=int(not item['passed'])
        group['max_abs']=max(group['max_abs'],item['max_abs'])
        group['max_relative']=max(group['max_relative'],item['l2_relative'])
    result['summary']=summary
    if traces_ref is not None:
        import projection_trace
        result['projection_trace']=projection_trace.summarize(traces_ref,traces_got,ref,got)
    finish_backend(runtime,expected)
    if args.backend == 'kml':
        cpu36_guard.finish(result['cpu36'], torch)
    if args.backend == 'kml' and any(value <= 0 for value in result['kml_calls_by_side'].values()):
        raise RuntimeError('both full-batch paths require actual KML calls')
    result['status']='FAIL_ORIGINAL_CRITERIA' if failures else 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
    result['exact_repeat']=all(ref[k] is None or torch.equal(ref[k],got[k]) for k in ref) if 'repeat' in args.mode else None
    return int(bool(failures))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=['native','kml'],required=True)
    parser.add_argument('--mode',choices=['checkpoint_strict'],default='checkpoint_strict')
    parser.add_argument('--case-file',type=Path)
    parser.add_argument('--export-case',type=Path)
    parser.add_argument('--expected-cpus',type=lambda s:[int(v) for v in s.split(',')])
    parser.add_argument('--cpu-contract',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or (args.export_case and args.export_case.exists()):parser.error('refuse existing output/case')
    result=dict(status='STARTED',started_utc=datetime.now(timezone.utc).isoformat(),mode=args.mode,
        config=dict(belt='16_adjacent',part='pre',effective_batch=64,microbatch=64,
                    reference_checkpoint=False,candidate_checkpoint=True,
                    history='fresh',precision='fp32',threads=36),diagnostic_only=False,
        source_sha256={name:sha_file(ROOT/name) for name in ['diagnose_update.py','diagnostic_common.py','projection_trace.py',
            'tests/check_equivalence.py','tests/paired_fixture.py','baseline/s4_models.py',
            'baseline/kml_ops.py','candidate/training_step.py','candidate/paired_inputs.py','VALIDATION_PLAN.md',
            'cpu36_guard.py','cpu36_contract.py','run_c2_diagnostic.sh','CASE_MANIFEST.json',
            'candidate/full_batch_step.py']})
    try:code=main(args,result)
    except Exception as exc:
        result.update(status='ERROR_RUNTIME_OR_INPUT',error=repr(exc),traceback=traceback.format_exc());code=2
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k in ['status','mode','comparison_failures','summary','error']},indent=2))
    sys.exit(code)
