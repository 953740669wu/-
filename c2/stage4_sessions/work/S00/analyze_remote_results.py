"""Recompute historical timings; never promote missing exit/provenance evidence to acceptance."""
import csv
import json
import math
from pathlib import Path
import re
import statistics as st

WORK = Path(__file__).resolve().parent
SPECS = {'node16_sync_kmlfp32': (16, 3), 'node16_b32_membind': (16, 3),
         'node16_b32_hbm': (16, 2), 'die4_b32_ddr': (4, 1),
         'die4_b32_hbm': (4, 1), 'node16_b64ckpt_hbm': (16, 2)}


def analyze_round(files, round_id, expected_domains, belt, part):
    selected = [(int(m[2]), f) for f in files
                if (m := re.fullmatch(r'r(\d+)_d(\d+)\.json', f['name']))
                and int(m[1]) == round_id]
    domains = [d for d, _ in selected]
    missing = sorted(set(range(expected_domains)) - set(domains))
    issues, rates, steps, peaks = [], [], [], []
    if missing:
        issues.append('missing domains: ' + str(missing))
    if len(set(domains)) != len(domains) or set(domains) - set(range(expected_domains)):
        issues.append('duplicate or unexpected domain IDs')
    configs = {json.dumps({key: f['data'].get(key) for key in ('device', 'torch', 'cases', 'config')}, sort_keys=True)
               for _, f in selected}
    if len(configs) > 1:
        issues.append('configuration mismatch')
    prefix = 'pretrain' if part == 'pre' else 'decoder'
    for domain, f in selected:
        result = f['data'].get(belt, {})
        batch = f['data'].get('config', {}).get('batch')
        rate, step = result.get(prefix + '_frames_per_s'), result.get(prefix + '_step_s_B' + str(batch))
        if not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in (rate, step)):
            issues.append('invalid/missing timing domain ' + str(domain))
            continue
        if not math.isclose(rate, batch / step, rel_tol=1e-12):
            issues.append('step/rate mismatch domain ' + str(domain))
        if not f.get('stable_after_read') or 'log' not in f:
            issues.append('unstable snapshot or missing log domain ' + str(domain))
        if any(any(term in line.lower() for term in ('traceback', 'killed', 'bus error', 'memoryerror', 'timeout'))
               for line in f.get('log', {}).get('errors', [])):
            issues.append('failure marker domain ' + str(domain))
        rates.append(rate)
        steps.append(step)
        peaks.append(result['peak_mem_GB'])
    complete = not issues and len(rates) == expected_domains
    return dict(round=round_id, belt=belt, part=part, expected_domains=expected_domains,
        json_count=len(selected), timing_count=len(rates), missing_domains=missing, issues=issues,
        payload_complete=complete, observed_sum_fps=sum(rates) if rates else None,
        complete_node_sum_fps=sum(rates) if complete else None,
        min_domain_fps=min(rates) if rates else None, median_domain_fps=st.median(rates) if rates else None,
        conservative_fps=expected_domains * min(rates) if complete else None,
        median_step_s=st.median(steps) if steps else None, slowest_step_s=max(steps) if steps else None,
        peak_mem_legacy_GB_max=max(peaks) if peaks else None,
        exit_status='NOT_RECORDED', runtime_input_and_library_hashes='NOT_RECORDED',
        formal_acceptance=False)


def build_tables(evidence):
    domains, rounds, stability = [], [], []
    for tag, (expected, count) in SPECS.items():
        files = evidence['reports'][tag]['files']
        for f in files:
            m = re.fullmatch(r'r(\d+)_d(\d+)\.json', f['name'])
            if not m:
                continue
            for belt in ('16_adjacent', '32_skip4'):
                for part, prefix in [('pre', 'pretrain'), ('dec', 'decoder')]:
                    result, cfg = f['data'][belt], f['data']['config']
                    domains.append(dict(tag=tag, round=int(m[1]), domain=int(m[2]), belt=belt, part=part,
                        batch=cfg['batch'], amp=cfg['amp'], threads=f['data']['gpu'],
                        step_s=result[prefix + '_step_s_B' + str(cfg['batch'])],
                        frames_per_s=result[prefix + '_frames_per_s'],
                        peak_mem_legacy_GB=result['peak_mem_GB'], source_json_sha256=f['sha256']))
        for belt in ('16_adjacent', '32_skip4'):
            for part in ('pre', 'dec'):
                group = []
                for round_id in range(1, count + 1):
                    row = dict(tag=tag, **analyze_round(files, round_id, expected, belt, part))
                    rounds.append(row)
                    if row['payload_complete']:
                        group.append(row)
                values = [g['complete_node_sum_fps'] for g in group]
                spread = (max(values) - min(values)) / st.mean(values) if values else None
                stability.append(dict(tag=tag, belt=belt, part=part, complete_payload_rounds=len(values),
                    sums_fps=values, spread_of_complete_payloads=spread,
                    three_round_payload_spread_pass=len(values) >= 3 and spread <= .05,
                    formal_acceptance=False, reason='Per-domain exits and runtime fingerprints were not recorded; this is historical payload analysis only.'))
    return domains, rounds, stability


def main():
    evidence = json.loads((WORK / 'evidence/remote_details.json').read_text(encoding='utf-8'))
    domains, rounds, stability = build_tables(evidence)
    for name, rows in [('remote_domain_measurements', domains), ('remote_round_measurements', rounds)]:
        with (WORK / ('evidence/' + name + '.csv')).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (WORK / 'evidence/remote_recomputed.json').write_text(json.dumps(
        dict(rounds=rounds, stability=stability), indent=2) + '\n', encoding='utf-8')
    lines = ['# 历史逐域JSON重新计算', '',
             '仅核查历史payload；未记录逐域退出码／运行时哈希，不作为性能正式接受。缺域行的observed sum仅供诊断。', '',
             '| tag | belt/part | round | JSON/expected | 完整域合计fps | 诊断合计fps | min/median fps | N×min fps | median/slowest step s | legacy RSS max |',
             '|---|---|---|---|---|---|---|---|---|---|']
    def fmt(value):
        return '-' if value is None else '%.4f' % value
    for row in rounds:
        lines.append('| %s | %s/%s | %s | %s/%s | %s | %s | %s/%s | %s | %s/%s | %s |' % (
            row['tag'], row['belt'], row['part'], row['round'], row['json_count'], row['expected_domains'],
            fmt(row['complete_node_sum_fps']), fmt(row['observed_sum_fps']), fmt(row['min_domain_fps']),
            fmt(row['median_domain_fps']), fmt(row['conservative_fps']), fmt(row['median_step_s']),
            fmt(row['slowest_step_s']), fmt(row['peak_mem_legacy_GB_max'])))
    (WORK / 'evidence/remote_measurement_table.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('domain rows', len(domains), 'round/workload rows', len(rounds))
    for row in stability:
        print(row['tag'], row['belt'], row['part'], 'complete', row['complete_payload_rounds'],
              'sum', [round(v, 4) for v in row['sums_fps']], 'spread', row['spread_of_complete_payloads'])


if __name__ == '__main__':
    main()
