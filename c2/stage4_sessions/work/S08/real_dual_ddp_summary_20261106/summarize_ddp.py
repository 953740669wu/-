"""S08 scalar-only adapter for the explicit REAL_DUAL_DOMAIN_DDP_V1 report schema."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
LEGACY = ROOT.parent/'overnight_engineering_20261105/summarize.py'
if hashlib.sha256(LEGACY.read_bytes()).hexdigest() != 'ff0f31bf5ff185327c8e6b1263ecb036b51e8b01900668d9516ac4e780f93bed':
    raise ValueError('frozen scalar helper identity drift')
spec = importlib.util.spec_from_file_location('s08_frozen_scalar_helpers', LEGACY)
legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
distribution, clean = legacy.distribution, legacy.clean
IDENTITY = ('job_id', 'run_id', 'ready_token', 'config_sha256', 'reference_ready_sha256',
            'source_manifest_sha256', 'descriptor_sha256')
TIMES = ('train_step_seconds', 'forward_seconds', 'backward_including_ddp_seconds',
         'optimizer_seconds', 'denominator_collective_seconds', 'log_and_state_sync_seconds',
         'reference_gate_wait_seconds', 'reference_seconds', 'diagnostic_seconds')


def accounting(ranks, steps, parent):
    def count(value, maximum):
        return value if type(value) is int and 0 <= value <= maximum else None
    physical = [count(r.get('completed_updates'), 25) for r in ranks]
    references = [count(r.get('reference_updates'), 5) for r in ranks]
    gates = [count(r.get('strict_gates_passed'), 5) for r in ranks]
    rank_sum = sum(physical) if all(x is not None for x in physical) else None
    ref_sum = sum(references) if all(x is not None for x in references) else None
    if all(x is not None for x in gates) and min(gates) == 5:
        stage = 'COMPLETE' if physical == [25, 25] else 'PARTIAL_OR_NOT_CONFIRMED'
    elif all(x is not None for x in physical+gates) and max(physical) <= 5:
        stage = 'NOT_RUN'
    else:
        stage = 'UNKNOWN'
    return dict(global_updates_parent_verified=count(parent.get('global_updates'), 25),
        rank_optimizer_updates_reported=physical, physical_rank_updates_reported=rank_sum,
        reference_updates_reported=ref_sum, reference_updates_by_rank_reported=references,
        physical_updates_including_reference_reported=rank_sum+ref_sum if rank_sum is not None and ref_sum is not None else None,
        fully_logged_step_counts=[len(x) for x in steps], strict_gates_passed_by_rank=gates,
        post_gate_updates_stage=stage, expected_maximum=dict(global_updates=25, physical_rank_updates=50, reference_updates=5, total=55))


def paired_steps(steps):
    issues, matched, slowest, frames, indices = [], 0, [], [], []
    for rank, rows in enumerate(steps):
        if [r.get('step') for r in rows] != list(range(1, len(rows)+1)):
            issues.append(f'rank{rank}: missing/duplicate/out-of-order logged steps')
    left = {r.get('step'): r for r in steps[0]}; right = {r.get('step'): r for r in steps[1]}
    if set(left) != set(right): issues.append('rank step sets differ')
    for step in sorted(set(left)&set(right)):
        a, b = left[step], right[step]
        if a.get('state_identity') and a['state_identity'] == b.get('state_identity'):
            matched += 1
        else:
            issues.append(f'step{step}: parameter/AdamW state hash missing/different')
        global_indices = a.get('global_indices', [])
        if (len(global_indices) != 64 or len(set(global_indices)) != 64 or global_indices != b.get('global_indices') or
            a.get('local_indices') != global_indices[:32] or b.get('local_indices') != global_indices[32:]):
            issues.append(f'step{step}: shard size/order/union/overlap mismatch')
        indices.extend(a.get('local_indices', [])+b.get('local_indices', []))
        pair_frames = a.get('frame_ids', [])+b.get('frame_ids', [])
        digest = hashlib.sha256(json.dumps(pair_frames, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if len(a.get('frame_ids', [])) != 32 or len(b.get('frame_ids', [])) != 32 or \
           any(r.get('global_frame_ids_sha256') != digest for r in (a, b)):
            issues.append(f'step{step}: global frame identity mismatch')
        frames.extend(pair_frames)
        if not a.get('global_mask_sha256') or a['global_mask_sha256'] != b.get('global_mask_sha256'):
            issues.append(f'step{step}: global mask identity missing/different')
        counts = a.get('global_counts')
        if (not isinstance(counts, list) or len(counts) != 2 or counts != b.get('global_counts') or
            counts != [a.get('local_masked', 0)+b.get('local_masked', 0), 64*256]):
            issues.append(f'step{step}: global denominators mismatch')
        losses = a.get('losses') or {}
        if losses != b.get('losses') or not all(legacy.number(losses.get(k)) for k in ('total', 'voltage', 'coarse')):
            issues.append(f'step{step}: global loss records missing/different')
        values = [r.get('train_step_seconds') for r in (a, b)]
        slowest.append(dict(step=step, max_observed_rank_call_seconds=max(values) if all(legacy.number(x) for x in values) else None))
    if len(indices) != len(set(indices)): issues.append('repeated global train indices across logged steps')
    keys = [(f.get('unit'), f.get('pair_index')) for f in frames]
    if len(keys) != len(set(keys)): issues.append('repeated actual frame IDs across logged steps')
    return dict(issues=issues, paired_logged_steps=len(set(left)&set(right)), matched_state_steps=matched,
        unique_logged_training_frames=len(set(keys)), max_rank_call_seconds=slowest,
        timing_scope='max local duration, not exact aligned global-step wall or sum of rank timings')


def analyze(directory, expected_job):
    directory = Path(directory).resolve(); inputs, missing, issues = {}, [], []
    def read(name, jsonl=False):
        path = directory/name
        try:
            if not path.resolve().is_relative_to(directory): raise ValueError('path outside explicit run root')
            raw = path.read_bytes(); inputs[name] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            if not raw.strip(): raise ValueError('empty artifact')
            if not jsonl: return json.loads(raw.decode('utf-8-sig'))
            rows = []
            for i, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
                try: rows.append(json.loads(line))
                except ValueError as exc: issues.append(f'{name} line{i}: {exc}')
            return rows
        except (OSError, ValueError) as exc:
            missing.append(dict(file=name, error=str(exc))); return [] if jsonl else {}
    manifest = read('manifest.json'); participants = read('participants.json'); parent = read('summary.json')
    ranks = [read(f'rank{rank}.json') for rank in range(2)]
    steps = [read(f'rank{rank}.steps.jsonl', True) for rank in range(2)]
    gates = read('gate_metrics.jsonl', True)
    supervisor_events = read('supervisor.events.jsonl', True)
    worker_events = [read(f'rank{rank}.events.jsonl', True) for rank in range(2)]
    if manifest.get('job_id') != expected_job: issues.append('manifest job differs from bound S00 handoff')
    if manifest.get('config', {}).get('protocol') != 'REAL_DUAL_DOMAIN_DDP_V1': issues.append('wrong/missing DDP protocol')
    for rank, report in enumerate(ranks):
        if any(report.get(k) != manifest.get(k) or report.get(k) is None for k in IDENTITY):
            issues.append(f'rank{rank}: current-run identity missing/different')
        pids = participants.get('pids', [])
        if report.get('rank') != rank or len(pids) != 2 or report.get('pid') != pids[rank]:
            issues.append(f'rank{rank}: participant rank/PID mismatch')
        if report.get('steps', []) != steps[rank]: issues.append(f'rank{rank}: embedded/logged steps differ')
    pair = paired_steps(steps); issues.extend(pair['issues'])
    gate_records = []
    for row in gates:
        metrics = row.get('metrics', []); failed = [m for m in metrics if m.get('passed') is not True]
        gate_records.append(dict(step=row.get('step'), metric_count=len(metrics), failed=failed,
            status='NO_METRICS_RECORDED' if not metrics else ('FAILED_ITEMS' if failed else 'RECORDED_ITEMS_PASSED')))
    exposure = {}
    for role in ('rank0', 'rank1', 'reference'):
        ledger = read(role+'.exposure.json')
        confirmed = [f for x in ledger.get('confirmed_updates', []) for f in x.get('frame_ids', [])]
        exposure[role] = dict(units=ledger.get('units'), confirmed_updates=len(ledger.get('confirmed_updates', [])) if ledger else None,
            confirmed_frame_observations=len(confirmed) if ledger else None,
            confirmed_unique_frames=len({(f.get('unit'), f.get('pair_index')) for f in confirmed}) if ledger else None,
            in_flight=ledger.get('in_flight', 'UNKNOWN'), recovery_probe=ledger.get('recovery_probe', 'UNKNOWN'))
    timing = []
    for rank, rows in enumerate(steps):
        phases = {}
        for name, chosen in (('first5_with_reference', [r for r in rows if r['step'] <= 5]),
                             ('after5_reference_released', [r for r in rows if r['step'] > 5])):
            phases[name] = dict(logged_steps=len(chosen), seconds={k: distribution([r.get(k) for r in chosen]) for k in TIMES},
                rss_bytes=distribution([r.get('rss_bytes') for r in chosen]),
                process_lifetime_hwm_bytes=distribution([r['process_lifetime_hwm_kib']*1024 if 'process_lifetime_hwm_kib' in r else None for r in chosen]))
        timing.append(dict(rank=rank, phases=phases, scope='HWM can retain earlier reference peak; timing components overlap and are not added'))
    rank_summaries = []
    for report in ranks:
        compact = {k: report.get(k) for k in (*IDENTITY, 'status', 'rank', 'pid', 'world_size', 'stage', 'error',
            'completed_updates', 'reference_updates', 'strict_gates_passed', 'local_consumed_frames',
            'global_cursor', 'initialization', 'normalization', 'recovery', 'cpu_receipt',
            'reference_observation_frames', 'recovery_probe_frames', 'module_identity')}
        compact['cpu_checkpoint_names'] = [c.get('name') for c in report.get('cpu_checkpoints', [])]
        compact['runtime'] = {k: report.get('runtime', {}).get(k) for k in
            ('backend', 'torch_threads', 'interop_threads', 'kml_gemm_calls', 'libraries', 'libraries_after')}
        rank_summaries.append(compact)
    begins = [r.get('monotonic_ns') for r in supervisor_events if r.get('event') == 'supervisor_begin']
    ends = [r.get('monotonic_ns') for r in supervisor_events if r.get('event') == 'supervisor_end']
    supervised_wall = (ends[0]-begins[0])/1e9 if len(begins) == len(ends) == 1 and \
        type(begins[0]) is int and type(ends[0]) is int and ends[0] >= begins[0] else None
    return clean(dict(status='DDP_RESULT_OBSERVATIONS', original_parent_status=parent.get('status'),
        expected_job=expected_job, inputs=inputs, missing_files=missing, issues=issues,
        accounting=accounting(ranks, steps, parent), paired_logged_checks=pair, gate_records=gate_records,
        rank_reports=rank_summaries, parent_report=parent, exposure=exposure, timing=timing,
        stages=dict(first5=[r.get('strict_gates_passed') for r in ranks],
            save_restore=[r.get('recovery', {'status': 'NOT_RUN_OR_UNKNOWN'}) for r in ranks]),
        supervisor_window_seconds=supervised_wall,
        supervisor_window_scope='supervisor begin through cleanup end, not training-only wall or full job wall',
        worker_errors=[dict(rank=rank, events=[r for r in events if r.get('event') == 'worker_error'])
            for rank, events in enumerate(worker_events)],
        speedup='NOT_MEASURED', scaling_efficiency='NOT_MEASURED', steady_state_gain='NOT_MEASURED',
        scientific_acceptance=False, performance_acceptance=False, new_cluster_jobs=0))


def markdown(value):
    a = value['accounting']
    lines = ['# 首次真实双域DDP工程摘要', '',
        f"job：{value['expected_job']}；原parent状态：{value['original_parent_status']}。", '',
        '以下实际数来自绑定原件；缺失为UNKNOWN。提速、扩展效率、稳态收益均NOT_MEASURED：本轮无同job单域25步对照。', '',
        '| 计数 | 实际记录 | 计划上限 |', '| --- | --- | --- |',
        f"| parent确认的全局更新 | {a['global_updates_parent_verified']} | 25 |",
        f"| 两rank已执行optimizer计数 | {a['rank_optimizer_updates_reported']} | 各25 |",
        f"| 两rank物理更新合计 | {a['physical_rank_updates_reported']} | 50 |",
        f"| 完整B64参考更新 | {a['reference_updates_reported']} | 5 |",
        f"| 物理更新含参考合计 | {a['physical_updates_including_reference_reported']} | 55 |",
        f"| 两rank完整逐步日志数 | {a['fully_logged_step_counts']} | 各25 |",
        f"| 两rank通过原严格门槛数 | {a['strict_gates_passed_by_rank']} | 各5 |", '',
        f"第6—25阶段：{a['post_gate_updates_stage']}。optimizer计数先于严格门槛持久化，不等于该步已通过全部数值/同步检查。", '',
        '| rank | 原状态/最后阶段 | 原错误 | 恢复 |', '| --- | --- | --- | --- |']
    for rank, report in enumerate(value['rank_reports']):
        lines.append(f"| {rank} | {report.get('status')} / {report.get('stage')} | {report.get('error')} | {report.get('recovery')} |")
    lines += ['', f"成对完整日志中的同步状态一致步数：{value['paired_logged_checks']['matched_state_steps']}；独特训练帧：{value['paired_logged_checks']['unique_logged_training_frames']}（仅这些完整日志的覆盖，不替代曝光账本）。", '',
        '原数值门槛记录：', '']
    for gate in value['gate_records']:
        lines.append(f"- step{gate['step']}：{gate['status']}，记录{gate['metric_count']}项，失败项{gate['failed']}。")
    lines += ['', '| 曝光角色 | 已确认更新 | 帧观察次数 | 已确认独特帧 | 中断可能曝光 |', '| --- | --- | --- | --- | --- |']
    for role, exposure in value['exposure'].items():
        lines.append(f"| {role} | {exposure['confirmed_updates']} | {exposure['confirmed_frame_observations']} | {exposure['confirmed_unique_frames']} | {exposure['in_flight']} |")
    lines += ['', '参考观察不计入新训练吞吐；已选/统计加载单位与NPZ/sidecar身份保留在JSON账本摘要，失败仍须按真实subject追溯排除最终test。', '',
        '| rank/阶段 | 完整日志步数 | 训练调用秒 min/median/max | RSS bytes | process-lifetime HWM bytes |',
        '| --- | --- | --- | --- | --- |']
    for rank in value['timing']:
        for phase, row in rank['phases'].items():
            lines.append(f"| {rank['rank']}/{phase} | {row['logged_steps']} | {row['seconds']['train_step_seconds']} | {row['rss_bytes']} | {row['process_lifetime_hwm_bytes']} |")
    lines += ['', f"监督器含清理窗口：{value['supervisor_window_seconds']}秒；不是纯训练或全job壁钟。每rank同步/等待/参考/诊断分项见JSON，部分范围嵌套，不累加父子/两rank时间冒充wall。", '',
        '参考释放后的HWM仍可能包含早期参考共存峰值，不称纯DDP训练峰值。零额外更新恢复仅按原记录转述；未到阶段NOT_RUN，不读权重补验。', '',
        f"原parent/清理：{value['parent_report']}。", '',
        f"缺失原件：{value['missing_files']}。", f"身份/一致性问题：{value['issues']}。", '',
        '两rank完整报告/失败、原门槛、同步、恢复和清理分列；不以exit0替代训练接受。无正式subject/split/val/test，不作科学或性能接受。源path/bytes/SHA、失败项与曝光细节见同名JSON；S08未训练/读NPZ或权重/提交集群。']
    return '\n'.join(lines).replace('None', 'UNKNOWN')+'\n'


if __name__ == '__main__':
    verified = json.loads((ROOT/'INPUT_VERIFICATION.json').read_text(encoding='utf-8'))
    if verified.get('all_passed') is not True: raise ValueError('actual S00 input verification required')
    for a in verified['assets'].values():
        path = Path(a['path'])
        if path.suffix in ('.pt', '.npz'): raise ValueError('weights/data not permitted')
        raw = path.read_bytes()
        if len(raw) != a['bytes'] or hashlib.sha256(raw).hexdigest() != a['sha256']: raise ValueError('bound input drift')
    value = analyze(verified['run_directory'], verified['job_id'])
    with (ROOT/'DDP_SUMMARY.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')
    with (ROOT/'DDP_SUMMARY.md').open('x', encoding='utf-8') as stream:
        stream.write(markdown(value))
    print(json.dumps(dict(status=value['original_parent_status'], issues=len(value['issues']), missing_files=len(value['missing_files']))))
