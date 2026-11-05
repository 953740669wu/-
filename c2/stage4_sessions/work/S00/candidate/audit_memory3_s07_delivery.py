"""Audit returned original data only; no model, compiler or communication run."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import zipfile

work = Path(__file__).resolve().parent.parent
root = work / 'evidence/memory3_s07_r2_20261105'
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
policy = runpy.run_path(str(work / 'candidate/s03_cpu36_contract_frozen.py'))
request = load(root / 'ROUND_REQUEST.json')
for name, row in request['protected_files'].items():
    p = work / name
    assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], name
jobs = {}
for kind, job_id, digest, count, size, archive, state, code, cpu, wall in [
    ('S02', '2039061', 'cd6be5d0aaf6a690524f465598f3a79df29c2b838ba35479437e4bce4d6f7613', 168, 320351,
     'S02_CKPT64_R6_CODE.zip', 'SUCCEEDED', 0, 38, 900),
    ('S07', '2039114', '6e3f10538532c3455e9a0f021466c16d25fa2b4968e81d31b8e39c0b9bab6563', 52, 83313,
     'S07_R2_VALIDATION.zip', 'FAILED', 1, 76, 300),
]:
    received = root / kind / 'received'
    bundle = root / ('JOB_' + job_id + '_full_evidence.zip')
    assert sha(bundle) == digest and bundle.stat().st_size == size
    with zipfile.ZipFile(bundle) as z:
        assert len(z.namelist()) == count and not any(n.endswith('.pt') for n in z.namelist())
    collection = load(received / 'COLLECTION_S00.json')
    assert collection['job_id'] == job_id and collection['changed_payload_files'] == []
    assert collection['retries'] == 0 and not collection['real_HBM'] and not collection['formal_training']
    assert collection['real_S07_probe'] is False
    for name, row in collection['files'].items():
        p = received / name
        assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], name
        assert type(row['mtime_ns']) is int and row['mtime_ns'] > 0
    pre = load(received / 'pre_submit_checks.json')
    assert pre['status'] == 'PASS_REMOTE_ORIGINAL_SHA_LF_LINUX_SYNTAX'
    assert pre['package_sha256'] == sha(work / 'execution_packages' / archive)
    assert all(sha(received / n) == h for n, h in pre['payload_files'].items())
    assert all(sha(received / n) == h for n, h in pre['wrapper_files'].items())
    with zipfile.ZipFile(work / 'execution_packages' / archive) as z:
        members = {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if not n.endswith('/')}
    expected = {('pair' + str(i) + '/payload/' + n): h for i in (1, 2, 3) for n, h in members.items()} if kind == 'S02' else {
        'payload/' + n: h for n, h in members.items()}
    assert expected == pre['payload_files'] and len(expected) == (84 if kind == 'S02' else 34)
    job = load(received / 'djob_final.json')['data']['successData'][0]
    assert str(job['jobId']) == job_id and job['state'] == state and job['jobExitCode'] == code
    assert job['jobWallClockLimit'] == wall and job['retryPolicy']['currentRetryTimes'] == job['retryPolicy']['maxRetryCnt'] == 0
    assert len(job['resGroups']) == 1
    group = job['resGroups'][0]
    assert group['resReq']['cpu'] == cpu and group['resReq']['mem'] == group['resLimit']['mem'] == 24576
    assert len(group['nodeResUsages']) == 1
    usage = group['nodeResUsages'][0]
    assert usage['pids'] == '-'
    elapsed = (datetime.fromisoformat(job['endTime'].replace('Z', '+00:00')) -
               datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))).total_seconds()
    jobs[kind] = dict(job_id=job_id, state=state, exit_code=code, host=usage['execNode'],
        start_utc=job['startTime'], end_utc=job['endTime'], elapsed_wall_seconds=elapsed,
        allocated_cores=cpu, scheduler_cpu_list=usage['hwThreads'], memory_MB=24576, wall_limit_seconds=wall,
        bundle_sha256=digest, bundle_bytes=size, file_count=count)

received = root / 'S02/received'
summary = load(received / 'job_evidence/SUMMARY.json')
assert summary['status'] == 'PASS_THREE_NEW_PAIRS_DDR_FIRST_STEP_DIAGNOSTIC_ONLY'
assert summary['job_id'] == '2039061' and summary['host'] == jobs['S02']['host']
assert len(summary['pairs']) == 3
strict = load(received / 'strict_reference_result.json')
assert strict['status'] == 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
assert len(strict['metrics']) == 1063 and strict['failures'] == [] and all(x['passed'] for x in strict['metrics'])
pairs, pids = [], []
for index in (1, 2, 3):
    payload = received / ('pair' + str(index)) / 'payload'
    out = payload / 'evidence/memory_2039061_ckpt64'
    gate = load(out / 'strict_gate.json')
    assert gate == load(received / ('memory_gate_before_submit_pair' + str(index) + '.json'))
    assert gate['sha256'] == sha(received / 'strict_reference_result.json')
    measured = []
    for ckpt in (0, 1):
        folder = out / ('ckpt' + str(ckpt))
        assert (folder / 'exit_code.txt').read_text().strip() == '0'
        d = load(folder / 'result.json')
        assert d['status'] == 'DDR_ONE_STEP_DIAGNOSTIC_ONLY_NOT_BENEFIT_ACCEPTANCE'
        assert d['config'] == dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
            checkpoint=bool(ckpt), history='fresh', precision='fp32', threads=36, loss='original_mean',
            hbm=False, training_steps=1, warmup_steps=0)
        assert d['case_identity'] == strict['case_identity'] and d['case_file_sha256'] == strict['case_file_sha256']
        assert d['case_file_bytes'] == 271979513 and d['optimizer_steps'] == 1
        assert d['parameter_counts'] == dict(enc=37995777, dec=29416449)
        assert d['checkpoint_wrapped_layers'] == ckpt * 12 and not d['comparison_snapshots_retained']
        assert d['initial_weights_released_before_training']
        assert all(sha(payload / n) == h for n, h in d['source_sha256'].items())
        cpu = d['cpu36']
        assert cpu['job_id'] == '2039061' and cpu['host'] == jobs['S02']['host'] and cpu['errors'] == []
        policy['validate_receipt'](cpu['receipt'])
        assert cpu['receipt']['allocated'] == policy['cpu_list'](jobs['S02']['scheduler_cpu_list'])
        assert len(cpu['receipt']['selected']) == 36 and len(cpu['receipt']['reserved']) == 2
        assert [c['name'] for c in cpu['checkpoints']] == ['before_framework', 'after_framework', 'after_backend',
            'initialized', 'before_training', 'after_training', 'publish']
        for checkpoint in cpu['checkpoints']:
            assert checkpoint['pid'] == cpu['pid']
            policy['validate_checkpoint'](checkpoint, cpu['receipt'])
        runtime = d['runtime']
        assert runtime['backend'] == 'kml' and runtime['torch_threads'] == 36
        assert runtime['kml_gemm_calls'] == (149 if ckpt == 0 else 197)
        assert {x['sha256'] for x in runtime['libraries']} == {x['sha256'] for x in runtime['libraries_after']}
        for label in ('initialization', 'training_start', 'training'):
            row = d[label]
            assert row['hugetlb_bytes'] == 0 and row['peak_rss_bytes'] >= row['rss_bytes'] > 0
            assert row['rss_MiB'] == row['rss_bytes'] / 2**20 and row['peak_rss_MiB'] == row['peak_rss_bytes'] / 2**20
        assert d['peak_reset']['available'] is True
        assert d['training_start']['peak_rss_bytes'] == d['training_start']['rss_bytes'] <= d['initialization']['peak_rss_bytes']
        assert 0 < d['training']['elapsed_seconds'] < 360
        pids.append(cpu['pid'])
        measured.append(dict(checkpoint=ckpt, pid=cpu['pid'], loss=d['loss'], initialization=d['initialization'],
            training_start=d['training_start'], peak_reset=d['peak_reset'], training=d['training'],
            kml_calls=runtime['kml_gemm_calls'], cpu_checkpoints=7))
    assert measured == summary['pairs'][index - 1]['measurements'] or all(
        all(m[k] == summary['pairs'][index - 1]['measurements'][i][k] for k in m) for i, m in enumerate(measured))
    pairs.append(dict(pair=index, measurements=measured))
assert len(set(pids)) == 6 and pids == summary['distinct_model_pids']
for step in summary['steps']:
    assert step['exit_code'] == (1 if step['label'] == 'libubsan_package' else 0)
    assert not step.get('timed_out') and step['remaining_live'] == [] and step['cleanup_actions'] == []
pre = load(received / 'pre_submit_checks.json')
after = load(received / 'case_identity_after.json')
assert after['sha256'] == pre['case_sha256'] and after['bytes'] == pre['case_bytes'] and after['mtime_ns'] == pre['case_mtime_ns']
stats = {}
for ckpt in (0, 1):
    rows = [p['measurements'][ckpt] for p in pairs]
    stats[str(ckpt)] = {}
    for key, values in [('training_peak_MiB', [m['training']['peak_rss_MiB'] for m in rows]),
                        ('training_end_RSS_MiB', [m['training']['rss_MiB'] for m in rows]),
                        ('training_seconds', [m['training']['elapsed_seconds'] for m in rows]),
                        ('initialization_peak_MiB', [m['initialization']['peak_rss_MiB'] for m in rows])]:
        stats[str(ckpt)][key] = dict(values=values, median=statistics.median(values), min=min(values), max=max(values))
jobs['S02'].update(status=summary['status'], pairs=pairs, statistics_new_three_only=stats, distinct_model_pids=pids)
old = load(work / 'evidence/r6_memory_ubsan_20261105/review.json')['jobs']['S02']
assert old['job_id'] == '2037434' and old['host'] == 'cn21339'

s07 = root / 'S07/received'
assert 'line 5: /etc/profile.d/donaukit_scheduler.sh: No such file or directory' in (s07 / 'job.log').read_text()
assert not (s07 / 'job_evidence').exists() and not (s07 / 'scheduler_allocation.json').exists()
assert not (s07 / 'payload/allocation.json').exists() and not (s07 / 'payload/environment_current.json').exists()
assert not (s07 / 'payload/checks_current_job').exists()
dependency = load(s07 / 'memory_dependency.json')
assert dependency['job_id'] == '2039061' and dependency['three_pairs_valid'] is True
assert dependency['summary_sha256'] == sha(received / 'job_evidence/SUMMARY.json')
assert dependency['terminal_sha256'] == sha(s07 / 'memory_dependency_terminal.json')
assert jobs['S02']['end_utc'] < jobs['S07']['start_utc']
jobs['S07'].update(status='BLOCKED_S00_WRAPPER_REQUIRES_LOGIN_ONLY_PROFILE_ON_COMPUTE',
    standard_library_tests='NOT_RUN', environment_check='NOT_RUN', communication_cases='NOT_RUN',
    per_rank_physical_domain_authority='NOT_REACHED', intended_selected_cores=72, actual_workers=0)
review = dict(status='COMPLETE_MEMORY3_DIAGNOSTIC_S07_STARTUP_FAILED_STOPPED', jobs=jobs,
    old_first_pair_separate=old, new_jobs=2, retries=0, real_HBM=False, UBSan_retry=False, formal_training=False,
    scientific_memory_benefit_acceptance=False, production_integration=False, old_protected_evidence_unchanged=True,
    node_seconds_this_round=sum(j['elapsed_wall_seconds'] for j in jobs.values()), clean_terminal_pids=True)
save = lambda p, d: p.write_text(json.dumps(d, indent=2) + '\n', encoding='utf-8')
save(root / 'review.json', review)
print(json.dumps({k: v for k, v in review.items() if k not in ('jobs', 'old_first_pair_separate')}, indent=2))
print(json.dumps(stats, indent=2))
