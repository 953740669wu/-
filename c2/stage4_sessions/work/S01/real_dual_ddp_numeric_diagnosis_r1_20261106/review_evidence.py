"""Independent saved-evidence audit; no model, autograd, GEMM or communication run."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
OWN = Path(__file__).resolve().parent
WORK = OWN.parent.parent
SRC = WORK / 'S07/real_dual_ddp_numeric_diagnosis_r1_20261106'
OLD = WORK / 'S07/real_dual_ddp_20261106'
COMPARE = WORK / 'S02/real_dual_ddp_reference_20261106/tests/check_equivalence.py'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def asset(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    verified = {}

    def verify(value):
        if isinstance(value, dict):
            if {'path', 'sha256'} <= value.keys():
                actual = asset(value['path'])
                assert actual['sha256'] == value['sha256'], value['path']
                if 'bytes' in value:
                    assert actual['bytes'] == value['bytes'], value['path']
                verified[actual['path']] = actual
            for child in value.values():
                verify(child)
        elif isinstance(value, list):
            for child in value:
                verify(child)

    ready = read(SRC / 'DIAGNOSIS_READY.json')
    verified[str(SRC / 'DIAGNOSIS_READY.json')] = asset(SRC / 'DIAGNOSIS_READY.json')
    verify(ready)
    sources = read(SRC / 'SOURCE_INPUTS.json')
    evidence = read(SRC / 'EVIDENCE_MANIFEST.json')
    diagnosis = read(SRC / 'DIAGNOSIS.json')
    for value in (sources, evidence, diagnosis, read(SRC / 'evidence/RUN_SOURCES.json')):
        verify(value)
    assert len(sources['files']) == 17
    assert asset(COMPARE)['sha256'] == 'e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e'
    assert asset(WORK / 'S01/real_dual_ddp_review_20261106/S01_REVIEW.json')['sha256'] == 'f933a3af02a9362b9bce854935cbb18eecebfb38dd761805da163b48ff110f74'
    for name in ('run_once.py', 'diagnostic_worker.py'):
        ast.parse((SRC / name).read_text(encoding='utf-8'), feature_version=(3, 9))
    assert diagnosis['full_vs_sequence'] == read(SRC / 'evidence/FULL_VS_SEQUENCE.json')
    assert diagnosis['float64_cause_control'] == read(SRC / 'evidence/FLOAT64_CONTROL.json')
    assert diagnosis['new_ddp_comparisons'] is None
    assert ready['run_counts'] == diagnosis['run_counts'] == dict(full=1, sequence=1, ddp=1, fp64=1)
    markers = {name: read(SRC / ('RUN_' + name + '.json')) for name in ready['run_counts']}
    assert markers['full']['start_monotonic'] < markers['sequence']['start_monotonic'] < markers['fp64']['start_monotonic'] < markers['ddp']['start_monotonic']
    assert (SRC / 'FLOAT64_PURPOSE.json').stat().st_mtime_ns <= (SRC / 'RUN_fp64.json').stat().st_mtime_ns
    for name, row in diagnosis['paths'].items():
        assert row == read(SRC / 'evidence' / (name + '_supervision.json'))
        assert row['seconds'] <= 60 + 15 and row['cleanup_seconds'] <= 15
        assert row['all_reaped'] is True
    assert diagnosis['local_wall_seconds'] <= 300
    assert not (SRC / 'RUN_merge.json').exists() and not (SRC / 'raw/ddp0.pt').exists() and not (SRC / 'raw/ddp1.pt').exists()
    for rank in (0, 1):
        log = (SRC / f'evidence/ddp{rank}.log').read_text(errors='replace')
        assert 'before_pg' in log and '10013' in log and '10049' in log and 'after_pg' not in log

    # Only deserialize already captured tiny tensors and recompute existing comparison metrics.
    # No author controller/worker is executed; no forward/backward or contraction is repeated.
    import torch
    full = torch.load(SRC / 'raw/full.pt', weights_only=True, map_location='cpu')
    seq = torch.load(SRC / 'raw/sequence.pt', weights_only=True, map_location='cpu')
    initial = {name: read(SRC / 'evidence' / (name + '_initial.json')) for name in ('full', 'sequence', 'ddp0', 'ddp1')}
    for value in initial.values():
        assert value['initialization_sha256'] == initial['full']['initialization_sha256']
        assert value['post_init_rng_sha256'] == initial['full']['post_init_rng_sha256']
        assert value['environment'] == initial['full']['environment']
        assert value['seed'] == 7 and value['optimizer_updates'] == 0 and value['parameters'] == 1337
    assert full['metadata'] == initial['full'] and seq['metadata'] == initial['sequence']
    assert full['parts'][0]['shards'] == [p['shards'][0] for p in seq['parts']]
    assert [(p['start'], p['stop']) for p in seq['parts']] == [(0, 32), (32, 64)]
    assert full['parts'][0]['local_counts'] == [4, 16384]
    assert [p['local_counts'] for p in seq['parts']] == [[1, 8192], [3, 8192]]
    for rank in (0, 1):
        assert initial[f'ddp{rank}']['prepared_inputs_sha256'] == full['parts'][0]['shards'][rank]['inputs_sha256']
    for value in (full, seq):
        assert value['global_counts'] == [4, 16384] and value['backward_multiplier'] == 1
    for name in ('full', 'sequence'):
        complete = read(SRC / 'evidence' / (name + '_complete.json'))
        assert (complete['parameter_grad_divisor'], complete['input_grad_divisor']) == (1, 1)

    tree = ast.parse(COMPARE.read_text(encoding='utf-8'))
    compare_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'compare')
    namespace = {}
    exec(compile(ast.Module(body=[compare_node], type_ignores=[]), str(COMPARE), 'exec'), namespace)
    rows = []

    def compare(name, left, right):
        try:
            namespace['compare'](torch, name, left, right, 'tensor', rows)
        except AssertionError:
            assert rows and rows[-1]['name'] == name and rows[-1]['passed'] is False

    assert set(full['tensors']) == set(seq['tensors'])
    for name, value in full['tensors'].items():
        compare(name, value, seq['tensors'][name])
    for name in ('voltage', 'coarse', 'total'):
        compare('loss.' + name, full['losses'][name], seq['losses'][name])
    assert set(full['parameter_grads']) == set(seq['parameter_grads'])
    assert len(full['parameter_grads']) == 11
    for name, value in full['parameter_grads'].items():
        compare('parameter.' + name, value, seq['parameter_grads'][name])
    for name in ('v', 'image'):
        compare('input.' + name, full['input_grads'][name], seq['input_grads'][name])
    reported = diagnosis['full_vs_sequence']['metrics']
    assert len(rows) == len(reported) == 34
    for actual, published in zip(rows, reported):
        assert all(published[k] == v for k, v in actual.items()), actual['name']
    original13 = read(OLD / 'evidence/tiny_ddp_192181562000000/strict_pair_metrics.json')
    indexed = {row['name']: row for row in rows}
    for row in original13:
        name = 'input.' + row['name'][6:] if row['name'].startswith('input_') else 'parameter.' + row['name']
        assert all(indexed[name][k] == row[k] for k in ('max_abs', 'l2_relative', 'reference_norm', 'passed'))
    exact_observations = {}
    for name, value in full['tensors'].items():
        other = seq['tensors'][name]
        exact = value.numpy().tobytes() == other.numpy().tobytes()
        exact_observations[name] = exact
        assert exact and next(row for row in reported if row['name'] == name)['exact'] is True
    control = diagnosis['float64_cause_control']
    assert control['scope'] == 'ONE_RECORDED_OPERAND_CONTRACTION_CONTROL_NO_MODEL_RERUN'
    pid_gaps = {name: dict(supervised_pids=diagnosis['paths']['ddp' if name.startswith('ddp') else name]['pids'],
                           recorded_compute_pid=value['pid']) for name, value in initial.items()
                if value['pid'] not in diagnosis['paths']['ddp' if name.startswith('ddp') else name]['pids']}
    result = dict(status='REVIEWED_PARTIAL_DIAGNOSIS_NO_TRAINING_RELEASE',
                  reviewed_utc=datetime.now(timezone.utc).isoformat(),
                  ready=asset(SRC / 'DIAGNOSIS_READY.json'), source_inputs=len(sources['files']),
                  evidence_entries=len(evidence['files']), verified_unique_files=len(verified),
                  recomputed_saved_tensor_metrics=rows, original13_scalar_metrics_reproduced=True,
                  captured_activations_and_adjoints_byte_equal=exact_observations,
                  initialization_digest=initial['full']['initialization_sha256'],
                  post_init_rng_digest=initial['full']['post_init_rng_sha256'],
                  diagnosis_threading=dict(intraop=initial['full']['environment']['intraop'],
                                          interop=initial['full']['environment']['interop'],
                                          env=initial['full']['environment']['environment']),
                  full_sequence_and_two_prePG_rank_environments_equal=True,
                  pid_identity_evidence_gaps=pid_gaps,
                  float64_contractions_repeated=False, forward_backward_repeated=False,
                  metric_reader_torch=str(torch.__version__), metric_reader_threads=torch.get_num_threads(),
                  inputs=sorted(verified.values(), key=lambda row: row['path']))
    (OWN / 'EVIDENCE_REVIEW.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('inputs', 'recomputed_saved_tensor_metrics')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
