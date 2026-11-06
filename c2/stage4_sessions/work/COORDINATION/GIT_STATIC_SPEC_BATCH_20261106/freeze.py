"""Exact static proposal/spec archive; no Git writes or author execution."""
import csv,hashlib,json,subprocess,datetime
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[5]; W=ROOT/'c2/stage4_sessions/work'; C=W/'COORDINATION'; OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ident(p):
 b=Path(p).read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def rel(p):
 p=Path(p);return (p if p.is_absolute() else ROOT/p).resolve().relative_to(ROOT).as_posix()
def dump(n,d):(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
assert git('rev-parse','HEAD').decode().strip()=='05ded1bfd2b9339dcb5cd0c6708ec0b29dfa44a5'
assert not git('diff','--cached','--name-only').strip()
blocked_dir=W/'S02/real_dual_ddp_localization_prepare_r1_20261106'
blocked=read(blocked_dir/'PREPARATION_BLOCKED.json'); verified={}
def verify(node):
 if isinstance(node,dict):
  if 'path' in node and 'sha256' in node:
   p=rel(node['path']);a=ident(ROOT/p);assert a['sha256']==node['sha256'] and a['bytes']==node.get('bytes',a['bytes']),p;verified[p]=a
  for v in node.values():verify(v)
 elif isinstance(node,list):
  for v in node:verify(v)
verify(blocked);verify(read(blocked_dir/'evidence/SOURCE_INPUTS.json'))
assert blocked['status']=='BLOCKED_PREPARATION_WITH_REASON' and not blocked['PREPARATION_READY_published']
dump('BLOCKED_DELIVERY_IDENTITY_REVIEW.json',dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision='IDENTITY_VERIFIED_TECHNICAL_REVIEW_PENDING',blocked=ident(blocked_dir/'PREPARATION_BLOCKED.json'),verified=verified,blocker=blocked['blocker_code'],deployable=False,execution_authorized=False,scope='No model or fixtures rerun; full preparation directory deferred pending S01 review'))
selected={};drifts=[]
def add(p,e=None):
 p=rel(p);f=ROOT/p;a=ident(f)
 assert f.suffix.lower() not in {'.zip','.pt','.npz','.npy','.pyc','.exe'},p
 assert 'real_dual_ddp_localization_prepare_r1_20261106/' not in p,p
 if e and 'sha256' in e and (a['sha256']!=e['sha256'] or a['bytes']!=e.get('bytes',a['bytes'])):
  assert f.name in ('SESSION_STATUS.md','ROUND_DELTA.md') and f.parent.parent==W,('FROZEN_DRIFT',p)
  drifts.append(dict(path=p,previous=e,current=a))
 selected[p]=dict(scope=p.split('/')[3],path=p,**a)
for name in ['S02/real_dual_ddp_minimal_candidate_proposal_20261106/ARCHIVE_FILES.json','S01/real_dual_ddp_proposal_review_20261106/ARCHIVE_SCOPE.json']:
 idx=W/name;f=read(idx)['files'];entries=f.items() if isinstance(f,dict) else [(e['path'],e) for e in f]
 for p,e in entries:add(p,e)
 add(idx)
 artifact=idx.parent/'ARTIFACT_SHA256.json'
 if artifact.is_file():add(artifact)
def selected_verify(x):
 if isinstance(x,dict):
  if 'path' in x and 'sha256' in x and rel(x['path']) in selected:add(x['path'],x)
  for v in x.values():selected_verify(v)
 elif isinstance(x,list):
  for v in x:selected_verify(v)
selected_verify(read(W/'S01/real_dual_ddp_proposal_review_20261106/ARTIFACT_SHA256.json'))
for n in ['STATUS.md','SESSION_STATUS.md','ROUND_DELTA.md','COORDINATOR_HANDOFF_20261106.md','GIT_DIAG_99_POST_PUSH_REVIEW_20261106.json','S02_NO_CANDIDATE_PROPOSAL_REVIEW_20261106.json','S01_MINIMAL_EVIDENCE_SPEC_REVIEW_20261106.json','REAL_DUAL_DDP_PROPOSAL_REVIEW_AND_EVIDENCE_SPEC_20261106.md','REAL_DUAL_DDP_LOCALIZATION_PREPARE_R1_20261106.md','REAL_DUAL_DDP_PREPARATION_BLOCKER_REVIEW_20261106.md','GIT_SUBMIT_STATIC_SPEC_20261106.md']:add(C/n)
for n in ['SESSION_STATUS.md','ROUND_DELTA.md']:add(W/'GIT'/n)
tsv=C/'GIT_SUBMIT_STATIC_SPEC_20261106.tsv'
old={x['path']:x for x in read(C/'GIT_DUAL_DDP_BATCH_20261106/REMAINDER_DISPOSITION.json') if x['disposition']!='DEFER_UNCLOSED_DIAGNOSIS'}
pending=[(x[3:],x[:2]) for x in git('status','--porcelain=v1','-z','--untracked-files=all').decode().split('\0') if x]
ledger=[]
for p,st in pending:
 if p in selected or p.startswith(rel(OUT)+'/') or p==rel(tsv):continue
 if p in old:entry=dict(old[p])
 elif p.startswith(rel(blocked_dir)+'/'):
  entry=dict(path=p,owner='S02',disposition='DEFER_PREPARATION_BLOCKER_REVIEW',reason='B01_UNBOUND_INSTALLED_NATIVE_VJP; identity checked, technical review not complete',next_action='S01 reviews offline binding gap; no runtime or job authorized')
 else:entry=dict(path=p,owner=p.split('/')[3] if p.startswith('c2/stage4_sessions/work/') else 'OTHER',disposition='DEFER_NEW_UNAPPROVED',reason='Not in exact accepted static proposal/spec scope',next_action='Classify separately before any later exact batch')
 entry['git_state']=st;ledger.append(entry)
dump('REMAINDER_DISPOSITION.json',ledger);dump('CURRENT_STATE_INDEX_DRIFTS.json',drifts)
for f in OUT.iterdir():
 if f.is_file():add(f)
with tsv.open('w',encoding='utf-8',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=['scope','path','bytes','sha256'],delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(sorted(selected.values(),key=lambda x:(x['scope'],x['path'])))
for p,r in selected.items():assert ident(ROOT/p)=={k:r[k] for k in ('bytes','sha256')}
ignored=subprocess.run(['git','check-ignore','--stdin'],input='\n'.join(selected)+'\n',text=True,capture_output=True);assert not ignored.stdout,ignored.stdout
print(json.dumps(dict(rows=len(selected),with_tsv=len(selected)+1,scopes=dict(Counter(x['scope'] for x in selected.values())),sha256=ident(tsv)['sha256'],blocked_delivery_verified_unique=len(verified),remaining=dict(Counter(x['disposition'] for x in ledger)),mutable_drifts=len(drifts)),ensure_ascii=False,indent=2))
