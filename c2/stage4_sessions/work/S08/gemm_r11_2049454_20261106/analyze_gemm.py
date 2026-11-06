"""Standalone R11 scalar-record analysis; no torch, BLAS, data or weights."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
PROTOCOL = 'ENGINEERING_REAL_CORPUS_GEMM5_V1'


def union_ns(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return sum(b-a for a, b in merged)


def boundary_totals(rows):
    result = {}
    for boundary in ('gemm', 'ctypes'):
        threads = defaultdict(list)
        for row in rows:
            threads[row['thread_id']].append((row[boundary+'_start_ns'], row[boundary+'_end_ns']))
        per_thread = [dict(thread_id=t, union_ns=union_ns(spans)) for t, spans in sorted(threads.items())]
        raw_sum = sum(r[boundary+'_wall_ns'] for r in rows)
        thread_sum = sum(t['union_ns'] for t in per_thread)
        result[boundary] = dict(raw_sum_ns=raw_sum, per_thread=per_thread,
            per_thread_union_sum_ns=thread_sum, same_thread_overlap_removed_ns=raw_sum-thread_sum,
            all_threads_coverage_ns=union_ns([p for spans in threads.values() for p in spans]))
    result['calls'] = len(rows)
    result['paired_difference_sum_ns'] = sum(r['outer_minus_ctypes_ns'] for r in rows)
    result['coverage_difference_ns'] = result['gemm']['all_threads_coverage_ns']-result['ctypes']['all_threads_coverage_ns']
    return result


def check_sample(sample, expected_calls=149):
    issues = []
    def check(condition, message):
        if not condition:
            issues.append(message)
    rows = sample['calls']; ids = {r['call_index']: r for r in rows}
    check(sample['protocol'] == PROTOCOL and sample['status'] == 'COMPLETE', 'protocol/status')
    check(sample['records'] == len(rows) == expected_calls and
          [r['call_index'] for r in rows] == list(range(1, expected_calls+1)), 'missing/duplicate call sequence')
    for r in rows:
        label = f"step{sample['step']} call{r['call_index']}: "
        a, b, out, native = r['a'], r['b'], r['output'], r['sgemm']
        check(r['step'] == sample['step'] and r['native_calls'] == 1 and r['status'] == 'COMPLETE', label+'one-to-one pair')
        check(r['thread_id'] == r['ctypes_thread_id'], label+'thread mismatch')
        g0, c0, c1, g1 = [r[k] for k in ('gemm_start_ns', 'ctypes_start_ns', 'ctypes_end_ns', 'gemm_end_ns')]
        check(all(type(x) is int for x in (g0, c0, c1, g1)) and g0 <= c0 <= c1 <= g1,
              label+'interval containment')
        check(r['gemm_wall_ns'] == g1-g0 and r['ctypes_wall_ns'] == c1-c0 and
              r['outer_minus_ctypes_ns'] == (g1-g0)-(c1-c0), label+'interval arithmetic')
        m, k = (a['shape'][1], a['shape'][0]) if r['ta'] else a['shape']
        bk, n = (b['shape'][1], b['shape'][0]) if r['tb'] else b['shape']
        check((m, n, k) == (r['m'], r['n'], r['k']) and k == bk and out['shape'] == [m, n], label+'dimensions')
        for name, tensor in (('a', a), ('b', b), ('output', out)):
            check(tensor['dtype'] == 'torch.float32' and tensor['contiguous'] is True and
                  tensor['stride'] == [tensor['shape'][1], 1], label+name+' dtype/stride')
        check(out['aliases_a_storage'] is False and out['aliases_b_storage'] is False, label+'output alias')
        expected_role = {('forward', False, True): 'forward', ('backward', False, False): 'dX',
                         ('backward', True, False): 'dW'}.get((r['linear_context'], r['ta'], r['tb']), 'UNKNOWN')
        check(r['role'] == expected_role and expected_role != 'UNKNOWN', label+'role/context/flags')
        expected = dict(layout=101, transa=112 if r['ta'] else 111, transb=112 if r['tb'] else 111,
            m=m, n=n, k=k, alpha=1.0, lda=a['shape'][1], ldb=b['shape'][1],
            beta=r['beta'] if out['is_given_out'] else 0.0, ldc=n)
        check(native == expected, label+'native parameters')
        seen = {r['call_index']}; node = r
        while node['parent_call_index'] is not None:
            parent_id = node['parent_call_index']
            if parent_id in seen or parent_id not in ids:
                check(False, label+'missing/cyclic parent'); break
            seen.add(parent_id); parent = ids[parent_id]
            check(parent['thread_id'] == node['thread_id'] and parent['gemm_start_ns'] <= node['gemm_start_ns'] and
                  parent['gemm_end_ns'] >= node['gemm_end_ns'], label+'parent thread/interval')
            node = parent
    return issues


def spread(values):
    return dict(min=min(values), median=statistics.median(values), max=max(values)) if values else None


def signature(row):
    return dict(role=row['role'], m=row['m'], n=row['n'], k=row['k'], ta=row['ta'], tb=row['tb'],
        requested_beta=row['beta'], given_out=row['output']['is_given_out'],
        a_shape=row['a']['shape'], b_shape=row['b']['shape'],
        a_stride=row['a']['stride'], b_stride=row['b']['stride'], native=row['sgemm'])


def grouped(rows, shape):
    buckets = defaultdict(list)
    for r in rows:
        key = json.dumps(signature(r) if shape else dict(role=r['role']), sort_keys=True)
        buckets[key].append(r)
    result = []
    for key, group in buckets.items():
        samples = [dict(step=step, **boundary_totals([r for r in group if r['step'] == step])) for step in (3, 4, 5)]
        result.append(dict(signature=json.loads(key), samples=samples,
            gemm_coverage_ns=spread([s['gemm']['all_threads_coverage_ns'] for s in samples]),
            ctypes_coverage_ns=spread([s['ctypes']['all_threads_coverage_ns'] for s in samples]),
            paired_difference_sum_ns=spread([s['paired_difference_sum_ns'] for s in samples]),
            per_call_ns={k: spread([r[k] for r in group]) for k in
                ('gemm_wall_ns', 'ctypes_wall_ns', 'outer_minus_ctypes_ns')},
            sources=[dict(step=r['step'], call_index=r['call_index']) for r in group]))
    result.sort(key=lambda r: r['ctypes_coverage_ns']['median'], reverse=True)
    for rank, row in enumerate(result, 1): row['rank_ctypes'] = rank
    for rank, row in enumerate(sorted(result, key=lambda r: r['gemm_coverage_ns']['median'], reverse=True), 1):
        row['rank_gemm'] = rank
    return result


def write(name, value):
    with (ROOT/name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')


def main():
    verification = json.loads((ROOT/'INPUT_VERIFICATION.json').read_text(encoding='utf-8'))
    assets = verification['assets']
    for a in assets.values():
        path = Path(a['path'])
        if path.suffix in ('.pt', '.npz'): raise ValueError('refuse data/weights')
        raw = path.read_bytes()
        if len(raw) != a['bytes'] or hashlib.sha256(raw).hexdigest() != a['sha256']:
            raise ValueError('input changed: '+str(path))
    def load(key): return json.loads(Path(assets[key]['path']).read_text(encoding='utf-8-sig'))
    h, result, contract = load('handoff'), load('application_result'), load('gemm_contract')
    if h['job_id'] != '2049454' or not h['protocol'] == result['protocol'] == PROTOCOL:
        raise ValueError('R11 job/protocol mismatch')
    rows, samples, issues = [], [], []
    for step in (3, 4, 5):
        asset = assets[f'sample_{step}']; sample = load(f'sample_{step}')
        issues.extend(check_sample(sample))
        if len(sample['calls']) > contract['limits']['max_records_each'] or asset['bytes'] > contract['limits']['max_bytes_each']:
            issues.append(f'step{step}: sampling limit')
        samples.append(dict(step=step, source=asset, **boundary_totals(sample['calls']),
            parent_calls=sum(r['parent_call_index'] is not None for r in sample['calls'])))
        for position, row in enumerate(sample['calls']):
            rows.append(dict(row, source=dict(**asset, json_pointer=f'/calls/{position}')))
    write('CALL_VALIDATION.json', dict(issues=issues, pairs=len(rows), samples=samples))
    if issues: raise ValueError('record checks failed; see CALL_VALIDATION.json')
    shape_ranking, role_ranking = grouped(rows, True), grouped(rows, False)
    ranks = {}
    for rank, r in enumerate(sorted(rows, key=lambda r: r['gemm_wall_ns'], reverse=True), 1):
        ranks[(r['step'], r['call_index'])] = rank
    call_ranking = []
    for rank, r in enumerate(sorted(rows, key=lambda r: r['ctypes_wall_ns'], reverse=True), 1):
        call_ranking.append(dict(rank_ctypes=rank, rank_gemm=ranks[(r['step'], r['call_index'])],
            step=r['step'], call_index=r['call_index'], thread_id=r['thread_id'],
            parent_call_index=r['parent_call_index'], signature=signature(r), source=r['source'],
            boundaries={k: r[k] for k in ('gemm_start_ns', 'gemm_end_ns', 'gemm_wall_ns',
                'ctypes_start_ns', 'ctypes_end_ns', 'ctypes_wall_ns', 'outer_minus_ctypes_ns')},
            observer_ns={k: r[k] for k in ('observer_before_ns', 'observer_after_ns', 'observer_sgemm_bookkeeping_ns')}))
    write('SHAPE_RANKING.json', dict(units='nanoseconds', ranking=shape_ranking))
    write('CALL_RANKING.json', dict(units='nanoseconds', ranking=call_ranking))
    summary = dict(status='GEMM_OBSERVATIONS_RECORDED', job_id='2049454', host=h['host'], protocol=PROTOCOL,
        pairs=len(rows), roles=role_ranking, samples=samples, application_timing=result['timing'],
        node_seconds=h['node_seconds'], shape_ranking='SHAPE_RANKING.json', call_ranking='CALL_RANKING.json',
        shape_groups=len(shape_ranking), issues=issues, native_kernel_time='UNKNOWN_CTYPES_NOT_PURE_KERNEL',
        in_step_observer_overhead='UNKNOWN_WITHOUT_MATCHED_CONTROL', scientific_acceptance=False,
        performance_acceptance=False, new_cluster_jobs=0, method='METHOD.md')
    write('GEMM_SUMMARY.json', summary)
    def ms(value): return f'{value/1e6:.6f}'
    lines = ['# R11 实际矩阵/角色排名', '',
        '按每采样同参数组ctypes区间覆盖中位排序，单位ms。两边界与差值独立统计；不可相加多个中位数当全程中位。全部native参数、逐调用范围/中位与447条来源索引在JSON。', '',
        '| rank ctypes/outer | role | m,n,k | ta/tb | beta | calls 3/4/5 | ctypes 3/4/5 ms | ctypes min/median/max | outer median | 差值 min/median/max |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in shape_ranking:
        a = row['signature']; n = a['native']; p = row['ctypes_coverage_ns']; d = row['paired_difference_sum_ns']
        lines.append(f"| {row['rank_ctypes']}/{row['rank_gemm']} | {a['role']} | {a['m']},{a['n']},{a['k']} | {a['ta']}/{a['tb']} | {n['beta']} | "+
            '/'.join(str(s['calls']) for s in row['samples'])+' | '+
            '/'.join(ms(s['ctypes']['all_threads_coverage_ns']) for s in row['samples'])+' | '+
            '/'.join(ms(p[k]) for k in ('min','median','max'))+' | '+ms(row['gemm_coverage_ns']['median'])+' | '+
            '/'.join(ms(d[k]) for k in ('min','median','max'))+' |')
    with (ROOT/'SHAPE_RANKING.md').open('x', encoding='utf-8') as stream: stream.write('\n'.join(lines)+'\n')
    print(json.dumps(dict(status=summary['status'], pairs=len(rows), shape_groups=len(shape_ranking), issues=issues)))


if __name__ == '__main__': main()
