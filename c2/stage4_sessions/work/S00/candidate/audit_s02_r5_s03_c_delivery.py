"""Verify returned S02/S03 data without importing a model or rerunning C tests."""
from pathlib import Path
import datetime
import hashlib
import json
import math
import zipfile

work = Path(__file__).resolve().parents[1]
base = work / 'evidence/s02_r5_s03_c_20261105'
request = json.loads((work / 'evidence/s02_r5_s03_c_request_20261105.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
for name, digest in request['prior_evidence_sha256'].items():
    assert sha(work / name) == digest, name
records = {}
for task, jid, expected in [
    ('S02', '2034953', 'dc36ad1896eb54484588a11992c6c42d3fc20167e52ac8a05abb6bf6c99bd636'),
    ('S03', '2034987', '891b4f80884537e4b536bf27724c40539653c93fcbf3efc97a591fe266964521')]:
    root = base / task / 'received'
    bundle = base / ('JOB_' + jid + '_full_evidence.zip')
    assert sha(bundle) == expected
    collection = json.loads((root / 'COLLECTION_S00.json').read_text())
    assert collection['changed_payload_files'] == []
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(collection['files']) | {'COLLECTION_S00.json'}
        assert not any(name.endswith('.pt') for name in archive.namelist())
    for name, info in collection['files'].items():
        assert sha(root / name) == info['sha256']
        assert (root / name).stat().st_size == info['bytes'] and type(info['mtime_ns']) is int
    pre = json.loads((root / 'pre_submit_checks.json').read_text())
    for name, digest in pre['payload_files'].items():
        assert sha(root / 'payload' / name) == digest, name
    for name, digest in pre.get('wrapper_files', {}).items():
        assert sha(root / name) == digest, name
    job = json.loads((root / 'djob_final.json').read_text())['data']['successData'][0]
    resource = job['resGroups'][0]
    assert resource['resAlloc']['cpu'] == 38 and resource['resAlloc']['mem'] == 24576
    assert resource['resLimit']['mem'] == 24576
    assert all(row.get('pids') == '-' for row in resource['nodeResUsages'])
    started = datetime.datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))
    ended = datetime.datetime.fromisoformat(job['endTime'].replace('Z', '+00:00'))
    record = dict(job_id=jid, host=job['taskExecNodes'], scheduler_state=job['state'],
        job_exit_code=job['jobExitCode'], start_utc=job['startTime'], end_utc=job['endTime'],
        node_seconds=(ended - started).total_seconds(), memory_MB=24576,
        wall_limit_s=job['jobWallClockLimit'], bundle_sha256=expected,
        full_evidence_files=len(collection['files']) + 1, source_payload_unchanged=True,
        original_mtime_ns_preserved=True, prior_evidence_unchanged=True)
    if task == 'S02':
        folder = root / 'payload/evidence/c2_2034953_strict'
        result = json.loads((folder / 'result.json').read_text())
        case = json.loads((root / 'payload/CASE_MANIFEST.json').read_text())
        assert job['state'] == 'FAILED' and job['jobExitCode'] == 1 and job['jobWallClockLimit'] == 900
        assert (folder / 'checker_exit_code.txt').read_text().strip() == '1'
        assert result['status'] == 'FAIL_ORIGINAL_CRITERIA' and result['mode'] == 'strict'
        assert result['case_file_sha256'] == case['sha256'] == request['S02']['case_sha256']
        assert result['case_identity'] == case['identity']
        assert json.loads((root / 'case_identity_after.json').read_text())['sha256'] == case['sha256']
        assert result['cpu36']['errors'] == [] and result['cpu36']['job_id'] == jid
        receipt = result['cpu36']['receipt']
        assert receipt['allocated'] == list(range(38)) and receipt['selected'] == list(range(36)) and receipt['reserved'] == [36, 37]
        points = result['cpu36']['checkpoints']
        assert [p['name'] for p in points] == ['before_framework', 'after_framework', 'after_backend', 'before_reference', 'after_reference', 'after_candidate', 'publish']
        for point in points:
            assert point['pid'] == result['cpu36']['pid'] and point['snapshot']['complete'] and point['snapshot']['threads']
            if point['name'] != 'before_framework':
                assert point['torch_intraop'] == 36
            for thread in point['snapshot']['threads']:
                assert thread['affinity'] and set(thread['affinity']) <= set(receipt['selected'])
        runtime = result['runtime']
        assert runtime['backend'] == 'kml' and runtime['kml_gemm_calls'] == 447
        before = {item['path']: item['sha256'] for item in runtime['libraries']}
        after = {item['path']: item['sha256'] for item in runtime['libraries_after']}
        assert all(after.get(path) == digest for path, digest in before.items())
        metrics = result['metrics']
        assert len(metrics) == 1063 and sum(not m['passed'] for m in metrics) == len(result['failures']) == result['comparison_failures'] == 95
        assert sum(v['failed'] for v in result['summary'].values()) == 95
        submission = json.loads((root / 'submission.json').read_text())
        assert submission['donau_profile_reloaded_after_runtime'] and submission['dsub_path'] == '/opt/batch/cli/bin/dsub'
        record.update(conclusion='FAIL_ORIGINAL_CRITERIA_NUMERICAL_NOT_RUNTIME', checker_exit_code=1,
            compared_metrics=1063, comparison_failures=95, failure_families=result['summary'],
            cpu_checkpoints=7, same_pid=result['cpu36']['pid'], actual_torch_threads=36,
            kml_gemm_calls=runtime['kml_gemm_calls'], kml_shape_count=len(runtime['kml_shapes']),
            kml_libraries=runtime['libraries'], case_sha256=case['sha256'],
            fixed_case_not_downloaded=True, numerical_tolerances_unchanged=True)
    else:
        assert job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0 and job['jobWallClockLimit'] == 300
        folder = root / 'payload/linux_evidence'
        summary = json.loads((folder / 'SUMMARY.json').read_text())
        assert summary['status'] == 'PASS_LINUX_C_25_CASES_AND_ISOLATED_LIBRARY_ONLY'
        receipt = json.loads((folder / 'cpu_receipt.json').read_text())
        assert receipt['clean_environment'] and receipt['actual_affinity'] == list(range(36))
        assert receipt['contract']['reserved'] == [36, 37]
        frozen = json.loads((folder / 'frozen_faults.json').read_text())['cases']
        candidate = json.loads((folder / 'candidate_faults.json').read_text())['cases']
        assert len(frozen) == len(candidate) == 25 and sum(not c['passed'] for c in frozen) == 10
        assert all(c['passed'] for c in candidate)
        for case in candidate:
            if case['expected_exit'] == 1:
                assert case['exitcode'] == 1 and 'fatal' in case['stderr'] and 'restore' in case['stderr']
                assert 'RESULT returned_and_allocation_ok' not in case['stdout']
        steps = summary['steps']
        assert next(s['exit_code'] for s in steps if s['label'] == 'frozen_faults') == 1
        assert all(s['exit_code'] == 0 for s in steps if s['label'] != 'frozen_faults')
        assert all(s['affinity'] == list(range(36)) and not s.get('timed_out') for s in steps)
        assert not any('policy_probe' in str(s['command']) for s in steps)
        library = root / 'payload/build/libhbm_alloc_s03.so'
        assert sha(library) == summary['library_sha256']
        header = (folder / 'elf_header.txt').read_text()
        assert 'ELF64' in header and 'DYN' in header and 'AArch64' in header
        assert 'not found' not in (folder / 'ldd.txt').read_text()
        record.update(conclusion='PASS_CANDIDATE_25_C_CASES_AND_INDEPENDENT_SO_ONLY',
            frozen_passed=15, frozen_failed=10, frozen_expected_failure_runner_exit=1,
            frozen_failure_cases=[c['case'] for c in frozen if not c['passed']],
            candidate_passed=25, compiler=(folder / 'compiler.txt').read_text().splitlines()[0],
            glibc=(folder / 'glibc.txt').read_text().strip(), library_sha256=sha(library),
            library_bytes=library.stat().st_size, real_HBM=False, real_kernel_mempolicy=False,
            policy_probe=False, model_training=False)
    records[task] = record
    (base / task / 'review.json').write_bytes((json.dumps(record, indent=2) + '\n').encode())
s02end = datetime.datetime.fromisoformat(records['S02']['end_utc'].replace('Z', '+00:00'))
s03start = datetime.datetime.fromisoformat(records['S03']['start_utc'].replace('Z', '+00:00'))
assert s02end < s03start
summary = dict(status='COMPLETE_EVIDENCE_DELIVERY_S02_NUMERICAL_FAIL_S03_C_PASS',
    records=records, node_seconds_this_turn=sum(r['node_seconds'] for r in records.values()),
    cumulative_s00_node_seconds=377 + sum(r['node_seconds'] for r in records.values()),
    new_jobs=2, retries=0, numerical_thresholds_changed=False, real_HBM_run=False,
    training_memory_test_run=False, original_source_integrity_report='evidence/source_integrity.json')
(base / 'review.json').write_bytes((json.dumps(summary, indent=2) + '\n').encode())
print(json.dumps({k:v for k,v in summary.items() if k != 'records'}))
print([(task, r['job_id'], r['conclusion'], r['full_evidence_files'], r['node_seconds']) for task,r in records.items()])
