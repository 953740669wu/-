"""Validate archived memory evidence and summarize steps; no training rerun."""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import zipfile

s00 = Path(__file__).resolve().parents[1]
request = json.loads((s00 / 'tmp/CURRENT_MEMORY5_ROUND.json').read_bytes())
root = Path(request['local_evidence'])
received = root / 'received'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_bytes())
receipt = load(root / 'JOB_2040363_receipt.json')
bundle = root / 'JOB_2040363_full_evidence.zip'
assert bundle.stat().st_size == receipt['bytes'] and sha(bundle) == receipt['sha256']
with zipfile.ZipFile(bundle) as z:
    assert len(z.namelist()) == receipt['file_count'] == 66
    assert all(z.read(n) == (received / n).read_bytes() for n in z.namelist())
collection = load(received / 'COLLECTION_S00.json')
assert len(collection['files']) == 65 and collection['source_unchanged'] is True
for name, info in collection['files'].items():
    p = received / name
    assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256']
    assert isinstance(info['mtime_ns'], int) and info['mtime_ns'] > 0
pre = load(received / 'pre_submit_checks.json')
assert len(pre['payload_files']) == 24
for name, digest in pre['payload_files'].items(): assert sha(received / name) == digest
assert sha(received / 'sequence5_memory_once.py') == pre['execution_file_sha256']
assert sha(received / 'S02_SEQUENCE5_R7_CODE.zip') == request['package_sha256']
with zipfile.ZipFile(received / 'S02_SEQUENCE5_R7_CODE.zip') as z:
    assert len(z.namelist()) == 24
    assert all(z.read(n) == (received / 'payload' / n).read_bytes() for n in z.namelist())
for label in ('case', 'strict'):
    after = load(received / (label + '_identity_after.json'))
    assert after == pre[label]
assert sha(received / 'strict_reference_result.json') == request['strict_sha256'] == pre['strict']['sha256']
assert load(received / 'sequence_gate_before_submit.command.json')['exit_code'] == 0
job = load(received / 'djob_final.json')['data']['successData'][0]
assert str(job['jobId']) == '2040363' and job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0
assert job['jobWallClockLimit'] == 900 and len(job['resGroups']) == 1
assert job['retryPolicy']['maxRetryCnt'] == job['retryPolicy']['currentRetryTimes'] == 0
group = job['resGroups'][0]
assert group['resReq']['cpu'] == 38 and group['resReq']['mem'] == group['resLimit']['mem'] == 24576
assert len(group['nodeResUsages']) == 1
node = group['nodeResUsages'][0]
assert node['execNode'] == 'cn21339' and node['hwThreads'] == '0-37' and node['pids'] == '-'
payload = received / 'payload'
out = payload / 'evidence/sequence5_2040363_memory'
assert not list((payload / 'evidence').glob('*_strict'))
assert load(out / 'strict_gate.json')['sha256'] == request['strict_sha256']
command = [sys.executable, '-B', str(payload / 'sequence_gate.py'), str(received / 'strict_reference_result.json')]
p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
(root / 'original_sequence_gate_local.stdout').write_bytes(p.stdout)
(root / 'original_sequence_gate_local.stderr').write_bytes(p.stderr)
assert p.returncode == 0, p.stderr.decode(errors='replace')
sys.path.insert(0, str(payload))
import sequence_runtime

strict = load(received / 'strict_reference_result.json')
strict_libraries = {x['path']: x['sha256'] for x in strict['runtime']['libraries']}
series = []
for ckpt in (0, 1):
    folder = out / ('ckpt' + str(ckpt))
    assert (folder / 'exit_code.txt').read_text().strip() == '0'
    d = load(folder / 'result.json')
    assert d['status'] == 'DDR_SEQUENCE5_DIAGNOSTIC_ONLY_NOT_STEADY_STATE' and d['completed_steps'] == 5
    assert d['mode'] == 'sequence5_memory' and d['config']['checkpoint'] is bool(ckpt)
    assert d['config'] == dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
        checkpoint=bool(ckpt), precision='fp32', threads=36, hbm=False, history='fresh_once_then_continuous',
        updates=5, repeated_same_fixed_case=True, loss='original_mean', warmup_steps=0)
    assert d['comparison_snapshots_retained'] is False and d['repeated_same_fixed_case'] is True
    assert d['strict_reference']['sha256'] == request['strict_sha256']
    assert d['case_identity'] == strict['case_identity'] and d['case_file_sha256'] == pre['case']['sha256']
    assert d['source_manifest_sha256'] == sha(payload / 'SOURCE_SHA256.json')
    for name, digest in d['source_sha256'].items(): assert sha(payload / name) == digest
    assert d['runtime']['backend'] == 'kml' and d['runtime']['torch_threads'] == 36
    assert {x['path']: x['sha256'] for x in d['runtime']['libraries']} == strict_libraries
    cpu = d['cpu36']
    assert cpu['job_id'] == '2040363' and cpu['host'] == node['execNode']
    assert cpu['receipt']['allocated'] == list(range(38)) and cpu['receipt']['selected'] == list(range(36))
    assert cpu['receipt']['reserved'] == [36, 37] and len(cpu['checkpoints']) == 15
    sequence_runtime.validate(cpu, 'memory', 5)
    identity = None
    for step, row in enumerate(d['steps'], 1):
        assert row['step'] == step and row['source_manifest_sha256'] == d['source_manifest_sha256']
        assert row['case_file_sha256'] == d['case_file_sha256']
        before, after = row['before'], row['after']
        assert before['completed_updates'] == before['optimizer_step_min'] == before['optimizer_step_max'] == step - 1
        assert after['completed_updates'] == after['optimizer_step_min'] == after['optimizer_step_max'] == step
        assert before['optimizer_states'] == (0 if step == 1 else 153) and after['optimizer_states'] == 153
        assert before['parameter_gradients_cleared'] and before['input_gradients_cleared']
        assert after['input_gradients_finite'] and after['parameter_gradients_finite'] and after['optimizer_state_finite']
        current = (after['model_id'], after['optimizer_id'])
        assert current == (before['model_id'], before['optimizer_id']) and (identity is None or current == identity)
        identity = current
        assert row['kml_calls'] == (197 if ckpt else 149)
        assert row['peak_reset'] == dict(available=True, method='/proc/self/clear_refs=5')
        start = row['training_start']; train = row['training']
        assert start['peak_rss_bytes'] == start['rss_bytes'] <= row['before_reset']['peak_rss_bytes']
        assert train['peak_rss_bytes'] >= start['peak_rss_bytes'] and train['elapsed_seconds'] > 0
        for sample in (row['before_reset'], start, train):
            assert sample['hugetlb_bytes'] == 0 and sample['peak_rss_bytes'] >= sample['rss_bytes'] > 0
            assert sample['rss_MiB'] == sample['rss_bytes'] / 2**20
            assert sample['peak_rss_MiB'] == sample['peak_rss_bytes'] / 2**20
    series.append(dict(checkpoint=ckpt, pid=cpu['pid'], cpu_checkpoints=15,
                       initialization=d['initialization'], steps=d['steps']))
assert series[0]['pid'] != series[1]['pid']
pairs = []
for index in range(5):
    a, b = [side['steps'][index]['training'] for side in series]
    pairs.append(dict(step=index+1, CKPT0=a, CKPT1=b,
        peak_reduction_percent=(1-b['peak_rss_bytes']/a['peak_rss_bytes'])*100,
        end_RSS_reduction_percent=(1-b['rss_bytes']/a['rss_bytes'])*100,
        time_increase_percent=(b['elapsed_seconds']/a['elapsed_seconds']-1)*100))
later = []
for side in series:
    rows = [s['training'] for s in side['steps'][1:]]
    later.append({key: dict(median=statistics.median(x[key] for x in rows),
                           minimum=min(x[key] for x in rows), maximum=max(x[key] for x in rows))
                  for key in ('peak_rss_bytes', 'peak_rss_MiB', 'rss_bytes', 'rss_MiB', 'elapsed_seconds')})
review = dict(status='PASS_ONE_PAIR_FIVE_UPDATE_DDR_MEMORY_DIAGNOSTIC_NOT_STEADY_STATE', job_id='2040363',
    scheduler_state='SUCCEEDED', job_exit_code=0, host=node['execNode'], active_S00_jobs=[], retries=0,
    source_files_unchanged=24, metadata_entries=65, archive_files=66, bundle=receipt,
    strict_job='2040203', strict_result_sha256=request['strict_sha256'], numerical_strict_rerun=False,
    local_original_gate_exit=p.returncode, CPU36_checkpoints=30, HWM_resets=10, series=series, pairs=pairs,
    first_step=pairs[0], steps2_to5=dict(CKPT0=later[0], CKPT1=later[1],
        median_peak_reduction_percent=(1-later[1]['peak_rss_bytes']['median']/later[0]['peak_rss_bytes']['median'])*100,
        median_end_RSS_reduction_percent=(1-later[1]['rss_bytes']['median']/later[0]['rss_bytes']['median'])*100,
        median_time_increase_percent=(later[1]['elapsed_seconds']['median']/later[0]['elapsed_seconds']['median']-1)*100),
    node_seconds=collection['node_seconds'], scheduler_usage_seconds=collection['scheduler_usage_seconds'],
    cumulative_known_S00_jobs=20, cumulative_node_seconds=898+collection['node_seconds'],
    S07_run=False, S06_run=False, real_HBM=False, formal_training=False, comparison_snapshots=False)
for path, info in load(root / 'PROTECTED_BEFORE.json').items():
    p = Path(path); assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256']
(root / 'REVIEW.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(status=review['status'], first_step_peak_reduction=pairs[0]['peak_reduction_percent'],
                     steps2_to5=review['steps2_to5'], job_id='2040363', node_seconds=collection['node_seconds'])))
