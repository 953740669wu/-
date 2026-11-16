"""Verify exact returned identities, then count only completed updates inside each window."""
from contextlib import redirect_stdout
from io import StringIO
import json
from statistics import median
import sys

from datetime import datetime
from hashlib import sha256
from pathlib import Path
import shlex
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'aggressive_3h_20261111'))
import review_job
review_job.HERE = HERE
unpack, read = review_job.main, review_job.read


def lines(path):
    return [json.loads(row) for row in path.read_bytes().splitlines()]


def arm_metrics(root, arm, binding, topology, job):
    phase = root / arm
    window = read(phase / 'WINDOW.json')
    start, end = window['open_ns'], window['close_ns']
    assert end - start == 600 * 10**9
    receipt = read(phase / 'phase_receipt.json')
    assert receipt['status'] == 'PASS_FIXED_WINDOW' and receipt['job_id'] == job
    assert receipt['window'] == window and set(receipt['domains']) == set(topology['contracts'])
    releases = {int(p.stem):read(p) for p in (phase/'barriers').glob('*.release')}
    assert set(releases) == set(range(1,7)) and releases[6]['release_at_ns'] == start
    assert all(int(p.name.split('.')[0]) <= 6 for p in (phase/'barriers').glob('*.ready'))
    pairing = read(root.parent / 'PRIOR_PAIRING.json')
    domains = {}
    for node, contract in topology['contracts'].items():
        d = phase / f'node{node}'
        result, rows = read(d/'result.json'), lines(d/'steps.jsonl')
        assert result['status'] == 'PASS_FIXED_WINDOW' and result['job_id'] == job
        assert result['host'] == topology['context']['host'] and result['window'] == window
        assert len(rows) == result['completed_updates'] == receipt['domains'][node] and len(rows) >= 5
        assert [r['step'] for r in rows] == list(range(1,len(rows)+1))
        assert result['checkpoint_layers'] == binding['checkpoint_layers'][arm]
        use_tail = arm == 'B' and int(node) in binding['mixed_profile']['tail_domains']
        assert result['profile_domain'] == int(node)
        assert result['checkpoint_scope'] == ('full_tail_skip' if use_tail else 'full')
        if use_tail:
            assert result['checkpoint_tail_counts'] == dict(skipped=12*len(rows),escaped=0)
        else:
            assert result.get('checkpoint_tail_counts') is None
        assert result['hbm_min_request_KiB'] == binding['hbm_min_request_KiB'][arm]
        guard = result['cpu36']
        assert not guard['errors'] and guard['receipt'] == contract
        for check in guard['checkpoints']:
            assert check['snapshot']['complete'] and check.get('torch_intraop',36) == 36
            assert all(t['affinity'] and set(t['affinity']) <= set(contract['selected']) for t in check['snapshot']['threads'])
        assert len(result['metrics']) == 15 and all(m['passed'] for m in result['metrics'])
        hbm = result['hbm_allocator']
        assert hbm['sha256'] == binding['allocator_sha256'] and hbm['cap_MiB'] == 3800
        assert hbm['node'] == topology['hbm_pairs'][node]
        ledger = read(d/'EXPOSURE_LEDGER.json')
        assert not ledger['in_flight'] and len(ledger['confirmed_updates']) == len(rows)
        for row in rows:
            step = row['step']; slot = (step-1) % 25
            assert row['sequence_slot'] == slot+1 and row['sequence_cycle'] == (step-1)//25
            assert row['frame_indices'] == pairing['order'][slot*32:(slot+1)*32]
            assert row['mask_sha256'] == pairing['mask_sha256'][slot]
            assert row['batch_size'] == 32 and row['native_sgemm_calls'] == (185 if use_tail else 197)
            assert row['start_ns'] < row['end_ns']
            assert abs(row['step_seconds'] - (row['end_ns']-row['start_ns'])/1e9) < 1e-9
            assert 0 < row['rss_after']['hugetlb_bytes'] <= 3800*2**20
            if step <= 6:
                release = releases[step]
                assert str(release['arrivals'][node]['pid']) == str(result['pid'])
                assert row['release_ns'] == release['release_at_ns'] <= row['start_ns']
            else:
                assert row['release_ns'] is None
        assert all(row['end_ns'] <= start for row in rows[:5])
        assert all(start <= row['start_ns'] < end for row in rows[5:])
        waits = result['barrier_waits']
        assert [w['step'] for w in waits] == list(range(1,7))
        inside = [row for row in rows[5:] if row['end_ns'] <= end]
        cross = [row for row in rows[5:] if row['end_ns'] > end]
        assert len(cross) <= 1
        domains[node] = dict(completed_in_window=len(inside), frame_visits=32*len(inside),
                            frames_s=32*len(inside)/600, completed_updates=len(rows),
                            worker_started_ns=result['started_ns'], worker_finished_ns=result['finished_ns'],
                            warmup_step_seconds=[r['step_seconds'] for r in rows[:5]],
                            pure_train_median_s=median(r['step_seconds'] for r in inside) if inside else None,
                            observed_peak_estimate_MiB=max((r['rss_after']['peak_rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows),
                            cross_window_steps=[dict(step=r['step'],seconds=r['step_seconds'],after_close_s=(r['end_ns']-end)/1e9) for r in cross],
                            metrics_checked=len(result['metrics']))
    total = sum(d['frame_visits'] for d in domains.values())
    assert sum(d['completed_updates'] for d in domains.values()) <= receipt['updates_reserved'] <= 2000
    first = min(d['worker_started_ns'] for d in domains.values())
    last = max(d['worker_finished_ns'] for d in domains.values())
    assert first < start < end < last
    return dict(window=window, domains=domains, frame_visits=total, frames_s=total/600,
                updates_reserved=receipt['updates_reserved'],
                startup_and_warmup_s=(start-first)/1e9,
                post_window_worker_finish_s=(last-end)/1e9,
                worker_envelope_s=(last-first)/1e9,
                tail_after_window_s=max((x['after_close_s'] for d in domains.values() for x in d['cross_window_steps']),default=0))


def main(job, digest):
    version = 'R20_MIXED_TAIL_WINDOW'
    with redirect_stdout(StringIO()): unpack(version, job, digest)
    root = HERE/version; received = root/'received'; evidence = received/'job_evidence'
    report = read(root/'REVIEW.json'); binding = read(root/'RUN_BINDING.json')
    native, = read(received/'djob_final.json')['data']['successData']
    group, = native['resGroups']; node, = group['nodeResUsages']
    assert native['user'] == 'wujunyi' and native['exclusive'] is True
    assert native['execPath'] == binding['remote_root'] and native['jobWallClockLimit'] == 7200
    assert node['execNode'] == 'cn22035' and node['pids'] == '-'
    assert group['resReq']['cpu'] == group['resAlloc']['cpu'] == 608
    assert group['resReq']['mem'] == group['resAlloc']['mem'] == group['resLimit']['mem'] == 393216
    assert read(received/'FIXED_INPUTS_BEFORE.json') == read(received/'FIXED_INPUTS_AFTER.json')
    pin = sha256((root/'RUN_BINDING.json').read_bytes()).hexdigest()
    argv = [pin if a == 'BINDING_SHA256' else a for a in binding['native_argv']]
    assert shlex.split(native['cmd']) == argv[argv.index('bash'):]
    for name, expected in binding['frozen_sidecars'].items():
        if (received/name).exists():
            assert sha256((received/name).read_bytes()).hexdigest() == expected
        else:
            meta = read(received/'COLLECTION_INDEX.json')['files'][name]
            assert not meta['archive'] and meta['sha256'] == expected
    profile = read(received/'PROFILE_GATE.json')
    strict = read(received/'STRICT16_REVIEW.json')
    assert profile == binding['mixed_profile']
    assert profile['tail_domains'] == [i for i in range(16) if i != 4]
    assert profile['original_domains'] == [4] and strict['cleanup_passed']
    assert all(strict['domains'][f'node{i}']['strict5_passed'] for i in profile['tail_domains'])
    assert all(d['phases']['baseline']['passed'] for d in strict['domains'].values())
    topology = read(evidence/'domain_map.json')
    assert len(topology['contracts']) == 16 and len(topology['context']['allowed']) == 608
    assert all(len(r['allocated']) == 38 and len(r['selected']) == 36 and len(r['reserved']) == 2 for r in topology['contracts'].values())
    report['arms'] = {}
    for arm in ('A','B'):
        if (evidence/arm/'phase_receipt.json').exists():
            report['arms'][arm] = arm_metrics(evidence, arm, binding, topology, job)
    budget = read(evidence/'update_budget_cleanup.json')
    assert budget['removed'] and all(0 <= v <= 2000 for v in budget['reservations'].values())
    report['reserved_updates'] = sum(budget['reservations'].values())
    if native['state'] == 'SUCCEEDED':
        assert report['summary']['completed_arms'] == ['A','B'] and set(report['arms']) == {'A','B'}
        assert all(read(evidence/f'pool_return_{arm}.json')['passed'] for arm in ('A','B','terminal'))
        a, b = report['arms']['A'], report['arms']['B']
        assert a['window']['close_ns'] < b['window']['open_ns']
        for n in topology['contracts']:
            for x,y in zip(lines(evidence/f'A/node{n}/steps.jsonl'),lines(evidence/f'B/node{n}/steps.jsonl')):
                assert all(x[k] == y[k] for k in ('step','frame_indices','frame_ids','mask_sha256'))
        report['comparison'] = dict(throughput_change_pct=100*(b['frames_s']/a['frames_s']-1),
                                    delta_frames_s=b['frames_s']-a['frames_s'],
                                    per_domain_delta_frames_s={n:b['domains'][n]['frames_s']-a['domains'][n]['frames_s'] for n in a['domains']})
    recorded = charged = 0
    report['partial_domains'] = {}
    for arm in ('A','B'):
        for node in topology['contracts']:
            d = evidence/arm/f'node{node}'
            rows = lines(d/'steps.jsonl') if (d/'steps.jsonl').exists() else []
            ledger = read(d/'EXPOSURE_LEDGER.json') if (d/'EXPOSURE_LEDGER.json').exists() else {}
            charge = len(ledger.get('confirmed_updates',[])) + bool(ledger.get('in_flight'))
            recorded += len(rows); charged += charge
            report['partial_domains'][arm+'/'+node] = dict(recorded=len(rows),charged=charge)
    elapsed = lambda a,b: (datetime.fromisoformat(native[b].replace('Z','+00:00'))-datetime.fromisoformat(native[a].replace('Z','+00:00'))).total_seconds()
    report.update(recorded_updates=recorded,charged_updates=charged,
        allocation_seconds=elapsed('startTime','endTime'),queue_seconds=elapsed('createTime','startTime'),
        cleanup_passed=report['cleanup']['all_reaped'] and report['summary']['hbm_pool_restored'],
        fixed_inputs_before_after_equal=True)
    (root/'REVIEW.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('job_id','native_state','reserved_updates','comparison') if k in report},indent=2))


if __name__ == '__main__': main(*sys.argv[1:])
