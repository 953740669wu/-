"""Offline audit of immutable job2034247 evidence; no model or remote execution."""
from pathlib import Path
import datetime
import hashlib
import importlib
import json
import os
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]
BASE = WORK / 'S00/evidence/r7_cpu36_2034247'
RECEIVED = BASE / 'received'
R7 = WORK / 'S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z'
REPORTS = RECEIVED / 'payload/output/reports/s01_cpu36_2034247'
DOCS = [WORK / 'COORDINATION/CPU36_R7_STARTUP_RESULT_REVIEW.md',
        WORK / 'S00/CPU36_R7_STARTUP_REPORT.md', WORK / 'COORDINATION/R7_PASS_NEXT_S02.md']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            assert key not in value, ('duplicate JSON key', str(path), key)
            value[key] = item
        return value
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def snapshot(paths):
    return {str(p): dict(sha256=sha(p), bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns)
            for p in sorted(set(paths)) if p.is_file()}


inputs = snapshot([*BASE.rglob('*'), *R7.rglob('*'), *DOCS])
save('inputs_before.json', inputs)
collection = load(RECEIVED / 'COLLECTION_S00.json')
bundle = BASE / 'full_evidence.zip'
assert sha(bundle) == 'cf5db0ce6ac812c719b5879e26c68955f26fbfa23154a6bea96f31962bcb9755'
assert collection['job_id'] == '2034247' and collection['scheduler_state'] == 'SUCCEEDED'
assert collection['job_exit_code'] == 0 and collection['changed_payload_files'] == []
with zipfile.ZipFile(bundle) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist()) == len(set(archive.namelist())) == 54
    assert set(archive.namelist()) == set(collection['files']) | {'COLLECTION_S00.json'}
    assert {p.relative_to(RECEIVED).as_posix() for p in RECEIVED.rglob('*') if p.is_file()} == set(archive.namelist())
    for name in archive.namelist():
        assert archive.read(name) == (RECEIVED / name).read_bytes(), name
for name, info in collection['files'].items():
    assert sha(RECEIVED / name) == info['sha256'] and (RECEIVED / name).stat().st_size == info['bytes'], name
    assert type(info['mtime_ns']) is int and info['mtime_ns'] > 0
package = R7 / 'S01_CPU36_MODEL_R7.zip'
assert sha(package) == '288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c'
with zipfile.ZipFile(package) as archive:
    assert len(archive.namelist()) == 11
    for name in archive.namelist():
        assert archive.read(name) == (RECEIVED / 'payload' / name).read_bytes(), name
for name, info in load(RECEIVED / 'payload/SOURCE_MANIFEST.json')['files'].items():
    assert sha(RECEIVED / 'payload' / name) == info['sha256']
for line in (R7 / 'ARTIFACT_SHA256.txt').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha(R7 / name) == digest, name
pre_submit = load(RECEIVED / 'pre_submit_checks.json')
assert len(pre_submit['payload_files']) == 14 and len(pre_submit['source_files']) == 9
assert pre_submit['package_sha256'] == sha(package)
for item in pre_submit['shell_checks']:
    path = RECEIVED / 'payload' / item['file']
    assert item['cr_bytes'] == item['bash_n_exit'] == 0 and b'\r' not in path.read_bytes()
    assert sha(path) == item['sha256']
assert len(pre_submit['shell_checks']) == 3 and len(pre_submit['python_syntax']) == 4

# Import only the byte-verified stdlib runner; never call main/preflight/model.
sys.dont_write_bytecode = True
sys.path.insert(0, str(RECEIVED / 'payload/candidate'))
runner = importlib.import_module('runner')
cpu = importlib.import_module('cpu36_contract')
job = load(RECEIVED / 'djob_final.json')['data']['successData'][0]
assert job['jobId'] == '2034247' and job['taskExecNodes'] == 'cn21340'
assert job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0
resource = job['resGroups'][0]
assert resource['resAlloc']['cpu'] == 38 and resource['resAlloc']['mem'] == 24576
assert resource['resLimit']['mem'] == 24576 and job['jobWallClockLimit'] == 900
start = datetime.datetime.fromisoformat(job['startTime'].replace('Z', '+00:00')).timestamp()
end = datetime.datetime.fromisoformat(job['endTime'].replace('Z', '+00:00')).timestamp()
assert end - start == 111
submission = load(RECEIVED / 'submission.json')
assert submission['exit_code'] == 0 and json.loads(submission['stdout'])['data']['jobId'] == job['jobId']
assert (RECEIVED / 'job_id.txt').read_text().strip() == job['jobId']
assert (RECEIVED / 'payload/startup36_once.marker').read_text().strip() == job['jobId']
spec = load(REPORTS / 'manifest.json')
assert spec['job_id'] == job['jobId'] and spec['host'] == job['taskExecNodes']
assert spec['run_id'] == 's01_cpu36_2034247' and spec['rounds'] == 3 and spec['domains'] == [0]
assert spec['belts'] == ['16_adjacent'] and spec['parts'] == ['pre', 'dec']
assert spec['worker_environment'] == cpu.ENVIRONMENT
assert spec['hbm'] is False and spec['memory_policy'] == 'membind'
assert spec['run_timeout'] == 180 and spec['sync_timeout'] == 120
assert spec['device'] == 'cpu' and spec['input_protocol'] == 'LEGACY_TIMING_ONLY'
assert spec['config'] == dict(amp='fp32', batch=32, channels_last=False, compile=False, reps=1,
                            kml_conv=False, kml_blas='/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so',
                            ckpt=False, kml_linear=True, linear_dtype='fp32')
receipt = spec['cpu_contracts']['0']
cpu.validate_receipt(receipt)
assert receipt['allocated'] == receipt['domain_cpus'] == list(range(38))
assert receipt['selected'] == list(range(36)) and receipt['reserved'] == [36, 37]
assert all(receipt['physical_siblings'][str(i)] == [i] for i in range(38))
for name, digest in spec['source_sha256'].items():
    assert sha(RECEIVED / 'payload/candidate' / name) == digest
preflights = list((RECEIVED / 'payload/evidence').glob('CPU36_PREFLIGHT_*.json'))
assert len(preflights) == 1
preflight = load(preflights[0])
assert preflight['status'] == 'PASS_IMPORT_ONLY' and preflight['version'] == cpu.VERSION
for field in ('job_id', 'host', 'source_sha256', 'cpu_contracts'):
    assert preflight[field] == spec[field]
assert preflight['runtime'] == spec['runtime_reference'] and preflight['environment'] == cpu.ENVIRONMENT
assert preflight['torch_intraop'] == 36 and preflight['torch_interop'] == 608
assert start <= preflight['timestamp_ns'] / 1e9 <= end
cpu.validate_snapshot(receipt['selected'], preflight['snapshot'])
for name, info in preflight['runtime']['libraries'].items():
    assert spec['frozen_files'][name] == info['sha256']
    if 'omp_get_max_threads' in info:
        assert info['omp_get_max_threads'] == 36
for name, digest in preflight['frozen_files'].items():
    assert spec['frozen_files'][name] == digest
    if '/payload/' in name:
        relative = name.split('/payload/', 1)[1]
        assert pre_submit['payload_files'][relative] == digest
assert spec['frozen_files'][str(job['execPath']) + '/evidence/' + preflights[0].name] == sha(preflights[0])

rounds = []
assert not list(REPORTS.rglob('ABORT.json'))
for rid in range(1, 4):
    data, state = load(REPORTS / f'r{rid}_d0.json'), load(REPORTS / f'r{rid}_d0.status.json')
    sync = REPORTS / f'sync_r{rid}'
    assert state == load(sync / 'rank0.status.json')
    assert state['exit_code'] == 0 and state['timed_out'] is False
    assert state['diagnostic_matches']['count'] == 0
    assert start <= state['started'] <= data['run']['started'] <= data['run']['finished'] <= state['finished'] <= end
    assert state['finished'] - state['started'] < spec['run_timeout']
    assert data['run']['pid'] == state['pid'] and data['run']['source_sha256'] == spec['source_sha256']
    cpu.validate_result(spec, data, state, rid, 0)
    evidence = data['run']['cpu36']
    assert evidence == load(sync / 'thread_rank0.json')
    assert evidence['context'] == load(sync / 'cpu36_d0.json') == spec['cpu_contexts'][str(rid)]['0']
    checkpoints = evidence['checkpoints']
    assert [p['name'] for p in checkpoints] == cpu.required_checkpoints(spec)
    assert len(checkpoints) == 6
    assert [p['time'] for p in checkpoints] == sorted(p['time'] for p in checkpoints)
    assert checkpoints[0]['calling_affinity'] == list(range(36))
    assert data['run']['affinity'] == [0] and data['run']['omp_threads'] == 36
    for checkpoint in checkpoints[1:]:
        assert checkpoint['torch_intraop'] == 36 and checkpoint['torch_interop'] == 608
        assert checkpoint['environment'] == cpu.ENVIRONMENT
    for part in ('pre', 'dec'):
        assert load(sync / f'16_adjacent_{part}.0.json') == dict(run_id=spec['run_id'], rank=0)
    command = load(sync / 'commands.json')['0']
    assert command[:3] == ['numactl', '--physcpubind=' + ','.join(map(str, range(36))), '--membind=0']
    assert command[3].endswith('/ENV_20261104T130730Z_R4/venv/bin/python3')
    assert command[4:] == [job['execPath'] + '/candidate/s4_models.py', job['execPath'] + '/output', 's0322p0,s0322p1']
    observed, previous, count, max_tids = {}, 0, 0, 0
    with (sync / 'rank0.threads.jsonl').open() as stream:
        for line in stream:
            item = json.loads(line)
            snap = item['snapshot']
            cpu.validate_snapshot(receipt['selected'], snap)
            assert state['started'] <= item['time_ns'] / 1e9 <= state['finished']
            assert item['time_ns'] > previous
            previous = item['time_ns']
            assert state['pid'] in {row['tid'] for row in snap['threads']}
            for row in snap['threads']:
                observed.setdefault(row['tid'], set()).add(tuple(row['affinity']))
            count += 1
            max_tids = max(max_tids, len(snap['threads']))
    expected = {t['tid']: {tuple(m) for m in t['masks']} for t in state['thread_monitor']['threads']}
    assert observed == expected
    assert count == state['thread_monitor']['snapshots']
    rounds.append(dict(round=rid, pid=state['pid'], exit_code=state['exit_code'], timed_out=state['timed_out'],
                       duration_s=state['finished'] - state['started'], checkpoint_count=6,
                       monitor_samples=count, observed_tids=len(observed), max_simultaneous_tids=max_tids,
                       calling_affinity=data['run']['affinity'], torch_intraop=36, torch_interop=608,
                       checkpoint_thread_counts=[len(p['snapshot']['threads']) for p in checkpoints],
                       measurements=data['16_adjacent']))
assert [r['monitor_samples'] for r in rounds] == [571, 547, 565]

# Offline summarize needs original mtime, never mutate the received originals.
copy = HERE / 'replay_received'
assert not copy.exists(), 'audit output directory must be fresh'
shutil.copytree(RECEIVED, copy)
rounding = 0
for name, info in collection['files'].items():
    path = copy / name
    os.utime(path, ns=(info['mtime_ns'], info['mtime_ns']))
    rounding = max(rounding, abs(path.stat().st_mtime_ns - info['mtime_ns']))
offline = runner.summarize(copy / 'payload/output/reports/s01_cpu36_2034247')
remote = load(REPORTS / 'summary.json')
assert offline == remote and offline['status'] == 'PASS' and offline['errors'] == []
assert offline == load(BASE / 'offline_summary.json')
save('offline_summary.json', offline)
after = snapshot([Path(p) for p in inputs])
assert inputs == after, 'original input bytes/size/mtime changed'
save('inputs_integrity.json', dict(files_verified=len(inputs), bytes_size_mtime_unchanged=True))
result = dict(conclusion='ACCEPTED_BOUNDED_CPU36_MODEL_STARTUP_NO_S01_BLOCKER_FOR_S02',
              job_id=job['jobId'], host=job['taskExecNodes'], scheduler_state=job['state'], job_exit_code=0,
              evidence_files=54, package_members_verified=11, source_files_verified=9,
              pre_submit_payload_hash_receipts=14, bundle_sha256=sha(bundle), package_sha256=sha(package),
              allocated=receipt['allocated'], selected=receipt['selected'], reserved=receipt['reserved'],
              cpu_environment=cpu.ENVIRONMENT, preflight='PASS_IMPORT_ONLY_SAME_JOB',
              modules=preflight['runtime']['modules'], runtime_libraries=preflight['runtime']['libraries'],
              checkpoint_count=18, samples=1683, rounds=rounds, offline_summary_status=offline['status'],
              offline_equals_remote_exactly=True, mtime_copy_max_rounding_ns=rounding,
              originals_unchanged=True, blocking_findings=[], model_rerun=False, environment_retest=False,
              audit_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
save('review.json', result)
print(json.dumps({k: result[k] for k in ('conclusion', 'evidence_files', 'checkpoint_count', 'samples', 'rounds',
                                       'offline_summary_status', 'mtime_copy_max_rounding_ns')}, indent=2))
