import csv,hashlib,json,math,statistics,zipfile
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/'c2/stage4_sessions/work/M23_MEMORY_HBM/memory_hbm_32e_r1_20261108'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(p,ref):assert p.stat().st_size==ref['bytes'] and sha(p)==ref['sha256'],str(p)
def rows(p):return [json.loads(s) for s in p.read_bytes().splitlines() if s]
r=read(B/'MEMORY_HBM_32E_RESULT.json');refs={};remote_refs=set()
def walk(v):
 if isinstance(v,dict):
  if {'path','bytes','sha256'}<=v.keys():
   if v['path'].startswith('c2/'):refs[v['path']]=v
   else:remote_refs.add(v['path'])
  for a in v.values():walk(a)
 elif isinstance(v,list):
  for a in v:walk(a)
walk(r)
for path,ref in refs.items():verify(ROOT/path,ref)
metric_total=0;strict_workers=0;update_total=0;zipcount=0;collectioncount=0;sourcecount=0
rounds=[];settled=[];descriptor_hashes=set();pairings=set()
ROLE={'baseline':'DDR_CKPT0','candidate':'HBM_CKPT0','ckpt_ddr':'DDR_CKPT12','ckpt_hbm':'HBM_CKPT12'}
for j in r['jobs']:
 run=B/j['run_id'];raw=run/'received';ev=raw/'job_evidence'
 zpath=run/j['archive']['file'];verify(zpath,j['archive'])
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if not name.endswith('/'):assert z.read(name)==(raw/name).read_bytes(),name
  zipcount+=len(z.namelist())
 col=read(raw/'COLLECTION.json')
 for name,ref in col.items():verify(raw/name,ref)
 collectioncount+=len(col)
 src=read(raw/'SOURCE_SHA256.json')
 for name,digest in src.items():assert sha(raw/name)==digest,name
 sourcecount+=len(src)
 assert src['payload/tests/check_equivalence.py']==r['gates']['comparator_sha256']
 assert src['payload/baseline/kml_ops.py']=='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
 descriptor_hashes.add(sha(raw/'ENGINEERING_DESCRIPTOR.json'))
 assert sha(raw/'M23_PAYLOAD.zip')==j['package_sha256']
 native=read(raw/'djob_final.json')['data']['successData'][0]
 assert native['state']=='SUCCEEDED' and str(native['jobId'])==j['job_id'] and native['exclusive']
 assert all(n['pids']=='-' for g in native['resGroups'] for n in g.get('nodeResUsages',[]))
 dt=lambda k:datetime.fromisoformat(native[k].replace('Z','+00:00'))
 alloc=int((dt('endTime')-dt('startTime')).total_seconds());queue=int((dt('startTime')-dt('createTime')).total_seconds())
 assert alloc==j['allocated_seconds'] and queue==j['queue_seconds']
 clean=read(ev/'cleanup.json');assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
 app=read(ev/'SUMMARY.json');assert app['status']=='PASS_HBM_AB' and app['hbm_pool_restored']
 gates=list(ev.glob('real_hbm_node*/RECEIPT.json'));assert len(gates)==j['domains']
 for f in gates:
  g=read(f);assert g['status']=='PASS_REAL_HBM_SAFETY' and g['pool_pages_before']==g['pool_pages_after']
 bind=read(raw/'M23_RUN_BINDING.json');roles=bind.get('variants',['baseline','candidate'])
 domains=sorted(x.name for x in (ev/'strict_baseline').glob('node*') if x.is_dir());assert len(domains)==j['domains']
 for node in domains:
  base=read(ev/'strict_baseline'/node/'result.json');assert base['status']=='PASS_STRICT_REFERENCE5'
  pairings.add(base['pairing_sha256'])
  for role in roles:
   f=ev/f'strict_{role}'/node/'result.json';v=read(f)
   assert v['completed_updates']==5 and not v['cpu36']['errors']
   assert v['pairing_sha256']==base['pairing_sha256']
   if role!='baseline':
    assert v['status']=='PASS_STRICT_ENCODER5' and len(v['metrics'])==3880
    for m in v['metrics']:assert m['passed'] and m['max_abs']==0 and m['l2_relative']==0 and math.isfinite(m['reference_norm'])
    metric_total+=len(v['metrics']);strict_workers+=1
 confs={};identity=None
 for role in roles:
  samples=[];peaks=[];huge=[];rss=[];ends=[]
  for node in domains:
   f=ev/f'perf_{role}'/node;v=read(f/'result.json');s=rows(f/'steps.jsonl')
   assert v['status']=='PASS_PERF25' and len(s)==25 and not v['cpu36']['errors']
   assert {q['torch_intraop'] for q in v['cpu36']['checkpoints'] if 'torch_intraop' in q}=={36}
   assert [x['step'] for x in s]==list(range(1,26)) and all(x['batch_size']==32 for x in s)
   assert sorted(k for x in s for k in x['frame_indices'])==list(range(800))
   ids=[[x[k] for k in ['frame_ids','frame_indices','mask_sha256','step']] for x in s]
   if identity is None:identity=ids
   assert ids==identity
   assert all(x['sampled']==(x['step']>=6) and x['peak_reset']['available'] for x in s)
   for x in s[5:]:
    assert x['training_start']['rss_bytes']==x['training_start']['peak_rss_bytes']
    assert x['training_start']['hugetlb_bytes']==x['rss_after']['hugetlb_bytes']
    assert x['native_sgemm_calls']==x['kml_calls']==(197 if role.startswith('ckpt') else 149)
    h=x['rss_after']['hugetlb_bytes']/2**20
    assert (0<h<=3800) if role in ['candidate','ckpt_hbm'] else h==0
    huge.append(h);rss.append(x['rss_after']['peak_rss_MiB']);peaks.append(x['rss_after']['peak_rss_MiB']+h)
    ends.append((x['rss_after']['rss_bytes']+x['rss_after']['hugetlb_bytes'])/2**20)
   samples.append(s)
  spans=[(max(s[i]['end_ns'] for s in samples)-min(s[i]['start_ns'] for s in samples))/1e9 for i in range(5,25)]
  confs[ROLE[role]]=dict(median_seconds=statistics.median(spans),max_joint_peak_estimate_MiB=max(peaks),max_hbm_MiB=max(huge),max_RSS_MiB=max(rss),max_step_end_MiB=max(ends))
 count=sum(len(rows(f)) for f in ev.glob('*/*/steps.jsonl'));assert count==j['completed_model_updates'];update_total+=count
 rounds.append(dict(job_id=j['job_id'],domains=j['domains'],configurations=confs))
 settled.append(dict(job_id=j['job_id'],allocated_seconds=alloc,queue_seconds=queue))
assert metric_total==r['gates']['metrics']==155200 and strict_workers*765==30600
assert update_total==1860 and sum(x['allocated_seconds'] for x in settled)==12535 and sum(x['queue_seconds'] for x in settled)==19
assert len(descriptor_hashes)==len(pairings)==1
summary={}
for conf,reported in r['four_domain_repeat_summary'].items():
 vals=[x['configurations'][conf] for x in rounds if x['domains']==4 and conf in x['configurations']]
 times=[x['median_seconds'] for x in vals];spread=(max(times)-min(times))/statistics.mean(times)*100
 assert times==reported['step_span_medians_seconds']
 if len(times)>1:assert math.isclose(spread,reported['same_host_spread_pct'],abs_tol=1e-10)
 peak=max(x['max_joint_peak_estimate_MiB'] for x in vals)
 assert peak==reported['maximum_observed_joint_peak_estimate_MiB']
 summary[conf]=dict(rounds=len(times),median_seconds=statistics.median(times),round_seconds=times,spread_pct=spread if len(times)>1 else None,max_joint_peak_estimate_MiB=peak,max_hbm_MiB=max(x['max_hbm_MiB'] for x in vals))
assert summary['HBM_CKPT12']['spread_pct']>5 and summary['HBM_CKPT12']['max_joint_peak_estimate_MiB']<4096
with (B/'GIT_ARCHIVE_S09_32E.tsv').open(encoding='utf-8-sig') as f:
 gitrows=list(csv.DictReader(f,delimiter='\t'))
 for row in gitrows:verify(ROOT/row['path'],dict(bytes=int(row['bytes']),sha256=row['sha256']))
result=dict(status='ACCEPT_BASELINE_AND_MEMORY_CANDIDATE_WITH_STABILITY_FAIL',delivery_path=str(B/'MEMORY_HBM_32E_RESULT.json'),delivery_sha256=sha(B/'MEMORY_HBM_32E_RESULT.json'),local_refs_verified=len(refs),remote_refs_not_reread=len(remote_refs),zip_members_verified=zipcount,collection_files_verified=collectioncount,source_hashes_verified=sourcecount,git_suggestion_rows_verified=len(gitrows),strict_metric_records=metric_total,strict_max_abs=0,strict_max_relative_l2=0,exact_adamw_step_checks_from_unchanged_checker_and_pass_receipts=strict_workers*765,totals=r['budget']['used'],rounds=rounds,four_domain_summary=summary,decision={'adopted_stable_speed_configuration':'HBM_CKPT0','memory_candidate_for_full_node_validation':'HBM_CKPT12','CKPT12_stable_speed_adoption':False,'full_node_dependency_eligible':True,'reason':'Joint four-domain numerical and HBM safety gates pass; existing S00 card explicitly permits performance-rejected version as validation input; preserve 5.4363842683 percent stability failure.'},frozen_candidate_package_sha256=r['jobs'][-1]['package_sha256'],checkpoint_source_sha256=src.get('payload/checkpoint_layers.py'),limitations=['Peak is per-process RSS high-water plus constant resident HBM during sampled step, not instantaneous four-domain whole-node peak.','No tensor snapshots deserialized, no models run, no direct SSH. Exact step checks confirmed through unchanged checker path and successful raw worker results.','Scope real32 B32 fp32 Encoder on one host; not B64,16 domains,DDP or production default change.'])
Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='rounds'},ensure_ascii=True))
