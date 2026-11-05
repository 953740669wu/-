"""Five full B64 CKPT0/1 updates; original complete comparison after every step."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import traceback

import cpu36_guard
from diagnostic_common import configure_backend, finish_backend, sha_file
import sequence_runtime
from sequence_core import SequenceState, STEPS, accepted, load_case

ROOT = Path(__file__).resolve().parent
METRICS_PER_STEP = 1063


def numerical_step(state, step):
    torch, models = state.torch, state.models
    before_digest = state.digest()
    previous = {name: parameter.detach().clone() for name, parameter in models.named_parameters()}
    before = state.begin(step)
    outputs, handles = {}, []
    def hook(name):
        def capture(_module, _args, value):
            outputs[name] = value.detach().clone()
        return capture
    for name, module in dict(h=models['enc'].tf, voltage=models['enc'].head_v,
                             coarse=models['enc'].head_coarse).items():
        handles.append(module.register_forward_hook(hook(name)))
    try:
        loss = state.update()
    finally:
        for handle in handles:
            handle.remove()
    after = state.validate(step)
    snapshot = dict(loss=loss, input_v=state.v.grad.detach().clone(), input_y0=state.image.grad.detach().clone())
    snapshot.update({'output.' + name: value for name, value in outputs.items()})
    for name, parameter in models.named_parameters():
        snapshot['grad.' + name] = None if parameter.grad is None else parameter.grad.detach().clone()
        snapshot['param.' + name] = parameter.detach().clone()
        snapshot['delta.' + name] = parameter.detach() - previous[name]
        for key, value in state.optimizer.state.get(parameter, {}).items():
            snapshot['state.' + name + '.' + key] = value.detach().clone()
        if not accepted.expected_gradient(name, 'pre'):
            assert torch.equal(parameter, previous[name]), 'inactive parameter changed: ' + name
    return snapshot, dict(step=step, before=before, after=after, before_digest=before_digest,
                          after_digest=state.digest(), delta_origin='own_previous_update_parameters')


def compare_step(torch, reference, candidate):
    if set(reference) != set(candidate):
        raise ValueError('snapshot keys differ')
    metrics, failures = [], []
    for name in reference:
        category = 'exact' if name.endswith('.step') else 'state' if name.startswith('state.') else 'tensor'
        try:
            accepted.compare(torch, name, reference[name], candidate[name], category, metrics)
        except AssertionError as exc:
            failures.append(dict(name=name, reason=str(exc)))
    return metrics, failures


def run_steps(states, result, observe, runtime):
    previous = [state.digest() for state in states]
    if previous[0] != previous[1]:
        raise ValueError('reference and candidate initial parameter/optimizer states differ')
    result['steps'] = []
    for step in range(1, STEPS + 1):
        record = dict(step=step, lineage={}, case_file_sha256=result['case_file_sha256'],
                      source_manifest_sha256=result['source_manifest_sha256'])
        result['steps'].append(record)
        snapshots, lineage, calls = [], [], []
        for label, state in zip(('reference', 'candidate'), states):
            observe(f'before_{label}_{step}')
            count = runtime.get('kml_gemm_calls', 0)
            snapshot, meta = numerical_step(state, step)
            observe(f'after_{label}_{step}')
            snapshots.append(snapshot); lineage.append(meta)
            record['lineage'][label] = meta
            calls.append(runtime.get('kml_gemm_calls', 0) - count)
        if [item['before_digest'] for item in lineage] != previous:
            raise ValueError('parameters/optimizer state not carried from previous update')
        metrics, failures = compare_step(states[0].torch, *snapshots)
        if not failures and len(metrics) != METRICS_PER_STEP:
            raise ValueError('incomplete original metric coverage')
        if any(value <= 0 for value in calls):
            raise ValueError('each side/step requires actual KML calls')
        record.update(kml_calls=dict(zip(('reference','candidate'), calls)), metrics=metrics,
                      failures=failures, comparison_failures=len(failures))
        del snapshots, snapshot
        previous = [item['after_digest'] for item in lineage]
        if failures:
            return False
    return True


def main(args, result):
    result['cpu36'] = {}
    cpu36_guard.prepare(args.expected_cpus, args.cpu_contract, result['cpu36'])
    import torch
    cpu36_guard.checkpoint(result['cpu36'], 'after_framework', torch)
    runtime, expected = configure_backend(torch, 'kml', args.expected_cpus)
    result['runtime'] = runtime
    cpu36_guard.checkpoint(result['cpu36'], 'after_backend', torch)
    torch.manual_seed(0)
    case, identity = load_case(torch, args.case_file); result.update(identity)
    definitions = accepted.model_definitions(torch)
    states = [SequenceState(torch, definitions, case, checkpoint) for checkpoint in (False, True)]
    counts = {name: sum(p.numel() for p in model.parameters()) for name, model in states[0].models.items()}
    assert counts == dict(enc=37995777, dec=29416449)
    result['parameter_counts'] = counts
    result['checkpoint_wrapped_layers'] = len(states[1].models['enc'].tf.layers)
    passed = run_steps(states, result, lambda name: cpu36_guard.checkpoint(result['cpu36'], name, torch), runtime)
    finish_backend(runtime, expected)
    sequence_runtime.finish(result['cpu36'], torch, 'strict', len(result['steps']))
    result.update(completed_steps=len(result['steps']), comparison_failures=sum(s['comparison_failures'] for s in result['steps']),
                  status='PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY' if passed else 'FAIL_ORIGINAL_CRITERIA')
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-file', type=Path, required=True)
    parser.add_argument('--expected-cpus', type=lambda s: [int(x) for x in s.split(',')], required=True)
    parser.add_argument('--cpu-contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('refuse existing output')
    result = dict(status='STARTED', started_utc=datetime.now(timezone.utc).isoformat(), mode='sequence5_strict',
        config=dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
            reference_checkpoint=False, candidate_checkpoint=True, precision='fp32', threads=36, hbm=False,
            history='fresh_once_then_continuous', updates=5, repeated_same_fixed_case=True, loss='original_mean'),
        source_manifest_sha256=sha_file(ROOT / 'SOURCE_SHA256.json'),
        source_sha256={name: sha_file(ROOT / name) for name in [
            'check_sequence5.py','sequence_core.py','sequence_runtime.py','candidate/full_batch_step.py',
            'candidate/training_step.py','baseline/s4_models.py','baseline/kml_ops.py',
            'tests/check_equivalence.py','diagnostic_common.py','cpu36_guard.py','cpu36_contract.py','CASE_MANIFEST.json']})
    try:
        code = main(args, result)
    except Exception as exc:
        result.update(status='ERROR_RUNTIME_OR_STATE', error=repr(exc), traceback=traceback.format_exc()); code = 2
    result['ended_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status','completed_steps','comparison_failures','error') if k in result}, indent=2))
    sys.exit(code)
