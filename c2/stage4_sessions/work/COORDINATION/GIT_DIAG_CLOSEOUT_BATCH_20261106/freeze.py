"""Freeze a new diagnosis archive batch. No Git writes or author code execution."""
import csv,hashlib,json,subprocess,datetime
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[5]; W=ROOT/'c2/stage4_sessions/work'; C=W/'COORDINATION'; OUT=Path(__file__).resolve().parent
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def identity(p):
 b=Path(p).read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def rel(p):
 p=Path(p);return (p if p.is_absolute() else ROOT/p).resolve().relative_to(ROOT).as_posix()
def dump(name,d): (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
expected_head='f84281cb27be72fd9a4b8fb7ddb7654a338be1f5'
assert git('rev-parse','HEAD').decode().strip()==expected_head
assert not git('diff','--cached','--name-only').strip()
review=read(W/'S01/real_dual_ddp_evidence_closeout_r1_20261106/EVIDENCE_CLOSEOUT_REVIEW.json')
assert review['decision']=='ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS' and review['review_complete'] and not review['execution_authorized']
verified={}
def verify(node):
 if isinstance(node,dict):
  if 'path' in node and 'sha256' in node:
   p=rel(node['path']); got=identity(ROOT/p)
   assert got['sha256']==node['sha256'] and got['bytes']==node.get('bytes',got['bytes']),p
   verified[p]=got
  for v in node.values():verify(v)
 elif isinstance(node,list):
  for v in node:verify(v)
verify(review)
dump('CLOSEOUT_ACCEPTANCE.json',dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision='ACCEPT_LIMITED_DIAGNOSIS_ARCHIVE',review_identity=identity(W/'S01/real_dual_ddp_evidence_closeout_r1_20261106/EVIDENCE_CLOSEOUT_REVIEW.json'),verified=verified,historical_gaps_recovered=0,compute_descendant_15s_cleanup='UNKNOWN_NOT_PROVEN',original_training_FAIL_preserved=True,execution_authorized=False))
selected={};drifts=[]
def add(p,expected=None):
 p=rel(p);f=ROOT/p;assert f.is_file(),p
 assert f.suffix.lower() not in {'.pt','.npz','.npy','.zip','.exe','.pyc'},p
 assert not any(x in p for x in ('/.venv/','/__pycache__/','known_hosts')),p
 got=identity(f)
 if expected and 'sha256' in expected and (got['sha256']!=expected['sha256'] or got['bytes']!=expected.get('bytes',got['bytes'])):
  assert f.name in ('SESSION_STATUS.md','ROUND_DELTA.md') and f.parent.parent==W,('FROZEN_DRIFT',p)
  drifts.append(dict(path=p,previous=expected,current=got))
 selected[p]=dict(scope=p.split('/')[3],path=p,**got)
for t in ('S01','S07'):
 for d in ('real_dual_ddp_numeric_diagnosis_r1_20261106','real_dual_ddp_evidence_closeout_r1_20261106'):
  folder=W/t/d;idx=folder/'ARCHIVE_SCOPE.json';a=read(idx)
  entries=a.get('git_candidate_paths',a.get('files'))
  for e in entries:
   if isinstance(e,str):add(e)
   else:add(e['path'],e)
  add(idx)
  for n in ('ARTIFACT_SHA256.json','EVIDENCE_MANIFEST.json','DIAGNOSIS_READY.json','EVIDENCE_CLOSEOUT_READY.json','INPUT_MANIFEST.json','SHA256SUMS.txt','WAITING_ARCHIVE_SCOPE.json'):
   if (folder/n).is_file():add(folder/n)
  # Verify selected source/evidence identities, preserving current mutable status snapshots.
  def check(node):
   if isinstance(node,dict):
    if 'path' in node and 'sha256' in node and rel(node['path']) in selected:add(node['path'],node)
    for v in node.values():check(v)
   elif isinstance(node,list):
    for v in node:check(v)
  for n in ('ARTIFACT_SHA256.json','EVIDENCE_MANIFEST.json','INPUT_MANIFEST.json'):
   if (folder/n).is_file():check(read(folder/n))
old=read(C/'GIT_DUAL_DDP_BATCH_20261106/REMAINDER_DISPOSITION.json')
released=[x for x in old if x['disposition']=='DEFER_UNCLOSED_DIAGNOSIS'];assert len(released)==55
assert all(x['path'] in selected for x in released),[x['path'] for x in released if x['path'] not in selected]
for x in released:x.update(disposition='RELEASED_FOR_LIMITED_ARCHIVE_NEW_BATCH',reason='S01 closeout accepted with retained limitations; not historical recovery or training acceptance',next_action='Submit only under new exact TSV')
dump('DEFERRED_55_RELEASE.json',released)
dump('CURRENT_STATE_INDEX_DRIFTS.json',drifts)
for n in ('STATUS.md','SESSION_STATUS.md','ROUND_DELTA.md','COORDINATOR_HANDOFF_20261106.md','GIT_DUAL_DDP_268_POST_PUSH_REVIEW_20261106.json','REAL_DUAL_DDP_EVIDENCE_CLOSEOUT_R1_20261106.md','REAL_DUAL_DDP_MINIMAL_CANDIDATE_PROPOSAL_20261106.md','GIT_SUBMIT_DIAG_CLOSEOUT_20261106.md'):add(C/n)
for n in ('SESSION_STATUS.md','ROUND_DELTA.md'):add(W/'GIT'/n)
for f in OUT.iterdir():
 if f.is_file():add(f)
tsv=C/'GIT_SUBMIT_DIAG_CLOSEOUT_20261106.tsv'
with tsv.open('w',encoding='utf-8',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=['scope','path','bytes','sha256'],delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(sorted(selected.values(),key=lambda x:(x['scope'],x['path'])))
for p,row in selected.items():assert identity(ROOT/p)=={k:row[k] for k in ('bytes','sha256')}
ignored=subprocess.run(['git','check-ignore','--stdin'],input='\n'.join(selected)+'\n',text=True,capture_output=True,cwd=ROOT);assert not ignored.stdout,ignored.stdout
print(json.dumps(dict(rows=len(selected),with_tsv=len(selected)+1,scopes=dict(Counter(x['scope'] for x in selected.values())),sha256=identity(tsv)['sha256'],verified_closeout_unique=len(verified),released_old=55,old_remaining=Counter(x['disposition'] for x in old if x not in released),mutable_drifts=len(drifts)),ensure_ascii=False,indent=2))
