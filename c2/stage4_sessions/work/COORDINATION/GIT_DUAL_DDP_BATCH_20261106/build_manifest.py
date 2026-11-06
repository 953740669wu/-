"""Build exact archive proposal; no Git writes or author execution."""
import csv, hashlib, json, subprocess
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[5]
WORK = ROOT / 'c2/stage4_sessions/work'
COORD = WORK / 'COORDINATION'
OUT = Path(__file__).resolve().parent
AUDIT = COORD / 'GIT_ARCHIVE_GAP_AUDIT_20261106'
TSV = COORD / 'GIT_SUBMIT_DUAL_DDP_NO_RUN_20261106.tsv'
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ident(p):
    data=Path(p).read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
def rel(p):
    p=Path(p)
    return (p if p.is_absolute() else ROOT/p).resolve().relative_to(ROOT).as_posix()
def dump(name, data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
selected={}
checks=[]
drifts=[]
def add(p, origin, expected=None):
    p=rel(p); f=ROOT/p
    assert f.is_file(), p
    assert f.suffix.lower() not in {'.zip','.npz','.npy','.pt','.pth','.pyc','.exe','.dll','.so'},p
    assert not any(x in p for x in ('/.venv/','/__pycache__/','known_hosts','/frozen_reference/','/local_small_ddp/')),p
    current=ident(f)
    if expected and 'sha256' in expected:
        same=expected['sha256']==current['sha256'] and expected.get('bytes',current['bytes'])==current['bytes']
        mutable=f.name in ('SESSION_STATUS.md','ROUND_DELTA.md') and f.parent.parent==WORK
        if not same:
            assert mutable, ('FROZEN_DRIFT',p,expected,current)
            drifts.append(dict(path=p,old=expected,current=current,disposition='CURRENT_STATUS_SNAPSHOT_REPLACES_OLD_INDEX_HASH'))
        checks.append(dict(path=p,matched=same,mutable_snapshot=mutable))
    selected[p]=dict(scope=p.split('/')[3],path=p,**current,origin=origin)

indices=[
 'S02/real_dual_ddp_reference_20261106/ARCHIVE_FILES.json',
 'S07/real_dual_ddp_20261106/ARCHIVE_SCOPE.json',
 'S01/real_dual_ddp_review_20261106/ARCHIVE_SCOPE.json',
 'S00/real_dual_ddp_20261106/ARCHIVE_FILES.txt',
 'S08/real_dual_ddp_summary_20261106/ARCHIVE_FILES.txt']
for name in indices:
    index=WORK/name
    if index.suffix=='.txt': entries=[(s,None) for s in index.read_text().splitlines() if s.strip()]
    else:
        d=read(index)
        if 'git_candidate_paths' in d: entries=[(s,None) for s in d['git_candidate_paths']]
        elif isinstance(d['files'],dict): entries=list(d['files'].items())
        else: entries=[(x['path'],x) for x in d['files']]
    for p,expected in entries: add(p,name,expected)
    add(index,'AUTHOR_INDEX_SELF')

add(WORK/'S01/real_dual_ddp_review_20261106/ARTIFACT_SHA256.json','COORDINATOR_EXPLICIT_ARTIFACT_INDEX_SELF')

# Verify frozen identities for string-only author lists; do not select their excluded entries.
for name in ['S07/real_dual_ddp_20261106/SOURCE_MANIFEST.json','S07/real_dual_ddp_20261106/EVIDENCE_MANIFEST.json','S01/real_dual_ddp_review_20261106/ARTIFACT_SHA256.json','S00/real_dual_ddp_20261106/SHA256_INDEX.json','S08/real_dual_ddp_summary_20261106/SUMMARY_READY.json']:
    def walk(node):
        if isinstance(node,dict):
            if 'path' in node and 'sha256' in node and rel(node['path']) in selected: add(node['path'],name,node)
            for k,v in node.items():
                if isinstance(v,dict) and 'sha256' in v and k.startswith('c2/') and rel(k) in selected: add(k,name,v)
                walk(v)
        elif isinstance(node,list):
            for v in node: walk(v)
    walk(read(WORK/name))

pending=read(AUDIT/'PENDING_FILES.json')
for x in pending:
    if '/COORDINATION/' in x['path'] and not x['prior_remaining']: add(x['path'],'COORDINATOR_EXPLICIT_NEW_ROUND_SCOPE')
for name in ('SESSION_STATUS.md','ROUND_DELTA.md'): add(WORK/'GIT'/name,'GIT_PREVIOUS_CLOSEOUT_CURRENT_SNAPSHOT')
for f in AUDIT.iterdir():
    if f.is_file(): add(f,'GAP_AUDIT_EVIDENCE')

# Record partial diagnosis review; defer both full diagnosis directories this batch.
review_path=WORK/'S01/real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_REVIEW.json'
r=read(review_path)
assert r['review_complete'] and not r['execution_authorized']
review_checks=[]
for key in ('task_card','original_final_review','diagnosis_ready','evidence_review','report','current_pid_check'):
    v=r[key]; actual=ident(v['path']); assert actual['sha256']==v['sha256'] and actual['bytes']==v['bytes'],key
    review_checks.append(dict(binding=key,**actual))
dump('DIAGNOSIS_DISPOSITION.json',dict(review=ident(review_path),status=r['status'],decision=r['decision'],checks=review_checks,disposition='DEFER_BOTH_DIAGNOSIS_DIRECTORIES_THIS_BATCH',reason='S01 review completed but new DDP and contemporaneous compute-PID/descendant cleanup evidence remain incomplete; no rerun authorized',gaps=r['insufficient_evidence'],next_action=r['minimum_next_action']))

exceptions=read(AUDIT/'HISTORICAL_EXCEPTIONS.json')
for x in exceptions:
    if x['exact_archived_at_other_paths']:
        x['disposition']='MIGRATED_EXACT_BYTES_ALREADY_ARCHIVED'; x['action']='Preserve old manifests and use recorded committed history path; no duplicate addition.'
    else:
        x['disposition']='SUPERSEDED_OLD_SUMMARY_ORIGINAL_SHA_NOT_RETAINED'
        x['superseding_manifest']='GIT_SUBMIT_MEMORY3_S06R3_20261105.tsv'
        data=subprocess.check_output(['git','show','HEAD:'+x['path']],cwd=ROOT)
        x['current_committed_version']=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        x['action']='Old summary superseded by merged newer version; original SHA not retained. Do not reconstruct or call this a missing file.'
assert sum(x['disposition'].startswith('SUPERSEDED') for x in exceptions)==8
dump('HISTORICAL_DISPOSITION.json',exceptions)

raw=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=ROOT).decode('utf-8')
inventory=[]
for item in raw.split('\0'):
    if item: inventory.append((item[3:],item[:2]))
prior={x['path']:x for x in pending}
ledger=[]
for p,state in inventory:
    if p in selected or p.startswith(rel(OUT)+'/') or p==rel(TSV) or p==rel(COORD/'GIT_SUBMIT_DUAL_DDP_NO_RUN_20261106.md'): continue
    old=prior.get(p,{}).get('prior_remaining',False)
    if '/real_dual_ddp_numeric_diagnosis_r1_20261106/' in p:
        decision='DEFER_UNCLOSED_DIAGNOSIS'; reason='S01 completed partial review; DDP/cleanup timing gaps remain'; action='Coordinator closes bounded evidence disposition before a separate exact archive batch; no rerun.'
    elif any(s in p for s in ('/frozen_','/local_small_ddp/','/isolated_package/','/tiny_ddp_','known_hosts','/rendezvous','/reproduction_')):
        decision='EXCLUDE_DUPLICATE_OR_LOCAL_ARTIFACT';reason='Existing archive exclusions: duplicate frozen/extracted/temporary probe or machine-local transport file';action='Retain locally; do not add or delete; formal failure metrics are archived via S00 authoritative copy.'
    elif old:
        decision='DEFER_HISTORICAL_REVIEW';reason='Historical remainder outside accepted current round, no new acceptance evidence';action='Owning task and coordinator must establish specific evidence/scope before any future batch; preserve locally.'
    else:
        decision='DEFER_UNLISTED_NEW_FILE';reason='Not in approved author scope or explicit coordinator scope';action='Owning task must classify and provide verified exact scope; do not auto-add.'
    ledger.append(dict(path=p,owner=p.split('/')[3] if p.startswith('c2/stage4_sessions/work/') else 'OTHER',git_state=state,prior_remaining=old,disposition=decision,reason=reason,next_action=action))
dump('REMAINDER_DISPOSITION.json',ledger)
dump('AUTHOR_IDENTITY_CHECKS.json',dict(checks=checks,current_state_drifts=drifts))
for f in OUT.iterdir():
    if f.is_file(): add(f,'BATCH_CONTROL_AND_DISPOSITION')
readme=COORD/'GIT_SUBMIT_DUAL_DDP_NO_RUN_20261106.md'
add(readme,'BATCH_INSTRUCTIONS')
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT).strip(),'Shared index not empty'
base_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
rows=sorted(selected.values(),key=lambda x:(x['scope'],x['path']))
with TSV.open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['scope','path','bytes','sha256'],delimiter='\t',lineterminator='\n',extrasaction='ignore'); writer.writeheader();writer.writerows(rows)
for row in rows: assert ident(ROOT/row['path'])=={k:row[k] for k in ('bytes','sha256')}
assert not any('real_dual_ddp_numeric_diagnosis_r1_20261106/' in x['path'] for x in rows)
print(json.dumps(dict(base_head=base_head,rows=len(rows),total_with_manifest=len(rows)+1,scopes=dict(Counter(x['scope'] for x in rows)),manifest=ident(TSV),remaining=len(ledger),remaining_counts=dict(Counter(x['disposition'] for x in ledger)),historical_original_remaining=sum(x['prior_remaining'] for x in ledger),identity_checks=len(checks),mutable_drifts=len(drifts)),ensure_ascii=False,indent=2))
