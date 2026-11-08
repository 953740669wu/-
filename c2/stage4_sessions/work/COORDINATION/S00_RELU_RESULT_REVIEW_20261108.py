import hashlib, io, json, math, statistics, tarfile, zipfile
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'c2/stage4_sessions/work/S00/healthy_node_optimization_20261108'
OUT=Path(__file__).with_suffix('.json')
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(b): return hashlib.sha256(b).hexdigest()
def verify(p,ref):
    b=p.read_bytes()
    assert len(b)==ref['bytes'] and sha(b)==ref['sha256'],str(p)
def lines(p): return [json.loads(s) for s in p.read_text(encoding='utf-8-sig').splitlines() if s]
r=read(BASE/'OPTIMIZATION_RESULT.json')
refs={}
def walk(x):
    if isinstance(x,dict):
        if {'path','sha256','bytes'}<=x.keys(): refs[x['path']]=x
        for v in x.values(): walk(v)
    elif isinstance(x,list):
        for v in x:walk(v)
walk(r)
for s,v in refs.items():verify(Path(s),v)
m=read(BASE/'ARCHIVE_MANIFEST.json')
for f in m['files']:verify(BASE/f['path'],f)
archives=[]
for a in r['attempts']:
    folder=Path(a['binding']['path']).parent; raw=folder/'received'
    idx=read(raw/'COLLECTION_INDEX.json')
    indexed=0
    for name,f in idx['files'].items():
        if f.get('archive',True):verify(raw/name,f);indexed+=1
    with tarfile.open(a['transfer']['path']) as t:
        zm=[v for v in t.getmembers() if v.name.endswith('.zip')]
        assert len(zm)==1
        with zipfile.ZipFile(io.BytesIO(t.extractfile(zm[0]).read())) as z:
            assert z.testzip() is None
            for name in z.namelist():
                if not name.endswith('/'):
                    assert z.read(name)==(raw/name).read_bytes(),name
            members=len(z.namelist())
    d=read(Path(a['native']['path']))['data']['successData'][0]
    assert d['jobId']==a['job_id'] and d['state']==a['native_state'] and d['exitCode']==a['exit_code']
    dt=lambda s:datetime.fromisoformat(s.replace('Z','+00:00'))
    qend=d['endTime'] if d['startTime']=='-' else d['startTime']
    assert (dt(qend)-dt(d['createTime'])).total_seconds()==a['queue_seconds']
    if a['allocated_seconds']:
        assert (dt(d['endTime'])-dt(d['startTime'])).total_seconds()==a['allocated_seconds']
        node=d['resGroups'][0]['nodeResUsages'][0]
        assert node['execNode']=='cn21385' and node['pids']=='-' and d['exclusive']
        clean=read(Path(a['cleanup']['path']))
        assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
    else: assert d['startTime']=='-' and not [n for g in d['resGroups'] for n in (g.get('nodeResUsages') or [])]
    archives.append(dict(job_id=a['job_id'],indexed_files=indexed,zip_members=members,state=d['state']))
raw=BASE/'RELU_A/received'; ev=raw/'job_evidence'
sources=read(raw/'SOURCE_SHA256.json')
for name,digest in sources.items():assert sha((raw/name).read_bytes())==digest,name
assert sources['payload/baseline/kml_ops.py']=='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
assert sources['payload/tests/check_equivalence.py']=='e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e'
assert sources['payload/ffn_relu_reuse.py']==r['candidate']['source_sha256']
strict_count=0; series={}; recalculated={}
for n in range(4):
    d=read(ev/f'strict/node{n}/result.json')
    assert d['status']=='PASS_STRICT_ENCODER5' and not d['cpu36']['errors']
    assert d['candidate_source_sha256']==r['candidate']['source_sha256']
    for v in d['metrics']:
        assert v['passed'] and v['max_abs']==v['l2_relative']==0 and math.isfinite(v['reference_norm'])
    strict_count+=len(d['metrics'])
    ss=lines(ev/f'strict/node{n}/steps.jsonl')
    assert [(v['role'],v['candidate_ffn_calls']) for v in ss]==[('baseline',0),('candidate',12)]*5
    for role in ['baseline','candidate']:
        rr=read(ev/f'{role}/node{n}/result.json')
        assert rr['completed_updates']==25 and not rr['cpu36']['errors']
        assert {v['torch_intraop'] for v in rr['cpu36']['checkpoints'] if 'torch_intraop' in v}=={36}
        s=lines(ev/f'{role}/node{n}/steps.jsonl');series[role,n]=s
        assert [v['step'] for v in s]==list(range(1,26))
        assert all(v['native_sgemm_calls']==149 and v['candidate_ffn_calls']==(12 if role=='candidate' else 0) for v in s)
        vals=[v['step_seconds'] for v in s[5:]]
        peak=max(v[k]['peak_rss_MiB'] for v in s[5:] for k in ['rss_before','rss_after'])
        reported=r['experiment']['pair'][role]['domains'][str(n)]
        assert statistics.median(vals)==reported['sampled_seconds']['median'] and peak==reported['sample_hwm_MiB']
        assert all(v['sampled']==(v['step']>5) for v in s)
        recalculated[f'{role}_{n}']=dict(median_seconds=statistics.median(vals),total_seconds=sum(vals),sampled_peak_RSS_MiB=peak)
    for a,b in zip(series['baseline',n],series['candidate',n]):
        for key in ['frame_ids','frame_indices','mask_sha256','native_shapes','losses']: assert a[key]==b[key]
    a,b=[read(ev/f'{role}/node{n}/result.json') for role in ['baseline','candidate']]
    assert a['final_model_sha256']==b['final_model_sha256'] and a['runtime']['libraries_after']==b['runtime']['libraries_after']
assert strict_count==15580
spans={}
for role in ['baseline','candidate']:
    spans[role]=(max(series[role,n][-1]['end_ns'] for n in range(4))-min(series[role,n][5]['start_ns'] for n in range(4)))/1e9
    assert spans[role]==r['experiment']['pair'][role]['common_window_seconds']
reduction=100*(1-spans['candidate']/spans['baseline'])
assert reduction==r['experiment']['pair']['synchronized_window_time_reduction_pct'] and reduction<10 and not r['adopted']
assert sum(a['allocated_seconds'] for a in r['attempts'])==567
assert sum(a['queue_seconds'] for a in r['attempts'])==1173
review=dict(status='ACCEPT_REJECTION_EVIDENCE_NOT_PERFORMANCE_ADOPTION',result_path=str(BASE/'OPTIMIZATION_RESULT.json'),result_sha256=sha((BASE/'OPTIMIZATION_RESULT.json').read_bytes()),verified_refs=len(refs),author_manifest_files=len(m['files']),archives=archives,source_hashes=len(sources),strict_records=strict_count,strict_max_abs=0,strict_max_relative_L2=0,candidate_sha256=r['candidate']['source_sha256'],recomputed_domains=recalculated,synchronized_spans_seconds=spans,time_reduction_pct=reduction,throughput_frames_s={k:5120/v for k,v in spans.items()},budget=r['totals'],adopted=False,limitations=['One sequential same-host pair; no repeatability or HBM increment acceptance.','JSON comparisons and hashes verified; no checkpoint tensor deserialization or model rerun.','Returned native terminal/cleanup evidence verified; coordinator did not query live SSH.','cn21341 root cause remains unknown; cancellation is not a software fix.'])
OUT.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(review,ensure_ascii=False))
