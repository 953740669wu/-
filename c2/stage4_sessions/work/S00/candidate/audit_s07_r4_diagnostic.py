"""Audit terminal archives and event clocks only; never rerun probes or tests."""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

s00 = Path(__file__).resolve().parents[1]
root = s00 / 'evidence/s07_r4_diagnostic_20261105T104153Z'
request = json.loads((root / 'ROUND_REQUEST.json').read_bytes())
received = root / 'received'
load = lambda p: json.loads(p.read_bytes())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
receipt = load(root / 'JOB_2041165_receipt.json')
bundle = root / 'JOB_2041165_full_evidence.zip'
assert bundle.stat().st_size == receipt['bytes'] == 197610 and sha(bundle) == receipt['sha256']
with zipfile.ZipFile(bundle) as z:
    assert len(z.namelist()) == receipt['file_count'] == 82
    assert all(z.read(n) == (received / n).read_bytes() for n in z.namelist())
collection = load(received / 'COLLECTION_S00.json')
assert len(collection['files']) == 81 and collection['changed_source_files'] == []
for name, info in collection['files'].items():
    p = received / name
    assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256']
    assert type(info['mtime_ns']) is int and info['mtime_ns'] > 0
assert sha(received / 'S07_S00_DIAGNOSTIC_WRAPPER_R4.zip') == request['package_sha256']
assert sha(received / 'S07_INIT_DIAGNOSTIC_R3.zip') == request['inner_sha256']
with zipfile.ZipFile(received / 'S07_S00_DIAGNOSTIC_WRAPPER_R4.zip') as z:
    for n in z.namelist():
        if not n.endswith('/'): assert z.read(n) == (received / n).read_bytes()
pre = load(received / 'pre_submit_checks.json')
assert pre['package_files'] == len(pre['payload_files']) == 12 and pre['manifest_entries'] == 11
for name, digest in dict(pre['payload_files'], **pre['wrapper_files']).items(): assert sha(received / name) == digest
job = load(received / 'djob_final.json')['data']['successData'][0]
assert str(job['jobId']) == '2041165' and job['state'] == 'FAILED' and job['jobExitCode'] == 1
assert job['jobWallClockLimit'] == 300 and job['exclusive'] is True
assert job['retryPolicy']['maxRetryCnt'] == job['retryPolicy']['currentRetryTimes'] == 0
assert len(job['resGroups']) == 1
group = job['resGroups'][0]
assert group['resReq']['cpu'] == 76 and group['resReq']['mem'] == group['resLimit']['mem'] == 24576
assert len(group['nodeResUsages']) == 1
node = group['nodeResUsages'][0]
assert node['execNode'] == 'cn21338' and node['pids'] == '-'
summary = load(received / 'job_evidence/SUMMARY.json')
assert summary['status'] == 'FAIL_STOP_NO_RETRY'
assert summary['standard_library_tests'] == dict(passed=28, skipped=0, linux_group_cleanup='PASSED')
assert [s['label'] for s in summary['steps']] == ['diagnostic_tests', 'job_identity_tests', 'probe_tests', 'environment']
for label, count in [('diagnostic_tests', 6), ('job_identity_tests', 6), ('probe_tests', 16)]:
    log = (received / ('job_evidence/' + label + '.txt')).read_text(encoding='utf-8')
    assert re.search(r'Ran ' + str(count) + r' tests?', log) and '\nOK' in log
    assert 'skipped=' not in log and '... skipped' not in log
assert all(s['exit_code'] == 0 and s['remaining_live'] == [] for s in summary['steps'])
environment = load(received / 'payload/environment_current.json')
assert environment['gloo'] and environment['distributed'] and environment['torch_version'] == '2.7.1+cpu'
assert not environment['environment']['LD_PRELOAD']
authority = load(received / 'job_evidence/scheduler_handoff_receipt.json')
ready, req = load(received / 'scheduler_ready.json'), load(received / 'scheduler_request.json')
encode = lambda x: (json.dumps(x, sort_keys=True, indent=2) + '\n').encode('utf-8')
assert ready['job_id'] == authority['job_id'] == req['context']['job_id'] == '2041165'
assert ready['nonce'] == authority['nonce'] == req['nonce']
assert ready['raw_sha256'] == authority['scheduler_sha256'] == sha(received / 'scheduler_allocation.json')
assert ready['request_sha256'] == hashlib.sha256(encode(req)).hexdigest()
assert req['created_at'] <= ready['generated_at'] <= authority['verified_at']
assert authority['verified_at'] - ready['generated_at'] <= 30
sys.path.insert(0, str(received / 'payload/candidate'))
import cpu36_contract as cpu36
allocation = load(received / 'job_evidence/verified_allocation.json')
assert allocation['job_id'] == '2041165' and allocation['inherited_allowed'] == authority['allowed']
assert cpu36.cpu_list(node['hwThreads']) == authority['allowed'] and len(authority['allowed']) == 76
assert len(allocation['ranks']) == 2 and allocation['ranks'][0]['node'] != allocation['ranks'][1]['node']
for row in allocation['ranks']:
    cpu36.validate_receipt(row)
    assert len(row['allocated']) == 38 and len(row['selected']) == 36 and len(row['reserved']) == 2
assert not set(allocation['ranks'][0]['allocated']) & set(allocation['ranks'][1]['allocated'])
case = received / 'payload/checks_current_job/normal'
assert load(received / 'payload/checks_current_job/checks.json') == dict(status='FAIL', cases=[], error='normal communication failed')
normal = load(case / 'summary.json')
assert normal['status'] == 'FAIL' and normal['supervisor']['exit_codes'] == [-15, 1]
assert normal['supervisor']['reason'] == 'child_failed' and normal['supervisor']['all_reaped']
execution = load(received / 'job_evidence/run_checks_receipt.json')
assert execution['exit_code'] == 1 and execution['remaining_live'] == [] and not execution.get('timed_out')
manifest = load(case / 'manifest.json')
assert manifest['job_id'] == '2041165' and manifest['pg_timeout'] == 5 and manifest['deadline'] == 30
streams = {}
for name in ('rank0', 'rank1', 'supervisor'):
    p = case / (name + '.events.jsonl'); raw = p.read_bytes(); assert raw.endswith(b'\n')
    rows = [json.loads(line) for line in raw.splitlines()]
    assert all(type(x['time_ns']) is int and type(x['monotonic_ns']) is int for x in rows)
    assert [x['monotonic_ns'] for x in rows] == sorted(x['monotonic_ns'] for x in rows)
    streams[name] = rows
assert [len(streams[n]) for n in ('rank0', 'rank1', 'supervisor')] == [15, 25, 10]
origin = streams['supervisor'][0]['monotonic_ns']
timeline = {name: [dict(**x, seconds_from_supervisor_begin=(x['monotonic_ns']-origin)/1e9) for x in rows]
            for name, rows in streams.items()}
def moment(name, event):
    return next(x['seconds_from_supervisor_begin'] for x in timeline[name] if x['event'] == event)
key_times = dict(rank0_torch_import_begin=moment('rank0', 'torch_import_begin'),
    rank0_torch_import_end=moment('rank0', 'torch_import_end'),
    rank1_torch_import_begin=moment('rank1', 'torch_import_begin'),
    rank1_torch_import_end=moment('rank1', 'torch_import_end'),
    rank1_init_begin=moment('rank1', 'init_process_group_begin'),
    rank1_wait_timeout=moment('rank1', 'worker_error'),
    parent_cleanup_begin=moment('supervisor', 'cleanup_begin'), parent_TERM=moment('supervisor', 'signal_sent'),
    parent_end=moment('supervisor', 'supervisor_end'))
assert key_times['rank1_wait_timeout'] < key_times['rank0_torch_import_end'] < key_times['parent_TERM']
ranks = [load(case / ('rank' + str(rank) + '.json')) for rank in (0, 1)]
assert ranks[0]['stage'] == 'before_framework' and 'torch_intraop' not in ranks[0]
assert ranks[1]['stage'] == 'init_process_group' and ranks[1]['torch_intraop'] == 36
assert ranks[1]['error'] == 'RuntimeError: Wait timeout'
sys.path.insert(0, str(received))
import trace_inventory
archived = load(received / 'DIAGNOSTIC_INVENTORY.json'); replay = trace_inventory.inspect(received)
assert archived['status'] == replay['status'] == 'DIAGNOSTIC_EVIDENCE_INCOMPLETE'
for key in ('complete', 'issues', 'not_run'): assert archived[key] == replay[key]
assert replay['not_run'] == ['crash', 'collective-timeout', 'watchdog']
assert all('TRACE_WRITE_ERROR' not in x and 'truncated' not in x and 'invalid line' not in x for x in replay['issues'])
for name, info in archived['cases']['normal']['files'].items():
    for key in ('bytes', 'sha256', 'valid_rows', 'open_intervals'):
        assert info[key] == replay['cases']['normal']['files'][name][key]
for path, info in load(root / 'PROTECTED_BEFORE.json').items():
    p = Path(path); assert p.stat().st_size == info['bytes'] and sha(p) == info['sha256']
review = dict(status='PASS_ARCHIVED_DIAGNOSTIC_EVIDENCE_AUDIT_NOT_COMMUNICATION_PASS', job_id='2041165',
    scheduler_state=job['state'], job_exit_code=1, host=node['execNode'], active_S00_jobs=[], retries=0,
    bundle=receipt, archive_files=82, metadata_entries=81, source_changed=False,
    linux_checks_passed=28, linux_checks_skipped=0, environment_passed=True,
    authorized_ranks=allocation['ranks'], actual_torch36_measured_ranks=[1], rank0_actual_torch36_unmeasured=True,
    diagnostic_inventory=archived, event_counts=dict(rank0=15, rank1=25, supervisor=10),
    key_times=key_times, timeline=timeline, cleanup=normal['supervisor'], outer_remaining_live=[],
    normal_communication='FAIL_DURING_INIT', broadcast_and_all_reduce_reached=False,
    not_run=replay['not_run'], node_seconds=collection['node_seconds'], scheduler_usage_seconds=node['wallclockDuration'],
    start_utc=job['startTime'], end_utc=job['endTime'], cumulative_known_S00_jobs=21,
    cumulative_node_seconds=964+collection['node_seconds'], S02_run=False, S06_run=False,
    pure_import_or_communication_performance=False, old_root_cause_confirmed=False)
(root / 'REVIEW.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(status=review['status'], job_id='2041165', event_counts=review['event_counts'],
                     key_times=key_times, node_seconds=collection['node_seconds'])))
