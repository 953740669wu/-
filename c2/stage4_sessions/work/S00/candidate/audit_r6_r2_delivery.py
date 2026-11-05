"""Verify only this round's R6 CKPT and R2 UBSan evidence, without executing tests."""
from pathlib import Path
import datetime
import hashlib
import json
import zipfile

work = Path(__file__).resolve().parents[1]
base = work / 'evidence/s02_r6_s03_r2_20261105'
request = json.loads((work / 'evidence/s02_r6_s03_r2_request_20261105.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, digest in request['prior_evidence_sha256'].items():
    assert sha(work / name) == digest, name
records = {}
for task, jid, digest in [
    ('S02', '2037034', '7d6365f5ebe41c6fa8e80168a3ea3bb9a55ec7105944d7b0575818d496201bce'),
    ('S03', '2037064', '28a6530ecc4fc32b3984572330a48817ad07dafc5ef471420ba71de1cc9c1646')]:
    root = base / task / 'received'
    bundle = base / ('JOB_' + jid + '_full_evidence.zip')
    assert sha(bundle) == digest
    collection = json.loads((root / 'COLLECTION_S00.json').read_text())
    assert collection['changed_payload_files'] == []
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(collection['files']) | {'COLLECTION_S00.json'}
    for name, entry in collection['files'].items():
        assert sha(root / name) == entry['sha256']
        assert (root / name).stat().st_size == entry['bytes'] and type(entry['mtime_ns']) is int
    pre = json.loads((root / 'pre_submit_checks.json').read_text())
    for name, value in pre['payload_files'].items():
        assert sha(root / 'payload' / name) == value, name
    for name, value in pre.get('wrapper_files', {}).items():
        assert sha(root / name) == value, name
    job = json.loads((root / 'djob_final.json').read_text())['data']['successData'][0]
    res = job['resGroups'][0]
    assert res['resAlloc']['cpu'] == 38 and res['resAlloc']['mem'] == res['resLimit']['mem'] == 24576
    assert all(x.get('pids') == '-' for x in res['nodeResUsages'])
    start = datetime.datetime.fromisoformat(job['startTime'].replace('Z', '+00:00'))
    end = datetime.datetime.fromisoformat(job['endTime'].replace('Z', '+00:00'))
    item = dict(job_id=jid, host=job['taskExecNodes'], scheduler_state=job['state'],
                job_exit_code=job['jobExitCode'], start_utc=job['startTime'], end_utc=job['endTime'],
                node_seconds=(end-start).total_seconds(), allocated_cpu=38, selected_cpu=36,
                memory_MB=24576, wall_limit_s=job['jobWallClockLimit'],
                bundle_sha256=digest, full_evidence_files=len(collection['files'])+1,
                source_unchanged=True, original_mtime_ns_preserved=True,
                training_memory_run=False, real_HBM_run=False)
    if task == 'S02':
        folder = root / 'payload/evidence/c2_2037034_checkpoint_strict'
        result = json.loads((folder / 'result.json').read_text())
        assert job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0 and job['jobWallClockLimit'] == 900
        assert (folder / 'checker_exit_code.txt').read_text().strip() == '0'
        assert result['status'] == 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
        assert result['mode'] == 'checkpoint_strict' and result['config']['microbatch'] == 64
        assert result['config']['effective_batch'] == 64 and result['config']['reference_checkpoint'] is False and result['config']['candidate_checkpoint'] is True
        assert result['comparison_failures'] == 0 and result['failures'] == [] and len(result['metrics']) == 1063
        assert all(m['passed'] and m['max_abs'] == 0 and m['l2_relative'] == 0 for m in result['metrics'])
        case = json.loads((root / 'payload/CASE_MANIFEST.json').read_text())
        assert result['case_identity'] == case['identity']
        assert result['case_file_sha256'] == case['sha256'] == request['case_sha256']
        assert json.loads((root / 'case_identity_after.json').read_text())['sha256'] == case['sha256']
        pair = result['checkpoint_pair']
        assert pair['reference'] is False and pair['candidate'] is True and pair['independent_model_instances']
        assert pair['wrapped_encoder_layers'] == 12 and pair['batch'] == 64 and pair['loss'] == 'unchanged_original_mean' and pair['use_reentrant'] is False
        calls = result['kml_calls_by_side']
        assert calls['reference'] == 149 and calls['candidate'] == 197
        assert result['runtime']['backend'] == 'kml' and result['runtime']['kml_gemm_calls'] == sum(calls.values())
        before = {x['path']:x['sha256'] for x in result['runtime']['libraries']}
        after = {x['path']:x['sha256'] for x in result['runtime']['libraries_after']}
        assert all(after.get(p) == h for p,h in before.items())
        cpu = result['cpu36'];assert cpu['errors'] == [] and cpu['job_id'] == jid
        assert cpu['receipt']['selected'] == list(range(36)) and cpu['receipt']['reserved'] == [36,37]
        expected = ['before_framework','after_framework','after_backend','before_reference','after_reference','after_candidate','publish']
        assert [p['name'] for p in cpu['checkpoints']] == expected
        for point in cpu['checkpoints']:
            assert point['pid'] == cpu['pid'] and point['snapshot']['complete'] and point['snapshot']['threads']
            if point['name'] != 'before_framework': assert point['torch_intraop'] == 36
            for thread in point['snapshot']['threads']: assert thread['affinity'] and set(thread['affinity']) <= set(range(36))
        item.update(conclusion='PASS_THIS_FIXED_B64_CKPT0_VS_CKPT1_STRICT_CASE_ONLY',
                    compared_metrics=1063, failed_metrics=0, max_abs=0, max_l2_relative=0,
                    cpu_checkpoints=7, same_pid=cpu['pid'], actual_torch_intraop=36,
                    checkpoint_pair=pair, kml_calls_by_side=calls, source_package_sha256=request['packages']['S02_R6']['package_sha256'],
                    memory_gain_accepted=False, old_R5_failure_unchanged=True)
    else:
        folder = root / 'payload/linux_evidence'
        summary = json.loads((folder / 'SUMMARY.json').read_text())
        assert job['state'] == 'FAILED' and job['jobExitCode'] == 1 and job['jobWallClockLimit'] == 300
        assert summary['status'] == 'FAIL_C_OR_INFRASTRUCTURE'
        log = (folder / 'build_previous.txt').read_text()
        assert 'cannot find -lubsan' in log
        steps = summary['steps'];assert steps[-1]['label'] == 'build_previous' and steps[-1]['exit_code'] == 1
        assert '-fsanitize=undefined' in steps[-1]['command'] and '-fno-sanitize-recover=all' in steps[-1]['command']
        assert all(s['exit_code'] == 0 for s in steps[:-1])
        assert all(s['affinity'] == list(range(36)) and not s.get('timed_out') for s in steps)
        receipt = json.loads((folder / 'cpu_receipt.json').read_text())
        assert receipt['clean_environment'] and receipt['contract']['reserved'] == [36,37]
        assert not (folder / 'previous_cases.json').exists() and not (folder / 'candidate_cases.json').exists()
        assert not (root / 'payload/build/libhbm_alloc_s03_round2.so').exists()
        item.update(conclusion='BLOCKED_DEFAULT_TOOLCHAIN_CANNOT_LINK_LIBUBSAN_NOT_CANDIDATE_FAILURE',
                    blocker='ld: cannot find -lubsan', previous_case_count_run=0, candidate_case_count_run=0,
                    expected_previous_defects=21, expected_previous_controls=29, expected_candidate_cases=50,
                    isolated_library_built=False, ubsan_not_removed=True, retry_submitted=False,
                    source_package_sha256=request['packages']['S03_R2']['package_sha256'])
    records[task] = item
    (base / task / 'review.json').write_bytes((json.dumps(item,indent=2)+'\n').encode())
assert records['S02']['end_utc'] < records['S03']['start_utc']
result = dict(status='COMPLETE_S02_R6_STRICT_PASS_S03_R2_UBSAN_LINK_BLOCKED',
              records=records, new_jobs=2, retries=0, node_seconds_this_round=sum(x['node_seconds'] for x in records.values()),
              cumulative_s00_node_seconds=408+sum(x['node_seconds'] for x in records.values()),
              old_evidence_unchanged=True, training_memory_run=False, real_HBM_run=False)
(base / 'review.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
print([(k,v['job_id'],v['node_seconds'],v['conclusion']) for k,v in records.items()])
