"""Verify namespace repair and the returned first-step numerical rejection."""
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'S00/external_fp32_attn_ab_r1_20261110'
ROOT=PARENT/'namespace_continue_20261110'
def read(p):return json.loads(p.read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
refs={}
def check_refs(x):
    if isinstance(x,dict):
        if 'path' in x and 'sha256' in x and Path(x['path']).is_absolute():
            p=Path(x['path']);b=p.read_bytes();assert sha(b)==x['sha256'],str(p)
            if 'bytes' in x:assert len(b)==x['bytes'],str(p)
            refs[str(p)]=sha(b)
        for v in x.values():check_refs(v)
    elif isinstance(x,list):
        for v in x:check_refs(v)
result=read(ROOT/'FP32_ATTN_AB_RESULT.json');check_refs(result)
folder=ROOT/'M1_NS1_D1';raw=folder/'received';ev=raw/'job_evidence';job='2085664'
with tarfile.open(folder/f'JOB_{job}_TRANSFER.tgz') as tar:
    for m in tar.getmembers():assert m.isfile() and tar.extractfile(m).read()==(folder/m.name).read_bytes()
receipt=read(folder/'bundle_receipt.json');bundle=folder/f'JOB_{job}_evidence.zip'
assert sha(bundle.read_bytes())==receipt['sha256'] and bundle.stat().st_size==receipt['bytes']
with zipfile.ZipFile(bundle) as z:
    names=z.namelist();index=json.loads(z.read('COLLECTION_INDEX.json'))['files']
    assert len(names)==len(set(names))==receipt['members']
    assert set(names)=={n for n,r in index.items() if r['archive']}|{'COLLECTION_INDEX.json'}
    for n in names:
        b=z.read(n);assert b==(raw/n).read_bytes(),n
        if n!='COLLECTION_INDEX.json':assert sha(b)==index[n]['sha256'] and len(b)==index[n]['bytes']
sources=read(folder/'SOURCE_SHA256.json')
for n,digest in sources.items():assert sha((raw/n).read_bytes())==digest,n
old=PARENT/'V2_D1/received'
marker=b'/* exp(x)'
math_body=(raw/'kml_attn.c').read_bytes().split(marker,1)[1]
assert math_body==(old/'kml_attn.c').read_bytes().split(marker,1)[1]
assert sha(math_body)==result['source_identity']['unchanged_math_body_sha256']
def math_class(p):return ast.dump(next(n for n in ast.parse(p.read_bytes()).body if isinstance(n,ast.ClassDef) and n.name=='FusedAttention'))
assert math_class(raw/'payload/attn_dispatch.py')==math_class(old/'payload/attn_dispatch.py')
for n in ['payload/baseline/s4_models.py','payload/baseline/kml_ops.py','payload/tests/check_equivalence.py','payload/checkpoint_layers.py']:
    assert (raw/n).read_bytes()==(old/n).read_bytes(),n
reference=read(ev/'strict_baseline/node0/result.json');candidate=read(ev/'strict_candidate/node0/result.json')
assert reference['status']=='PASS_STRICT_REFERENCE5' and reference['completed_updates']==5
metrics=candidate['metrics'];assert len(metrics)==4
assert all(m['passed'] and m['max_abs']==m['l2_relative']==0 for m in metrics[:3])
fail=metrics[-1];assert fail['name']=='1.output.h' and not fail['passed']
assert fail['max_abs']==2.8133392333984375e-5>2e-5
assert fail['l2_relative']==9.84024827895898e-7<2e-6
attn=candidate['attention'];assert attn['counts']=={'forward':24,'backward':12} and attn['bf16']==0 and attn['bq']==64
assert attn['locking_namespace']['namespace_id']==1 and attn['locking_namespace']['handle'] and attn['locking_namespace']['gemm_address']
assert attn['locking_namespace']['sha256']==attn['build']['locking_kml']['sha256']
assert sha((ev/'libfp32_attn.so').read_bytes())==attn['build']['library']['sha256']
guard=candidate['cpu36'];assert not guard['errors'];selected=guard['receipt']['selected']
assert len(selected)==36
for ck in guard['checkpoints']:
    assert ck['snapshot']['complete']
    assert all(t['affinity'] and set(t['affinity'])<=set(selected) for t in ck['snapshot']['threads'])
    if ck['name'] in ['after_backend','before_candidate_1','after_candidate_1']:
        assert len(ck['snapshot']['threads'])==36 and ck['torch_intraop']==36
        matching=[v for v in ck['runtime']['libraries'].values() if v.get('namespace_id')==1]
        assert len(matching)==1 and matching[0]['sha256']==attn['locking_namespace']['sha256']
steps={name:[json.loads(x) for x in (ev/name/'node0/steps.jsonl').read_bytes().splitlines()] for name in ['strict_baseline','strict_candidate']}
assert len(steps['strict_baseline'])==5 and len(steps['strict_candidate'])==1
for key in ['frame_indices','frame_ids','mask_sha256']:
    assert steps['strict_baseline'][0][key]==steps['strict_candidate'][0][key]
assert not list(ev.glob('perf*'))
native,=read(raw/'djob_final.json')['data']['successData'];group,=native['resGroups'];node,=group['nodeResUsages']
assert native['state']=='FAILED' and native['jobId']==job and node['pids']=='-'
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00')) if '/' not in s else datetime.strptime(s,'%Y/%m/%d %H:%M:%S')
assert max(node['wallclockDuration'],int((dt(native['endTime'])-dt(native['startTime'])).total_seconds()))==131
assert int((dt(native['startTime'])-dt(native['createTime'])).total_seconds())==3
assert group['resReq']['cpu']==group['resAlloc']['cpu']==38
clean=read(ev/'cleanup.json');assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
assert read(ev/'SUMMARY.json')['hbm_pool_restored'] and read(ev/'pool_return_terminal.json')['passed']
ledger=read(ROOT/'BUDGET_LEDGER.json');assert len(ledger['attempts'])==3
assert sum(a['allocated_seconds'] for a in ledger['attempts'])==ledger['allocation_seconds']==247
assert sum(a['queue_seconds'] for a in ledger['attempts'])==ledger['queue_seconds']==8
assert sum(a['confirmed_updates'] for a in ledger['attempts'])==ledger['confirmed_model_updates']==11
assert sum(a['charged_updates'] for a in ledger['attempts'])==ledger['model_updates']==20
out=dict(status='VERIFIED_ENGINEERING_FIX_PASS_NUMERICAL_REJECT',result_sha256=sha((ROOT/'FP32_ATTN_AB_RESULT.json').read_bytes()),verified_refs=refs,archive_members=len(names),source_hashes=len(sources),mathematical_body_unchanged=True,reference_steps=5,candidate_executed_updates=1,candidate_strict_passed_steps=0,native_counts=attn['counts'],first_failure=fail,engineering_namespace_cpu36='PASS',performance='NOT_RUN_NUMERICAL_GATE_FAILED',adoption='REJECT_M1_FP32_BQ64',job_id=job,cleanup='PASS_RETURNED_EVIDENCE',cumulative=dict(jobs=3,allocation_seconds=247,queue_seconds=8,recorded_updates=11,charged_updates=20),remaining=dict(jobs=3,allocation_seconds=21353,queue_seconds=86392,new_hosts=2,model_updates=15980,deadline_BJT='2026-11-12 22:04:34'),limits=['No live SSH or model execution by coordinator','First failure abort means remaining tensors and later steps untested','No speed or memory A/B; strict-stage timing cannot establish performance'])
(HERE/'S00_FP32_ATTN_NS_REVIEW_20261110.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'refs':len(refs),'archive_members':len(names),'source_hashes':len(sources),'status':out['status']}))
