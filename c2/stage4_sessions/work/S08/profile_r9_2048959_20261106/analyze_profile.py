"""Read only the SHA-bound R9 spans; no torch, data, weights or cluster access."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
PHASES = ('zero_grad_before', 'forward_loss', 'zero_grad_after', 'backward', 'optimizer')
KML = 'S02/KML_python_gemm_envelope'


def union_us(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end-start for start, end in merged)


def contains(parent, child):
    return (parent['pid'], parent['tid']) == (child['pid'], child['tid']) and \
        parent['ts'] <= child['ts']+1e-6 and \
        parent['ts']+parent['dur'] >= child['ts']+child['dur']-1e-6


def copy_owner(names, phase):
    if KML in names:
        return 'inside_KML_envelope'
    if '_LinearFn' in names:
        return '_LinearFn_forward_boundary'
    if '_LinearFnBackward' in names:
        return '_LinearFnBackward_boundary'
    if 'ViewBackward0' in names:
        return 'ViewBackward_reshape_path'
    if any('flash_attention' in n and 'backward' in n.lower() for n in names):
        return 'attention_backward_path'
    if 'aten::native_layer_norm_backward' in names:
        return 'layer_norm_backward_path'
    return 'optimizer_path' if phase == 'optimizer' else 'other_observed_ancestors'


def attribute_trace(events):
    issues = []
    valid = []
    for e in events:
        if e.get('ph') != 'X' or not isinstance(e.get('args'), dict) or \
           'event_id' not in e['args'] or any(type(e.get(k)) not in (int, float) or
           not math.isfinite(e[k]) for k in ('ts', 'dur')) or e['dur'] < 0:
            issues.append('invalid or unsupported span; not assigned')
        else:
            valid.append(e)
    ids = {e['args']['event_id']: e for e in valid}
    if len(ids) != len(valid):
        issues.append('duplicate event_id; ownership not accepted as complete')
    phase_spans = [e for e in valid if e['name'] in ['S02/'+p for p in PHASES]]
    for phase in PHASES:
        if sum(e['name'] == 'S02/'+phase for e in phase_spans) != 1:
            issues.append('missing/duplicate phase marker: '+phase)
    kml, copies = [], []
    for event in valid:
        if event['name'] not in (KML, 'aten::copy_'):
            continue
        chain, reasons, seen, node = [], [], set(), event
        while node['args'].get('parent_id') is not None:
            parent_id = node['args']['parent_id']
            if parent_id in seen or parent_id not in ids:
                reasons.append('missing/cyclic parent')
                break
            seen.add(parent_id)
            parent = ids[parent_id]
            if not contains(parent, node):
                reasons.append('parent/thread/interval mismatch')
            chain.append(parent)
            node = parent
        ancestors = [p for p in chain if p in phase_spans]
        candidates = [p for p in phase_spans if contains(p, event)]
        if len(ancestors) != 1 or len(candidates) != 1 or \
           ancestors[0]['args']['event_id'] != candidates[0]['args']['event_id']:
            reasons.append('phase ancestry and interval not uniquely consistent')
        phase = ancestors[0]['name'][4:] if not reasons else 'UNKNOWN'
        if reasons:
            issues.append(f"event {event['args']['event_id']}: "+'; '.join(reasons))
        names = [p['name'] for p in chain]
        record = dict(event_id=event['args']['event_id'], parent_id=event['args'].get('parent_id'),
            pid=event['pid'], tid=event['tid'], start_us=event['ts'], end_us=event['ts']+event['dur'],
            duration_us=event['dur'], phase=phase, ancestor_names=names,
            ancestor_ids=[p['args']['event_id'] for p in chain], unknown_reasons=reasons)
        if event['name'] == KML:
            record['owner'] = '_LinearFnBackward' if '_LinearFnBackward' in names else \
                ('_LinearFn' if '_LinearFn' in names else 'UNKNOWN')
            kml.append(record)
        else:
            record['owner'] = copy_owner(names, phase) if not reasons else 'UNKNOWN'
            copies.append(record)

    def groups(records, by_chain=False):
        buckets = defaultdict(list)
        for row in records:
            key = (row['phase'], row['pid'], row['tid'], row['owner'],
                   tuple(row['ancestor_names']) if by_chain else ())
            buckets[key].append(row)
        result = []
        for (phase, pid, tid, owner, chain), rows in sorted(buckets.items()):
            intervals = [(r['start_us'], r['end_us']) for r in rows]
            raw_sum = sum(r['duration_us'] for r in rows)
            union = union_us(intervals)
            result.append(dict(phase=phase, pid=pid, tid=tid, owner=owner, calls=len(rows),
                raw_duration_sum_us=raw_sum, union_us=union, overlap_removed_us=raw_sum-union,
                ancestor_names=list(chain), example_event_ids=[r['event_id'] for r in rows[:3]]))
        return result
    if not kml:
        issues.append('missing KML envelopes')
    return dict(issues=issues, trace_spans=len(valid),
        threads=[dict(pid=p, tid=t) for p, t in sorted({(e['pid'], e['tid']) for e in valid})],
        phase_spans=[dict(name=e['name'], pid=e['pid'], tid=e['tid'],
            event_id=e['args']['event_id'], start_us=e['ts'], duration_us=e['dur']) for e in phase_spans],
        kml_groups=groups(kml), copy_groups=groups(copies, by_chain=True), kml_index=kml,
        copy_owner_groups=groups(copies),
        shape_metadata='UNKNOWN_NO_PER_CALL_SHAPES_IN_CAPTURE',
        native_kernel_time='UNKNOWN_PYTHON_ENVELOPES_ONLY')


def spread(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values)) if values else None


def main():
    verification = json.loads((ROOT/'INPUT_VERIFICATION.json').read_text(encoding='utf-8'))
    assets = verification['assets']
    for asset in assets.values():
        path = Path(asset['path'])
        if path.suffix in ('.pt', '.npz'):
            raise ValueError('refuse weights or corpus')
        raw = path.read_bytes()
        if len(raw) != asset['bytes'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise ValueError('bound input changed: '+str(path))
    def load(key):
        return json.loads(Path(assets[key]['path']).read_text(encoding='utf-8-sig'))
    handoff, result, contract = load('handoff'), load('application_result'), load('profile_contract')
    if handoff['job_id'] != '2048959' or result['protocol'] != 'ENGINEERING_REAL_CORPUS_PROFILE5_V1':
        raise ValueError('R9 job/protocol mismatch; never use the PILOT parser')
    steps = result['steps']; samples = []; issues = []
    limits = contract['profiling']
    for step in (3, 4, 5):
        trace = load(f'traces_{step}'); averages = load(f'events_{step}')
        parsed = attribute_trace(trace['traceEvents'])
        profile = steps[step-1]['profile']
        kml_count = sum(g['calls'] for g in parsed['kml_groups'])
        checks = dict(event_count_matches=len(trace['traceEvents']) == averages['events'] == profile['events'],
            event_count_limit=len(trace['traceEvents']) <= limits['max_events_per_sample'],
            kml_count_matches=kml_count == profile['kml_markers'] == 149,
            kml_marker_limit=kml_count <= limits['max_kml_markers_per_sample'],
            trace_byte_limit=assets[f'traces_{step}']['bytes'] <= limits['trace_bytes_each'],
            summary_byte_limit=assets[f'events_{step}']['bytes'] <= limits['summary_bytes_each'],
            copy_count_matches=sum(g['calls'] for g in parsed['copy_groups']) ==
                next(x['calls'] for x in averages['top_self_cpu'] if x['key'] == 'aten::copy_'),
            phase_wall_close=all(abs(next(x['duration_us'] for x in parsed['phase_spans']
                if x['name'] == 'S02/'+p)/1e6-profile['phase_seconds'][p]) < 0.001 for p in PHASES))
        issues.extend(f'step {step}: {x}' for x in parsed['issues'])
        issues.extend(f'step {step}: {k}' for k, value in checks.items() if not value)
        samples.append(dict(step=step, checks=checks, trace=assets[f'traces_{step}'],
            event_summary=assets[f'events_{step}'], events=averages['events'], distinct_keys=averages['distinct_keys'],
            exported_top_keys=len(averages['top_self_cpu']), top_self_cpu=averages['top_self_cpu'],
            attribution={k: v for k, v in parsed.items() if k != 'kml_index'}, kml_index=parsed['kml_index']))
    keys = list(dict.fromkeys(x['key'] for sample in samples for x in sample['top_self_cpu'][:10]))
    ranking = []
    for key in keys:
        observations = []
        for sample in samples:
            pair = next(((i, x) for i, x in enumerate(sample['top_self_cpu'], 1) if x['key'] == key), None)
            observations.append(dict(step=sample['step'], rank=pair[0], **pair[1]) if pair else
                dict(step=sample['step'], rank=None, self_cpu_us=None, calls=None))
        ranking.append(dict(key=key, samples=observations,
            self_cpu_us=spread([x['self_cpu_us'] for x in observations if x['self_cpu_us'] is not None])))
    ranking.sort(key=lambda x: x['self_cpu_us']['median'], reverse=True)
    phases = [{k: row['profile'][k] for k in ('step', 'sampled', 'phase_seconds',
        'instrumented_step_seconds', 'profiler_setup_start_seconds', 'profiler_stop_seconds',
        'profiler_postprocess_export_seconds', 'profiler_outside_step_seconds')} for row in steps]
    summary = dict(status='PROFILE_OBSERVATIONS_WITH_GAPS' if issues else 'PROFILE_OBSERVATIONS_RECORDED',
        job_id='2048959', host=handoff['host'], protocol=result['protocol'], issues=issues,
        phase_wall_seconds=phases,
        sampled_phase_wall_seconds={p: spread([x['phase_seconds'][p] for x in phases if x['sampled']]) for p in PHASES},
        application_timing=result['timing'], node_seconds=handoff['node_seconds'],
        top_self_cpu_comparison=ranking, samples=[{k: v for k, v in s.items() if k != 'kml_index'} for s in samples],
        unknowns=dict(native_kml_kernel_time='UNKNOWN', per_call_matrix_shapes='UNKNOWN_NOT_CAPTURED',
            actual_source_tensors_of_copies='UNKNOWN_NO_SHAPES_STACKS_OR_TENSOR_IDS',
            in_step_profiler_overhead='UNKNOWN_WITHOUT_MATCHED_CONTROL'),
        scientific_acceptance=False, performance_acceptance=False, new_cluster_jobs=0,
        source_verification='INPUT_VERIFICATION.json', method='METHOD.md')
    for name, value in (('PROFILE_SUMMARY.json', summary), ('ATTRIBUTION_INDEX.json',
        dict(job_id='2048959', units='microseconds', samples=[dict(step=s['step'], trace=s['trace'],
            kml_index=s['kml_index']) for s in samples]))):
        with (ROOT/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=summary['status'], issues=issues,
        groups=[dict(step=s['step'], kml=s['attribution']['kml_groups'],
        copy=s['attribution']['copy_owner_groups']) for s in samples]), ensure_ascii=False))


if __name__ == '__main__':
    main()
