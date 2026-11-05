"""Independent five-update DDR/HBM0 sequence; no comparison snapshots."""
import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import sys
import time
import traceback

import cpu36_guard
from diagnostic_common import configure_backend, finish_backend, sha_file
import memory_metrics
from sequence_core import SequenceState, STEPS, accepted, load_case
import sequence_gate
import sequence_runtime

ROOT = Path(__file__).resolve().parent


def measure_step(state, step, observe, runtime, record):
    record.update(step=step, before=state.begin(step))
    observe(f'before_training_{step}')
    record['before_reset'] = memory_metrics.rss()
    record['peak_reset'] = memory_metrics.reset_peak()
    if not record['peak_reset']['available']:
        raise ValueError('training HWM reset unavailable; this update was not executed')
    record['training_start'] = memory_metrics.rss()
    calls = runtime.get('kml_gemm_calls', 0)
    started = time.perf_counter()
    loss = state.update()
    elapsed = time.perf_counter() - started
    # First operation after the clock: capture HWM before validation/loss.item/JSON.
    record['training'] = dict(elapsed_seconds=elapsed, **memory_metrics.rss())
    record['after'] = state.validate(step)
    record['loss'] = loss.item()
    record['kml_calls'] = runtime.get('kml_gemm_calls', 0) - calls
    if record['kml_calls'] <= 0:
        raise ValueError('no actual KML on this training update')
    observe(f'after_training_{step}')


def main(args, result):
    initialized = time.perf_counter()
    result['strict_reference'] = sequence_gate.check_path(args.strict_result)
    result['cpu36'] = {}
    cpu36_guard.prepare(args.expected_cpus, args.cpu_contract, result['cpu36'])
    import torch
    cpu36_guard.checkpoint(result['cpu36'], 'after_framework', torch)
    runtime, expected = configure_backend(torch, 'kml', args.expected_cpus)
    result['runtime'] = runtime
    if {item['path']: item['sha256'] for item in runtime['libraries']} != result['strict_reference']['strict_libraries']:
        raise ValueError('memory runtime library identity differs from five-step strict result')
    cpu36_guard.checkpoint(result['cpu36'], 'after_backend', torch)
    torch.manual_seed(0)
    case, identity = load_case(torch, args.case_file); result.update(identity)
    state = SequenceState(torch, accepted.model_definitions(torch), case, bool(args.checkpoint))
    counts = {name: sum(p.numel() for p in model.parameters()) for name, model in state.models.items()}
    assert counts == dict(enc=37995777, dec=29416449)
    result['parameter_counts'] = counts
    del case['initial']; gc.collect()
    cpu36_guard.checkpoint(result['cpu36'], 'initialized', torch)
    result['initialization'] = dict(elapsed_seconds=time.perf_counter()-initialized, **memory_metrics.rss())
    result['steps'] = []
    for step in range(1, STEPS+1):
        record = dict(case_file_sha256=result['case_file_sha256'], source_manifest_sha256=result['source_manifest_sha256'])
        result['steps'].append(record)
        measure_step(state, step, lambda name: cpu36_guard.checkpoint(result['cpu36'], name, torch), runtime, record)
    finish_backend(runtime, expected)
    sequence_runtime.finish(result['cpu36'], torch, 'memory', STEPS)
    result.update(status='DDR_SEQUENCE5_DIAGNOSTIC_ONLY_NOT_STEADY_STATE', completed_steps=state.completed,
                  comparison_snapshots_retained=False, repeated_same_fixed_case=True)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=int, choices=[0,1], required=True)
    parser.add_argument('--strict-result', type=Path, required=True)
    parser.add_argument('--case-file', type=Path, required=True)
    parser.add_argument('--expected-cpus', type=lambda s:[int(x) for x in s.split(',')], required=True)
    parser.add_argument('--cpu-contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('refuse existing output')
    result = dict(status='STARTED', started_utc=datetime.now(timezone.utc).isoformat(), mode='sequence5_memory',
        config=dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64, checkpoint=bool(args.checkpoint),
            precision='fp32', threads=36, hbm=False, history='fresh_once_then_continuous', updates=5,
            repeated_same_fixed_case=True, loss='original_mean', warmup_steps=0),
        measurement=dict(unit='bytes / MiB (2**20 bytes) / seconds', method='same R6 VmRSS/VmHWM and clear_refs=5',
            scope='whole-process DDR/HBM0 RSS, not tensor-only/PSS/HBM residency; five updates are not steady-state'),
        source_manifest_sha256=sha_file(ROOT/'SOURCE_SHA256.json'),
        source_sha256={name: sha_file(ROOT/name) for name in ['train_sequence5.py','sequence_core.py','sequence_gate.py',
            'sequence_runtime.py','memory_metrics.py','candidate/full_batch_step.py','candidate/training_step.py',
            'tests/check_equivalence.py','baseline/s4_models.py','baseline/kml_ops.py',
            'diagnostic_common.py','cpu36_guard.py','cpu36_contract.py','CASE_MANIFEST.json']})
    try:
        code = main(args, result)
    except Exception as exc:
        result.update(status='ERROR_RUNTIME_OR_STATE', error=repr(exc), traceback=traceback.format_exc()); code=2
    result['ended_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('status','completed_steps','error') if key in result}, indent=2))
    sys.exit(code)
