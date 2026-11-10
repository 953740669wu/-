"""Verify returned FP32 attention failure evidence without executing model code."""
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile
from datetime import datetime

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent/'S00/external_fp32_attn_ab_r1_20261110'
def read(p): return json.loads(p.read_bytes())
def sha(b): return hashlib.sha256(b).hexdigest()
refs={}
def verify(x):
    if isinstance(x,dict):
        if 'path' in x and 'sha256' in x and Path(x['path']).is_absolute():
            p=Path(x['path']);b=p.read_bytes()
            assert sha(b)==x['sha256'],str(p)
            if 'bytes' in x: assert len(b)==x['bytes'],str(p)
            refs[str(p)]=sha(b)
        for v in x.values(): verify(v)
    elif isinstance(x,list):
        for v in x: verify(v)
result=read(ROOT/'FP32_ATTN_AB_RESULT.json');ledger=read(ROOT/'BUDGET_LEDGER.json')
verify(result)
members=sources=updates=0
jobs=[]
for attempt in ledger['attempts']:
    job=attempt['job_id'];folder=ROOT/attempt['version'];raw=folder/'received'
    with tarfile.open(folder/f'JOB_{job}_TRANSFER.tgz') as t:
        for m in t.getmembers():
            assert m.isfile() and t.extractfile(m).read()==(folder/m.name).read_bytes()
    bundle=folder/f'JOB_{job}_evidence.zip';receipt=read(folder/'bundle_receipt.json')
    assert sha(bundle.read_bytes())==receipt['sha256'] and bundle.stat().st_size==receipt['bytes']
    with zipfile.ZipFile(bundle) as z:
        names=z.namelist();index=json.loads(z.read('COLLECTION_INDEX.json'))['files']
        assert len(names)==len(set(names))==receipt['members']
        assert set(names)=={n for n,r in index.items() if r['archive']}|{'COLLECTION_INDEX.json'}
        for n in names:
            b=z.read(n);assert b==(raw/n).read_bytes(),n
            if n!='COLLECTION_INDEX.json':
                assert len(b)==index[n]['bytes'] and sha(b)==index[n]['sha256'],n
            members+=1
    for name,digest in read(folder/'SOURCE_SHA256.json').items():
        assert sha((raw/name).read_bytes())==digest,name
        sources+=1
    n,=read(raw/'djob_final.json')['data']['successData']
    g,=n['resGroups'];node,=g['nodeResUsages']
    assert n['state']=='FAILED' and n['jobId']==job and node['pids']=='-'
    def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00')) if '/' not in s else datetime.strptime(s,'%Y/%m/%d %H:%M:%S')
    allocated=max(node['wallclockDuration'],int((dt(n['endTime'])-dt(n['startTime'])).total_seconds()))
    queued=int((dt(n['startTime'])-dt(n['createTime'])).total_seconds())
    assert allocated==attempt['allocated_seconds'] and queued==attempt['queue_seconds']
    clean=read(raw/'job_evidence/cleanup.json')
    assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
    observed=sum(len(p.read_bytes().splitlines()) for p in (raw/'job_evidence').glob('*/node*/steps.jsonl'))
    assert observed==attempt['confirmed_updates'];updates+=observed
    jobs.append(dict(job_id=job,allocation_seconds=allocated,queue_seconds=queued,updates=observed,terminal='FAILED',cleanup='PASS'))
v2=ROOT/'V2_D1/received';ev=v2/'job_evidence'
reference=read(ev/'strict_baseline/node0/result.json');candidate=read(ev/'strict_candidate/node0/result.json')
assert reference['status']=='PASS_STRICT_REFERENCE5' and reference['completed_updates']==5
assert candidate['completed_updates']==0 and candidate['metrics']==[]
assert candidate['attention']['counts']=={'forward':0,'backward':0}
assert 'runtime_info' in candidate['traceback'] and 'RTLD_NOLOAD' in candidate['traceback']
assert candidate['error']=="OSError('dlopen() error')"
assert read(ev/'pool_return_terminal.json')['passed']
assert read(ev/'SUMMARY.json')['hbm_pool_restored']
build=read(ev/'ATTN_BUILD.json')
assert sha((ev/'libfp32_attn.so').read_bytes())==build['library']['sha256']
assert read(ev/'attn_compile.exit.json')['exit_code']==0 and read(ev/'attn_link.exit.json')['exit_code']==0
rows=[json.loads(x) for x in (ev/'strict_baseline/node0/steps.jsonl').read_bytes().splitlines()]
peak=max((r['rss_after']['peak_rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows)
assert updates==ledger['confirmed_model_updates']==5
assert sum(j['allocation_seconds'] for j in jobs)==116 and sum(j['queue_seconds'] for j in jobs)==5
assert result['active_job'] is None and result['adoption']=='NOT_ADOPTED_UNVALIDATED'
v1_sources=read(ROOT/'V1_D1/SOURCE_SHA256.json');v2_sources=read(ROOT/'V2_D1/SOURCE_SHA256.json')
changed_sources=[k for k in sorted(set(v1_sources)|set(v2_sources)) if v1_sources.get(k)!=v2_sources.get(k)]
assert changed_sources==['scheduler_handoff.py']
out=dict(status='VERIFIED_BLOCKED_BEFORE_CANDIDATE_EXECUTION',result_sha256=sha((ROOT/'FP32_ATTN_AB_RESULT.json').read_bytes()),verified_refs=refs,archive_members=members,source_hashes=sources,jobs=jobs,reference_steps=5,candidate_updates=0,candidate_comparisons=0,candidate_forward_backward=[0,0],reference_strict_peak_estimate_MiB=peak,speed_comparison='NOT_RUN',memory_comparison='NOT_RUN',numerical_comparison='NOT_RUN',adoption='NOT_ADOPTED_UNVALIDATED',remaining_budget=dict(submissions=4,allocation_seconds=21484,queue_seconds=86395,model_updates=15990,new_hosts=2,original_deadline_BJT='2026-11-12 22:04:34'),limits=['Returned evidence verification, no live SSH or model execution','Reference memory includes strict snapshots; not a performance baseline','Namespace explanation supported by traceback and source; repair not runtime tested'])
out['v1_to_v2_changed_sources']=changed_sources
(HERE/'S00_FP32_ATTN_R1_REVIEW_20261110.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(refs=len(refs),members=members,sources=sources,reference_peak=peak,status=out['status'])))
