"""Read the SHA-bound R12 A/B metadata; no data, weights, torch or cluster."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
PROTOCOL = 'ENGINEERING_DW_TILES_R12_AB_V1'


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def median_change_percent(baseline, candidate):
    if not positive(baseline) or not positive(candidate):
        raise ValueError('positive finite medians required')
    return (candidate/baseline-1)*100


def perf_statistics(steps):
    if len(steps) != 25 or [x['step'] for x in steps] != list(range(1, 26)) or \
       [x['adamw_step'] for x in steps] != list(range(1, 26)) or \
       any(x['sampled'] is not (x['step'] > 5) for x in steps):
        raise ValueError('exactly25 updates, warmup1..5, observed6..25 required')
    times = [x['step_seconds'] for x in steps]
    if not all(positive(x) for x in times):
        raise ValueError('nonfinite/nonpositive step timing')
    if any(x['rss_peak_scope'] != 'process_lifetime' for x in steps):
        raise ValueError('RSS scope unknown/different')
    memory = [x[k] for x in steps for k in ('rss_before', 'rss_after')]
    if not all(positive(x[k]) for x in memory for k in ('rss_bytes', 'peak_rss_bytes')):
        raise ValueError('memory samples missing/nonfinite')
    observed = times[5:]
    return dict(all25_seconds=times, warmup5_seconds=times[:5], observed20_seconds=observed,
        observed20_count=20, observed20_median_seconds=statistics.median(observed),
        observed20_range_seconds=[min(observed), max(observed)], all25_training_seconds=sum(times),
        memory_samples=len(memory), sampled_process_lifetime_hwm_bytes=max(x['peak_rss_bytes'] for x in memory),
        sampled_process_lifetime_hwm_MiB=max(x['peak_rss_bytes'] for x in memory)/2**20,
        sampled_rss_range_bytes=[min(x['rss_bytes'] for x in memory), max(x['rss_bytes'] for x in memory)])


def main():
    identity = json.loads((ROOT/'INPUT_VERIFICATION.json').read_text(encoding='utf-8'))
    assets = identity['assets']
    def load(name):
        return json.loads(Path(assets[name]['path']).read_text(encoding='utf-8-sig'))
    def hashes():
        return {key: len(raw := Path(a['path']).read_bytes()) == a['bytes'] and
                hashlib.sha256(raw).hexdigest() == a['sha256'] for key, a in assets.items()}
    if any(Path(a['path']).suffix in ('.pt', '.npz') for a in assets.values()):
        raise ValueError('refuse weights/corpus')
    if not all(hashes().values()): raise ValueError('bound input drift')
    handoff = load('handoff'); coordinator = load('coordination_review')
    results = {phase: load(phase+'_result') for phase in handoff['phase_order']}
    checks = {}
    def check(name, value): checks[name] = bool(value)
    check('job_and_protocol', handoff['job_id'] == '2049894' and handoff['protocol'] == PROTOCOL and
        all(r['job_id'] == '2049894' and r['host'] == 'cn21338' for r in results.values()) and
        all(results[p]['protocol'] == PROTOCOL for p in ('strict', 'perf_baseline', 'perf_candidate')))
    expected = dict(target='PASS_ACTUAL_KML_TARGET_ONLY', strict='PASS_STRICT_ENCODER5',
        perf_baseline='PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE', perf_candidate='PERF25_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE')
    check('phase_status', all(results[p]['status'] == status for p, status in expected.items()))
    for phase, count in (('target', 1), ('strict', 3895), ('perf_baseline', 15), ('perf_candidate', 15)):
        metrics = results[phase]['metrics']
        check(phase+'_numeric_record', len(metrics) == count and all(m['passed'] is True and
            m['max_abs'] == m['l2_relative'] == 0 for m in metrics))
    baseline, candidate = results['perf_baseline'], results['perf_candidate']
    stats = {}
    for role, result in (('baseline', baseline), ('candidate', candidate)):
        phase = 'perf_'+role
        raw_steps = [json.loads(line) for line in Path(assets[phase+'_steps']['path']).read_text().splitlines()]
        check(role+'_result_matches_steps', result['steps'] == raw_steps)
        stats[role] = perf_statistics(raw_steps)
        check(role+'_role_and_full_epoch', result['variant'] == role and result['completed_updates'] ==
            result['planned_updates'] == result['optimizer_updates_total'] == 25 and result['consumed_frames'] == 1600 and
            all(x['role'] == role and x['batch_size'] == 64 for x in raw_steps))
        check(role+'_call_counts', all(x['kml_calls'] == 149 and x['native_sgemm_calls'] ==
            (149 if role == 'baseline' else 161) and x['target_logical_gemm'] == 12 and
            x['target_native_full'] == (12 if role == 'baseline' else 0) and
            x['target_native_tiles'] == (0 if role == 'baseline' else 24) and
            x['dispatch_hits'] == (0 if role == 'baseline' else 12) for x in raw_steps))
        check(role+'_source_descriptor', result['source_manifest_sha256'] == handoff['source_bindings']['code_source_manifest_sha256'] and
            result['descriptor_sha256'] == handoff['source_bindings']['descriptor_sha256'])
        check(role+'_training_total', math.isclose(stats[role]['all25_training_seconds'],
            result['timing']['training_step_seconds'], rel_tol=1e-12))
        check(role+'_wall_components', math.isclose(sum(v for k, v in result['timing'].items() if k != 'wall_seconds'),
            result['timing']['wall_seconds'], rel_tol=1e-12))
        memory_key = 'process_lifetime_HWM_MiB'
        check(role+'_handoff_statistics', math.isclose(stats[role]['observed20_median_seconds'],
            handoff['performance'][role]['observed20_median_seconds'], rel_tol=1e-12) and
            stats[role]['observed20_range_seconds'] == handoff['performance'][role]['observed20_range_seconds'] and
            stats[role]['sampled_process_lifetime_hwm_MiB'] == handoff['performance'][role][memory_key])
        recovery = result['recovery']
        check(role+'_recovery_record', recovery['status'] == 'PASS_NO_EXTRA_UPDATE' and recovery['extra_updates'] == 0 and
            all(recovery[k] for k in ('parameters_exact', 'optimizer_exact', 'rng_exact', 'cursor_exact', 'identity_exact')) and
            all(m['passed'] and m['max_abs'] == m['l2_relative'] == 0 for m in recovery['forward_metrics']))
        ledger = load(phase+'_ledger')
        check(role+'_exposure_and_coverage', len({(f['unit'], f['pair_index']) for x in raw_steps for f in x['frame_ids']}) == 1600 and
            len(ledger['confirmed_updates']) == 25 and ledger['in_flight'] is None and all(
            a['frame_ids'] == b['frame_ids'] and a['frame_indices'] == b['frame_indices']
            for a, b in zip(raw_steps, ledger['confirmed_updates'])))
        stats[role].update(timing=result['timing'], recovery=result['recovery'],
            source_result=assets[phase+'_result'], source_steps=assets[phase+'_steps'],
            process_pid=result['pid'], checkpoint=result['checkpoint'], variant=role)
    check('independent_perf_processes_same_host', baseline['pid'] != candidate['pid'] and baseline['host'] == candidate['host'])
    check('matched_initialization', baseline['initialization']['baseline'] == candidate['initialization']['candidate'])
    check('matched_statistics', baseline['normalization'] == candidate['normalization'])
    check('matched_frames_masks', all(all(a[k] == b[k] for k in ('frame_indices', 'frame_ids', 'mask_sha256'))
        for a, b in zip(baseline['steps'], candidate['steps'])))
    check('matched_runtime_libraries', all(baseline['runtime'][k] == candidate['runtime'][k] for k in
        ('backend', 'python', 'torch', 'torch_file', 'torch_threads', 'interop_threads', 'env', 'libraries')))
    cp_count = 0
    for phase, result in results.items():
        cpu = result['cpu36']; cp = cpu['checkpoints']; cp_count += len(cp)
        selected = set(cpu['receipt']['selected'])
        check(phase+'_CPU36', len(selected) == 36 and cpu['errors'] == [] and all(
            c['snapshot']['complete'] and not c['snapshot']['errors'] and all(set(t['affinity']) <= selected
            for t in c['snapshot']['threads']) for c in cp))
    strict = results['strict']
    check('60_full_updates', strict['completed_updates'] == 5 and strict['optimizer_updates_total'] == 10 and
        strict['optimizer_updates_total']+baseline['optimizer_updates_total']+candidate['optimizer_updates_total'] == 60)
    check('139_CPU_snapshots', cp_count == 139)
    change = median_change_percent(stats['baseline']['observed20_median_seconds'], stats['candidate']['observed20_median_seconds'])
    check('percent_crosscheck', math.isclose(change, handoff['candidate_observed20_median_change_percent'], rel_tol=1e-12) and
        math.isclose(change, coordinator['candidate_observed20_median_time_change_percent'], rel_tol=1e-12))
    check('no_gain_disposition', change > 0 and coordinator['decision'] == 'R12_CLOSED_NO_TRAINING_GAIN')
    check('engineering_scope', all(r['engineering_only'] is True and r['formal_split_status'] ==
        r['subject_mapping_status'] == 'UNKNOWN' and r['validation_status'] == 'NOT_RUN_NO_FORMAL_SPLIT'
        for r in (strict, baseline, candidate)))
    post_hashes = hashes(); check('all_inputs_unchanged', all(post_hashes.values()))
    validation = dict(checked_utc=datetime.now(timezone.utc).isoformat(), checks=checks,
        all_passed=all(checks.values()), post_analysis_input_hashes=post_hashes,
        local_fixture_tests=4, new_cluster_jobs=0, weights_or_data_read=False)
    (ROOT/'VALIDATION.json').write_text(json.dumps(validation, indent=2)+'\n', encoding='utf-8')
    if not validation['all_passed']: raise ValueError('crosscheck failed; see VALIDATION.json')
    overlap = [max(stats[r]['observed20_range_seconds'][0] for r in stats),
               min(stats[r]['observed20_range_seconds'][1] for r in stats)]
    summary = dict(status='AB_SUMMARY_COMPLETE', disposition='R12_CLOSED_NO_TRAINING_GAIN',
        job_id='2049894', host='cn21338', protocol=PROTOCOL, performance_pairs=1,
        phase_order=handoff['phase_order'], numerical_scope=dict(target_metrics=1, strict_metrics=3895,
            perf_first5_baseline_metrics=15, perf_first5_candidate_metrics=15, recorded_max_abs=0, full_model_updates=60),
        performance=stats, candidate_observed20_median_time_change_percent=change,
        observed20_ranges_overlap_seconds=overlap if overlap[0] <= overlap[1] else None,
        cpu_snapshots=cp_count, strict_phase_timing=strict['timing'],
        node_seconds=handoff['node_seconds'], application_timing_scope='Separate processes, sequential phases; not total job wall',
        memory_scope='50 before/after update samples per independent perf process across same25 updates; process-lifetime HWM at sample time, not exclusive step memory or whole-job final peak',
        conclusion='No training speed or memory decrease observed in this single same-node pair; retain original baseline, no candidate integration, no stable-regression claim',
        limitations=['One sequential baseline/candidate pair, not repeated trials', 'Observed step ranges overlap',
            'No formal split/val/test or scientific/production performance acceptance', 'Checkpoints remote only; S08 did not read or recompute weights'],
        original_evidence_modified=False, scientific_acceptance=False, performance_acceptance=False,
        candidate_integrated=False, new_cluster_jobs=0, source_verification='INPUT_VERIFICATION.json',
        validation='VALIDATION.json')
    with (ROOT/'AB_SUMMARY.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=summary['status'], checks=len(checks), median_change_percent=change)))


if __name__ == '__main__': main()
