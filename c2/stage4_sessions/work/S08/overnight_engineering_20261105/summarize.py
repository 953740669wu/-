"""Read one explicit engineering evidence directory; never load data or weights."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

PROTOCOL = 'ENGINEERING_REAL_CORPUS_PILOT_V1'
SUCCESS = 'ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE'
MANIFEST_SHA = 'bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032'
INTERFACE_SHA = '8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669'
ROOT = Path(__file__).resolve().parent
FLAGS = dict(protocol=PROTOCOL, engineering_only=True, formal_split_status='UNKNOWN',
             validation_status='NOT_RUN_NO_FORMAL_SPLIT', subject_mapping_status='UNKNOWN')
TIMING = ('wall_seconds', 'data_loading_seconds', 'batch_materialization_seconds',
          'training_step_seconds', 'diagnostic_seconds', 'checkpoint_and_recovery_seconds',
          'unattributed_seconds')


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def mapping(value):
    return value if isinstance(value, dict) else {}


def distribution(values):
    valid = [x for x in values if number(x)]
    return dict(observed=len(valid), missing_or_invalid=len(values)-len(valid),
                min=min(valid) if valid else None, median=statistics.median(valid) if valid else None,
                max=max(valid) if valid else None)


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def analyze(evidence_dir, run_subdir='.', ledger_relative_path='EXPOSURE_LEDGER.json'):
    root = Path(evidence_dir).resolve()
    issues, inputs = [], {}

    def read(name):
        path = root/name
        try:
            if not path.resolve().is_relative_to(root):
                raise ValueError('input escapes explicit evidence directory')
            raw = path.read_bytes()
            inputs[name] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            return raw.decode('utf-8-sig')
        except (OSError, ValueError, UnicodeError) as exc:
            issues.append(f'{name}: {exc}')
            return None

    def obj(name):
        raw = read(name)
        try:
            value = json.loads(raw) if raw is not None else {}
            if not isinstance(value, dict):
                raise ValueError('expected JSON object')
            return value
        except (ValueError, TypeError) as exc:
            issues.append(f'{name}: {exc}')
            return {}

    def check(condition, message):
        if not condition:
            issues.append(message)

    run = Path(run_subdir)
    result = obj(str(run/'result.json'))
    ledger = obj(ledger_relative_path)
    runner = obj(str(run/'runner_status.json')) if (root/run/'runner_status.json').exists() else None
    raw = read(str(run/'steps.jsonl'))
    steps = []
    for line, text in enumerate((raw or '').splitlines(), 1):
        try:
            row = json.loads(text)
            if not isinstance(row, dict):
                raise ValueError('expected step object')
            steps.append(row)
        except ValueError as exc:
            issues.append(f'steps.jsonl line {line}: {exc}; line retained as a gap')
    raw_exit = read(str(run/'exit_code.txt'))
    try:
        exit_code = int(raw_exit.strip()) if raw_exit is not None else None
    except ValueError:
        exit_code = None
    check(exit_code == 0, f'exit_code is {exit_code!r}, expected explicit 0')
    if runner is not None:
        issues.append('runner_status.json present: retain timeout/runner evidence; no completion inference')
    for key, value in FLAGS.items():
        check(result.get(key) == value, f'result.{key}: missing or outside engineering protocol')
    check(result.get('status') == SUCCESS, f'run status: {result.get("status", "MISSING")}')
    for key in ('source', 'data_identity', 'config', 'exposure_ledger'):
        check(isinstance(result.get(key), dict) and bool(result[key]), f'result.{key}: missing object')
    identity = mapping(result.get('data_identity'))
    manifest = mapping(mapping(identity.get('corpus')).get('manifest'))
    check(manifest.get('sha256') == MANIFEST_SHA, 'data_identity corpus manifest: missing or SOURCE_MISMATCH')
    check(identity.get('interface_sha256') == INTERFACE_SHA, 'data_identity interface: missing or SOURCE_MISMATCH')
    check(result.get('source_and_data_after') == 'PASS_SAME_FROZEN_IDENTITIES',
          'source/data after-run identity check missing or failed')
    for key in ('planned_updates', 'completed_updates', 'consumed_frames', 'stop_reason'):
        check(key in result, f'result.{key}: missing')
    check([s.get('step') for s in steps] == list(range(1, len(steps)+1)) and bool(steps),
          'step sequence missing, duplicated or out of order')
    check(result.get('completed_updates') == len(steps), 'completed_updates differs from logged steps')
    check(result.get('planned_updates') == result.get('completed_updates') and bool(steps),
          'planned updates not completed or unknown')
    check(len(steps) <= 200, 'update cap exceeded')
    embedded = result.get('steps')
    check(isinstance(embedded, list) and len(embedded) == len(steps), 'result.steps count missing or inconsistent')
    frames, frame_keys, rss, peaks, cursor = [], [], [], [], 0
    for index, row in enumerate(steps):
        label = f'step record {index+1}'
        for key in ('step', 'batch_size', 'frame_indices', 'frame_ids', 'masked_elements', 'mask_sha256',
                    'losses', 'loader_seconds', 'step_seconds', 'diagnostic_seconds', 'rss_before',
                    'rss_after', 'rss_peak_scope', 'kml_calls', 'adamw_step', 'cursor'):
            check(key in row, f'{label}.{key}: missing')
        batch = row.get('batch_size')
        ids = row.get('frame_ids')
        indices = row.get('frame_indices')
        check(type(batch) is int and 1 <= batch <= 64, f'{label}: invalid batch size')
        check(isinstance(ids, list) and len(ids) == batch, f'{label}: frame IDs/count mismatch')
        check(isinstance(indices, list) and len(indices) == batch, f'{label}: frame indices/count mismatch')
        if type(batch) is int and batch > 0:
            cursor += batch
        check(row.get('cursor') == cursor and row.get('adamw_step') == index+1,
              f'{label}: cursor/continuous AdamW mismatch')
        check(row.get('rss_peak_scope') == 'process_lifetime', f'{label}: RSS scope missing/wrong')
        for key in ('loader_seconds', 'step_seconds', 'diagnostic_seconds', 'kml_calls', 'masked_elements'):
            check(number(row.get(key)), f'{label}.{key}: missing/nonfinite/negative')
        check(number(row.get('kml_calls')) and row['kml_calls'] > 0, f'{label}: no actual KML calls')
        losses = mapping(row.get('losses'))
        for key in ('total', 'voltage', 'coarse'):
            check(number(losses.get(key)), f'{label}.losses.{key}: missing/nonfinite/negative')
        if all(number(losses.get(k)) for k in ('total', 'voltage', 'coarse')):
            check(math.isclose(losses['total'], losses['voltage']+losses['coarse'], rel_tol=1e-5, abs_tol=1e-7),
                  f'{label}: total loss differs from component sum')
        for key in ('rss_before', 'rss_after'):
            memory = mapping(row.get(key))
            check(number(memory.get('rss_bytes')) and number(memory.get('peak_rss_bytes')),
                  f'{label}.{key}: RSS/HWM missing or invalid')
            rss.append(memory.get('rss_bytes')); peaks.append(memory.get('peak_rss_bytes'))
        if isinstance(ids, list):
            frames.extend(ids)
            frame_keys.extend(json.dumps([mapping(f).get(k) for k in ('case', 'unit', 'pair_index')]) for f in ids)
        if isinstance(embedded, list) and index < len(embedded):
            check(embedded[index] == row,
                  f'{label}: result.steps differs from steps.jsonl')
    check(len(set(frame_keys)) == len(frame_keys), 'duplicate actual frame IDs')
    check(result.get('consumed_frames') == len(frames), 'consumed_frames differs from logged frame IDs')
    for key in ('protocol', 'engineering_only', 'formal_split_status', 'subject_mapping_status'):
        check(ledger.get(key) == FLAGS[key], f'exposure ledger.{key}: missing or inconsistent')
    units = ledger.get('units') if isinstance(ledger.get('units'), list) else []
    check(bool(units), 'exposure ledger.units missing/empty; exposure unknown, conservative exclusion review required')
    for unit in units:
        check(isinstance(unit, dict) and all(unit.get(k) for k in
              ('case', 'unit', 'npz_sha256', 'sidecar_sha256', 'usage_status')), 'exposure ledger: unit fields missing')
    ledger_by_unit = {u['unit']: u for u in units if isinstance(u, dict) and isinstance(u.get('unit'), str)}
    coverage = Counter()
    for frame in frames:
        frame = mapping(frame)
        unit = ledger_by_unit.get(frame.get('unit'), {})
        check(bool(unit) and all(frame.get(k) == unit.get(k) for k in
              ('case', 'unit', 'npz_sha256', 'sidecar_sha256')),
              'frame/ledger source identity missing or mismatched')
        check(frame.get('belt') == '16_adjacent' and frame.get('subject_id') is None and
              type(frame.get('pair_index')) is int, 'frame belt/subject/row metadata missing or inconsistent')
        coverage[(str(frame.get('case', 'UNKNOWN')), str(frame.get('unit', 'UNKNOWN')))] += 1
    check(not frames or all(ledger_by_unit.get(mapping(f).get('unit'), {}).get('usage_status') ==
          'CONSUMED_CONFIRMED' for f in frames), 'logged frames lack confirmed ledger exposure; preserve conservative review')
    check(not ledger.get('in_flight'), 'interrupted in-flight update: possible exposure requires conservative exclusion review')
    cpu = result.get('cpu36') if isinstance(result.get('cpu36'), dict) else {}
    runtime = result.get('runtime') if isinstance(result.get('runtime'), dict) else {}
    check(cpu.get('errors') == [] and bool(cpu.get('checkpoints')), 'CPU36 evidence missing or errors reported')
    check(runtime.get('backend') == 'kml' and runtime.get('torch_threads') == 36 and
          bool(runtime.get('libraries')) and bool(runtime.get('kml_resolved')), 'KML/thread/library evidence missing or inconsistent')
    checkpoint = result.get('checkpoint') if isinstance(result.get('checkpoint'), dict) else {}
    check(all(checkpoint.get(k) for k in ('path', 'bytes', 'sha256')), 'checkpoint path/bytes/SHA missing')
    recovery = result.get('recovery') if isinstance(result.get('recovery'), dict) else {}
    check(recovery.get('status') == 'PASS_NO_EXTRA_UPDATE' and recovery.get('extra_updates') == 0,
          'zero-extra-update checkpoint recovery missing or failed')
    timing = result.get('timing') if isinstance(result.get('timing'), dict) else {}
    for key in TIMING:
        check(number(timing.get(key)), f'timing.{key}: unknown/nonfinite/negative')
    cpu_summary = {k: cpu.get(k) for k in ('version', 'pid', 'job_id', 'host', 'receipt', 'errors')}
    checkpoints = cpu.get('checkpoints') if isinstance(cpu.get('checkpoints'), list) else []
    cpu_summary['checkpoints'] = [{k: mapping(c).get(k) for k in
        ('name', 'pid', 'calling_affinity', 'torch_intraop', 'torch_interop')} for c in checkpoints]
    runtime_summary = {k: runtime.get(k) for k in ('backend', 'host', 'python', 'torch_threads',
        'interop_threads', 'kml_gemm_calls', 'kml_resolved', 'kml_ops_file', 'libraries', 'libraries_after', 'env')}
    return clean(dict(summary_status='EVIDENCE_GAPS' if issues else 'ENGINEERING_OBSERVATIONS_RECORDED',
        evidence_kind=result.get('evidence_kind', 'SUPPLIED_RUN_EVIDENCE'),
        evidence_dir=str(root), protocol=PROTOCOL, interface_sha256=INTERFACE_SHA,
        scientific_acceptance='NOT_PERFORMED', validation_status='NOT_RUN_NO_FORMAL_SPLIT',
        run_status=result.get('status'), exit_code=exit_code, error=result.get('error'), runner_status=runner,
        stop_reason=result.get('stop_reason'), inputs=inputs, issues=issues,
        source=result.get('source'), data_identity=result.get('data_identity'),
        observations=dict(logged_steps=len(steps), planned_updates=result.get('planned_updates'),
            completed_updates=result.get('completed_updates'), observed_frame_count=len(frames),
            unique_frame_ids=len(set(frame_keys)),
            step_seconds=distribution([s.get('step_seconds') for s in steps]),
            rss_bytes=distribution(rss), hwm_bytes=distribution(peaks), rss_scope='process_lifetime',
            sample_coverage=[dict(case=k[0], unit=k[1], confirmed_logged_frames=n) for k, n in sorted(coverage.items())],
            loss_ranges={k: distribution([mapping(s.get('losses')).get(k) for s in steps])
                         for k in ('voltage', 'coarse', 'total')}),
        timing={k: timing.get(k) if number(timing.get(k)) else None for k in TIMING},
        cpu36=cpu_summary, runtime=runtime_summary, checkpoint=checkpoint, recovery=recovery,
        exposure=dict(ledger=ledger, usage_counts=dict(Counter(u.get('usage_status', 'UNKNOWN')
            for u in units if isinstance(u, dict))),
            future_test_policy='Resolve real subjects and exclude exposed subjects from final test; no current leakage guarantee'),
        steps=steps))


def markdown(value):
    obs = value['observations']
    lines = ['# 工程训练观察（非科学/性能验收）', '', f"证据类型：{value['evidence_kind']}。", '',
        f"状态：{value['summary_status']}；原始运行状态：{value['run_status']}；退出码：{value['exit_code']}。",
        '无正式 val/test；缺失值均为未知。RSS/HWM 为 process-lifetime，不代表逐步独占内存。', '',
        f"记录步数 {obs['logged_steps']}；声明更新数 {obs['completed_updates']}；实际记录帧 {obs['observed_frame_count']}。",
        f"步耗时秒（min/median/max）：{obs['step_seconds']}。",
        f"RSS bytes：{obs['rss_bytes']}；HWM bytes：{obs['hwm_bytes']}。", '',
        '| step | batch | voltage | coarse | total | step s | loader s | diagnostic s |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in value['steps']:
        losses = mapping(row.get('losses'))
        cells = [row.get('step'), row.get('batch_size'), losses.get('voltage'), losses.get('coarse'),
                 losses.get('total'), row.get('step_seconds'), row.get('loader_seconds'), row.get('diagnostic_seconds')]
        lines.append('| '+' | '.join('UNKNOWN' if c is None else str(c) for c in cells)+' |')
    lines += ['', '实际记录的样本覆盖（case 不代表不同 subject）：', '',
              '| case | unit | logged frames |', '| --- | --- | --- |',
              *[f"| {r['case']} | {r['unit']} | {r['confirmed_logged_frames']} |"
                for r in obs['sample_coverage']], '', '整体计时（秒；不推算加速百分比）：', '',
              *[f'- {k}: {v if v is not None else "UNKNOWN"}' for k, v in value['timing'].items()], '',
              f"CPU36 报错：{value['cpu36'].get('errors', 'UNKNOWN')}；检查点数：{len(value['cpu36'].get('checkpoints', []))}。",
              f"KML：{value['runtime'].get('backend', 'UNKNOWN')}；Torch threads：{value['runtime'].get('torch_threads', 'UNKNOWN')}；调用数：{value['runtime'].get('kml_gemm_calls', 'UNKNOWN')}。",
              f"checkpoint 声明：{value['checkpoint']}；恢复声明：{value['recovery']}。",
              f"暴露使用状态计数：{value['exposure']['usage_counts']}。",
              '以上为运行证据转述；不加载权重，不独立复核线程实现。完整帧顺序、来源、库路径/SHA和暴露清单见同名 JSON。', '',
              '缺项/失败（均保留）：', '', *['- '+s for s in value['issues']]]
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--run-subdir', default='.', help='explicit result/steps/exit subdirectory within evidence-dir')
    parser.add_argument('--ledger-relative-path', default='EXPOSURE_LEDGER.json', help='explicit ledger path within evidence-dir')
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('output must stay inside this S08 task directory')
    if output.is_relative_to(args.evidence_dir.resolve()):
        parser.error('output must be separate from read-only evidence')
    value = analyze(args.evidence_dir, args.run_subdir, args.ledger_relative_path)
    output.mkdir(parents=True, exist_ok=True)
    for name, text in (('SUMMARY.json', json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n'),
                       ('SUMMARY.md', markdown(value))):
        with (output/name).open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(json.dumps(dict(summary_status=value['summary_status'], issues=len(value['issues']))))
    raise SystemExit(2 if value['issues'] else 0)
