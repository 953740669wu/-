"""Read archived R6 observation completeness; never infer communication PASS."""
import json
from pathlib import Path
from prepare import sha

def inspect(root):
    directory=Path(root)/'payload/checks_current_job/watchdog'
    result=dict(status='NOT_RUN',complete=False,issues=[],files={},scope='watchdog Python/proc evidence only; ARMED/EXITED alone never imply complete; no communication verdict')
    if not directory.is_dir():result['issues'].append('watchdog not reached');return result
    names=[f'rank{r}.{suffix}' for r in (0,1) for suffix in ('python_stack.txt','stack_status.json','installed_python.json')]+['proc_identity.json','proc_fields.jsonl','proc_summary.json','proc_helper.log','participants.json','summary.json','manifest.json','supervisor.events.jsonl']
    for name in names:
        path=directory/name
        if path.is_file():result['files'][name]=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),mtime_ns=path.stat().st_mtime_ns)
        else:result['issues'].append(name+': missing')
    def require(ok,message):
        if not ok:raise ValueError(message)
    def load(name):return json.loads((directory/name).read_text(encoding='utf-8'))
    try:
        context=load('participants.json');target=context['deadline_ns']-5_000_000_000;pids=context['pids']
        manifest=load('manifest.json');receipts=manifest['allocation']['ranks']
        parent_events=[json.loads(line) for line in (directory/'supervisor.events.jsonl').read_bytes().splitlines()]
        parent_pid=parent_events[0]['pid']
        def guard_evidence(record,selected):
            snapshot=record['snapshot']
            require(record['calling_affinity'] and set(record['calling_affinity'])<=set(selected) and snapshot['complete'] and not snapshot['errors'] and not snapshot['vanished'],'observer CPU snapshot incomplete/outside authority')
            require(snapshot['threads'] and all(t['affinity'] and set(t['affinity'])<=set(selected) for t in snapshot['threads']),'observer TID outside selected36')
        helper=load('summary.json')['supervisor']['stack_observation']
        require(helper['target_ns']==target and helper['sample_stop_ns']==target+2_000_000_000,'parent target/window mismatch')
        require(helper.get('reaped') is True and helper.get('returncode') is not None and helper.get('status')=='EXITED','helper not reaped/finished')
        require(any(e['event']=='proc_helper_started' and e.get('helper_pid')==helper['helper_pid'] for e in parent_events),'helper absent from actual parent events')
        for rank in (0,1):
            state=load(f'rank{rank}.stack_status.json');raw=(directory/f'rank{rank}.python_stack.txt').read_bytes()
            require(state['target_ns']==target and state['armed_at_ns']<target and state['rank']==rank and state['pid']==pids[rank] and state['job_id']==context['job_id'] and state['run_id']==context['run_id'],'rank stack identity/target mismatch')
            require(state['status'] in ('ARMED','CANCELLED_OR_DUMP_FINISHED'),'timer missed/failed')
            require(bool(raw) and b'Timeout' in raw and b'Thread' in raw,'empty/missing Python traceback; ARMED is insufficient')
            for name in ('before_timer_cpu','after_timer_cpu'):guard_evidence(state[name],receipts[rank]['selected'])
            sources=load(f'rank{rank}.installed_python.json')
            require(sources['status']=='RECORDED' and len(sources['files'])==2,'installed source evidence incomplete')
            require({s['module'] for s in sources['files']}=={'torch.distributed.distributed_c10d','torch.distributed.rendezvous'},'installed distributed source set mismatch')
            require(all(s.get('path') and 0<s['bytes']<=1048576 and len(s['sha256'])==64 and s['mtime_ns']>0 for s in sources['files']),'installed source fields missing')
        proc_identity=load('proc_identity.json');require(proc_identity['identity']=={k:context[k] for k in ('job_id','run_id','ready_token')},'proc native/run identity mismatch')
        targets=proc_identity['targets'];require(len(targets)==2 and [t['pid'] for t in targets]==pids and all(t['sid']==t['pid'] and t['start_ticks']>0 and t['ppid']==parent_pid for t in targets) and proc_identity['captured_ns']<target,'proc target owner/session/start_ticks mismatch')
        proc=load('proc_summary.json');require(proc['helper_pid']==helper['helper_pid'] and proc['target_ns']==target and proc['sample_stop_ns']==target+2_000_000_000,'proc helper/window identity mismatch')
        require(proc['status']=='RECORDED_AVAILABLE_FIELDS_ONLY' and target<=proc['sample_started_ns']<=proc['finished_ns']<=target+2_000_000_000,'proc missed/incomplete/shared-window exceeded')
        require(len(proc['ranks'])==2 and all(r['status']=='RECORDED' and r['pid']==pids[r['rank']] and not r.get('fd_error') and all('error' not in fd for fd in r.get('fds_first16',[])) for r in proc['ranks']),'rank proc/FD incomplete')
        for rank in proc['ranks']:
            r=rank['rank'];selected=receipts[r]['selected']
            require(rank['target']['identity']==rank['identity_after']['identity']==targets[r] and all(v['affinity'] and set(v['affinity'])<=set(selected) for v in (rank['target'],rank['identity_after'])),'target identity/CPU recheck incomplete')
            guard_evidence(rank['helper_cpu'],selected)
        raw=(directory/'proc_fields.jsonl').read_bytes();require(bool(raw) and raw.endswith(b'\n'),'empty/partial proc fields')
        rows=[json.loads(line) for line in raw.splitlines()];require(len(rows)==8 and {(r['rank'],r['field']) for r in rows}=={(rank,field) for rank in (0,1) for field in ('wchan','syscall','stack','mountinfo')},'missing/duplicate proc fields')
        require(all(r['pid']==pids[r['rank']] and r['status']=='OK' for r in rows),'proc EMPTY/ERROR/TRUNCATED fields retained; not complete')
        result.update(target_ns=target,helper_receipt=helper,proc_status=proc['status'],stack_scope='Python traceback at original deadline-5; proc native stack may have permission/capability limits')
    except (OSError,ValueError,KeyError,IndexError,TypeError) as exc:result['issues'].append(repr(exc))
    result['complete']=not result['issues'];result['status']='COMPLETE_R6_OBSERVATION_ONLY' if result['complete'] else 'R6_OBSERVATION_INCOMPLETE'
    return result
