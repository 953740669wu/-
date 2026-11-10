"""Read-only verification of returned evidence; writes only coordinator report."""
import hashlib
import io
import json
import math
from pathlib import Path
import statistics as st
import tarfile
import zipfile
from datetime import datetime

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'S00/full_node_16domain_hbm_ckpt_r1_20261108'
def read(p):
    return json.loads(p.read_bytes())
def sha(b):
    return hashlib.sha256(b).hexdigest()
refs = {}
def verify_refs(x):
    if isinstance(x, dict):
        if 'path' in x and 'sha256' in x and Path(x['path']).is_absolute():
            p = Path(x['path']); b = p.read_bytes()
            assert sha(b) == x['sha256'], str(p)
            if 'bytes' in x: assert len(b) == x['bytes'], str(p)
            refs[str(p)] = sha(b)
        for v in x.values(): verify_refs(v)
    elif isinstance(x, list):
        for v in x: verify_refs(v)
def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8), (a,b)
def dt(s):
    return datetime.strptime(s,'%Y/%m/%d %H:%M:%S') if '/' in s else datetime.fromisoformat(s.replace('Z','+00:00'))

result = read(ROOT/'FULL_NODE_16DOMAIN_RESULT.json')
ledger = read(ROOT/'BUDGET_LEDGER.json')
verify_refs(result)
verify_refs(read(ROOT/'GIT_ARCHIVE_SUGGESTION.json'))
members = source_files = metric_count = updates = visits = 0
jobs = []; coverage = {}; paired = []
for attempt in ledger['attempts']:
    job = attempt['job_id']; folder = ROOT/attempt['version']; raw = folder/'received'
    binding = read(folder/'RUN_BINDING.json'); analysis = read(folder/'ANALYSIS.json')
    with tarfile.open(folder/f'JOB_{job}_TRANSFER.tgz') as tar:
        for member in tar.getmembers():
            assert member.isfile()
            assert tar.extractfile(member).read() == (folder/member.name).read_bytes()
    receipt = read(folder/'bundle_receipt.json')
    bundle = (folder/f'JOB_{job}_evidence.zip').read_bytes()
    assert sha(bundle) == receipt['sha256'] and len(bundle) == receipt['bytes']
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        names = z.namelist(); index = json.loads(z.read('COLLECTION_INDEX.json'))['files']
        assert len(names) == len(set(names)) == receipt['members']
        assert set(names) == {n for n,v in index.items() if v['archive']} | {'COLLECTION_INDEX.json'}
        for n in names:
            b = z.read(n); assert b == (raw/n).read_bytes(), n
            if n != 'COLLECTION_INDEX.json':
                assert sha(b) == index[n]['sha256'] and len(b) == index[n]['bytes'], n
            members += 1
    for n, digest in read(folder/'SOURCE_SHA256.json').items():
        assert sha((raw/n).read_bytes()) == digest, n
        source_files += 1
    assert sha((folder/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    assert sha((raw/'payload/tests/check_equivalence.py').read_bytes()) == 'e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e'
    assert binding['numerical'] == dict(denominator_floor=1e-12,near_zero_norm=1e-8,relative_L2=2e-6,state_abs=2e-6,strict_steps=5,tensor_abs=2e-5)
    assert binding['stability'] == {'rounds':3,'spread_pct':5}
    native, = read(raw/'djob_final.json')['data']['successData']
    group, = native['resGroups']; node, = group['nodeResUsages']
    assert native['jobId'] == job and native['state'] == 'SUCCEEDED' and native['jobExitCode'] == 0
    assert native['exclusive'] and node['pids'] == '-'
    assert group['resReq']['cpu'] == group['resAlloc']['cpu'] == 608
    assert group['resReq']['mem'] == group['resAlloc']['mem'] == group['resLimit']['mem'] == 393216
    allocated = max(node['wallclockDuration'], int((dt(native['endTime'])-dt(native['startTime'])).total_seconds()))
    queued = int((dt(native['startTime'])-dt(native['createTime'])).total_seconds())
    assert allocated == attempt['allocated_seconds'] and queued == attempt['queue_seconds']
    ev = raw/'job_evidence'; app = read(ev/'SUMMARY.json'); clean = read(ev/'cleanup.json')
    assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
    assert app['hbm_safety'] == 'PASS' and app['hbm_pool_restored']
    assert all(read(p)['passed'] for p in ev.glob('pool_return_*.json'))
    topo = read(ev/'domain_map.json'); contracts = topo['contracts']
    assert len(contracts) == 16
    assert len({c for v in contracts.values() for c in v['selected']}) == 576
    assert all(len(c['selected'])==36 and len(c['reserved'])==2 and not set(c['selected'])&set(c['reserved']) for c in contracts.values())
    for p in ev.glob('real_hbm_node*/RECEIPT.json'):
        s=read(p); assert s['status']=='PASS_REAL_HBM_SAFETY' and s['pool_pages_after']==s['pool_pages_before']
    phase_rows = {}; perf = {}; job_updates=0
    for name, published in analysis['phases'].items():
        rows_by_domain = {}; peaks=[]; end_mem=[]
        for n,c in contracts.items():
            home=ev/name/f'node{n}'; value=read(home/'result.json')
            rows=[json.loads(line) for line in (home/'steps.jsonl').read_bytes().splitlines()]
            expected=5 if name.startswith('strict') else 25
            assert value['completed_updates']==expected and len(rows)==expected
            assert value['job_id']==job and value['host']==node['execNode']
            assert not value['cpu36']['errors'] and value['cpu36']['receipt']==c
            for check in value['cpu36']['checkpoints']:
                assert check['snapshot']['complete']
                assert all(t['affinity'] and set(t['affinity'])<=set(c['selected']) for t in check['snapshot']['threads'])
                if 'torch_intraop' in check: assert check['torch_intraop']==36
            assert [r['step'] for r in rows]==list(range(1,expected+1))
            assert all(r['batch_size']==binding['batch_size'] and r['native_sgemm_calls']>0 for r in rows)
            if name=='strict_candidate':
                assert value['status']=='PASS_STRICT_ENCODER5'
                for m in value['metrics']:
                    assert m['passed'] and m['max_abs']==m['l2_relative']==0
                    metric_count+=1
            if 'candidate' in name:
                alloc=value['hbm_allocator']
                assert alloc['sha256']==binding['allocator_sha256'] and alloc['node']==topo['hbm_pairs'][n]
                assert all(0<r['rss_after']['hugetlb_bytes']<=3800*2**20 for r in rows)
            job_updates+=len(rows); visits+=sum(r['batch_size'] for r in rows)
            rows_by_domain[n]=rows
            if name.startswith('perf'):
                peaks.append(max((r['rss_after']['peak_rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows[5:]))
                end_mem.append([(r['rss_after']['rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows[5:]])
        for group_rows in zip(*rows_by_domain.values()):
            for k in ['frame_indices','frame_ids','mask_sha256','release_ns','native_shapes']:
                assert all(r[k]==group_rows[0][k] for r in group_rows)
        phase_rows[name]=rows_by_domain
        assert all(v==0 for v in read(ev/name/'exit_codes.json').values())
        if name.startswith('perf'):
            obs=[r[5:] for r in rows_by_domain.values()]
            spans=[(max(r['end_ns'] for r in g)-min(r['start_ns'] for r in g))/1e9 for g in zip(*obs)]
            window=(max(r[-1]['end_ns'] for r in obs)-min(r[0]['start_ns'] for r in obs))/1e9
            rate=16*20*binding['batch_size']/window
            median=st.median(spans); close(median,published['median_synchronized_step_seconds'])
            close(rate,published['synchronized_window_visits_per_second'])
            memory=max(map(sum,zip(*end_mem))); close(memory,published['max_sum_of_step_end_samples_MiB'])
            perf[name]=dict(median_step_seconds=median,window_rate=rate,domain_peak_estimate_MiB=max(peaks),sum_step_end_samples_MiB=memory)
            if 'candidate' in name:
                coverage.setdefault(node['execNode'],{}).setdefault(binding['workload'],[]).append(perf[name])
    for candidate in ['strict_candidate']+([n for n in phase_rows if n.startswith('perf_candidate')] if 'perf_baseline' in phase_rows else []):
        baseline='strict_baseline' if candidate.startswith('strict') else 'perf_baseline'
        for n in contracts:
            for a,b in zip(phase_rows[baseline][n],phase_rows[candidate][n]):
                assert all(a[k]==b[k] for k in ['frame_indices','frame_ids','mask_sha256','native_shapes'])
    if 'perf_baseline' in perf:
        p=perf['perf_candidate_r1']; b=perf['perf_baseline']
        paired.append(dict(host=node['execNode'],workload=binding['workload'],baseline=b,candidate=p,throughput_gain_pct=100*(p['window_rate']/b['window_rate']-1)))
    assert job_updates==attempt['confirmed_updates']==attempt['charged_updates']
    updates+=job_updates
    jobs.append(dict(job_id=job,host=node['execNode'],allocation_seconds=allocated,queue_seconds=queued,updates=job_updates,terminal_cleanup='PASS'))
    print('verified',job,flush=True)
stable=[]
for host,configs in coverage.items():
    for config,rounds in configs.items():
        assert len(rounds)==3
        times=[x['median_step_seconds'] for x in rounds]
        spread=100*(max(times)-min(times))/st.mean(times)
        close(spread,result['coverage'][host][config]['repeat_spread_pct'])
        if spread<=5: stable.append([host,config])
assert stable==result['acceptance']['stable_host_config_pairs']
assert metric_count==496640 and updates==ledger['model_updates']==10080
assert visits==result['model_frame_visits']==527360
assert sum(j['allocation_seconds'] for j in jobs)==ledger['allocation_seconds']==26526
assert sum(j['queue_seconds'] for j in jobs)==ledger['queue_seconds']==24
assert result['active_job'] is None
out=dict(status='REVIEWED_FUNCTIONAL_SAFETY_PASS_STABILITY_PARTIAL',result_sha256=sha((ROOT/'FULL_NODE_16DOMAIN_RESULT.json').read_bytes()),verified_references=refs,archive_members_verified=members,source_hashes_verified=source_files,strict_records_zero=metric_count,model_updates=updates,frame_visits=visits,jobs=jobs,paired_comparisons=paired,coverage=coverage,stable_pairs=stable,limits=['Returned evidence only; no live SSH or new cluster job.','No tensor deserialization; exact checks supported by frozen comparator and PASS receipts.','Memory is per-domain estimate or sum of step-end samples, not simultaneous whole-node peak.','Independent replicas, not DDP or scientific generalization acceptance.','No configuration passed stability on both hosts; original failures preserved.'])
(HERE/'S00_FULL16_REVIEW_20261110.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:out[k] for k in ['archive_members_verified','source_hashes_verified','strict_records_zero','stable_pairs']}))
