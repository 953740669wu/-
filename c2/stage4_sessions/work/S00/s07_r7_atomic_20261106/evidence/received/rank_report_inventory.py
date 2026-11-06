"""Describe terminal official rank checkpoints and atomic residues separately."""
import json
from pathlib import Path
from prepare import sha
CASES=('normal','crash','collective-timeout','watchdog')

def inspect(root):
    root=Path(root);output=dict(cases={},not_run=[],scope='terminal official JSON identity/checkpoint and raw residues only; not a communication verdict; no temp-to-formal recovery')
    def meta(path):return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path),mtime_ns=path.stat().st_mtime_ns)
    def events(path):
        if not path.is_file():return [],'missing events'
        try:return [json.loads(line) for line in path.read_bytes().splitlines()],None
        except (ValueError,UnicodeError) as exc:return [],repr(exc)
    for name in CASES:
        directory=root/'payload/checks_current_job'/name
        if not directory.is_dir():output['not_run'].append(name);continue
        context_error=None;manifest={};pids=[]
        try:
            manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'));pids=json.loads((directory/'summary.json').read_text(encoding='utf-8'))['supervisor']['pids']
            if manifest['job_id']!=(root/'job_id.txt').read_text().strip() or len(pids)!=2:raise ValueError('current manifest/parent PID identity mismatch')
        except (OSError,ValueError,KeyError,TypeError) as exc:context_error=repr(exc)
        parent,parent_error=events(directory/'supervisor.events.jsonl');reports={}
        for rank in (0,1):
            path=directory/f'rank{rank}.json';row=dict(formal_report_valid=False,stage=None)
            if path.is_file():row['file']=meta(path)
            try:
                value=json.loads(path.read_text(encoding='utf-8'))
                if context_error or not isinstance(value,dict) or value.get('rank')!=rank or value.get('pid')!=pids[rank] or value.get('run_id')!=manifest['run_id'] or value.get('world_size')!=2:raise ValueError('formal rank identity incomplete/different')
                checkpoints=value['checkpoints']
                if not isinstance(value['stage'],str) or not value['stage'] or not isinstance(checkpoints,list) or not checkpoints:raise ValueError('formal stage/checkpoint missing')
                row.update(formal_report_valid=True,stage=value['stage'],status=value.get('status'),last_published_checkpoint=checkpoints[-1]['stage'],error_present='error' in value,error=value.get('error'),pid=value['pid'])
            except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:row['formal_error']=repr(exc)
            stream,error=events(directory/f'rank{rank}.events.jsonl');ends=[e for e in stream if e.get('event')=='checkpoint_end']
            row.update(last_checkpoint_end_event=ends[-1] if ends else None,worker_error_events=[e for e in stream if e.get('event')=='worker_error'],event_parse_error=error,
                parent_term_and_reap_events=[e for e in parent if e.get('event') in ('signal_sent','child_reaped') and rank<len(pids) and e.get('child_pid')==pids[rank]])
            reports[str(rank)]=row
        residuals=[dict(name=p.name,**meta(p)) for p in sorted(directory.glob('.rank[01].json.*.tmp')) if p.is_file()]
        output['cases'][name]=dict(reports=reports,residuals=residuals,context_error=context_error,parent_event_parse_error=parent_error,
            note='A terminal official report may be the last committed checkpoint; it does not prove the final error handler committed. Temporary bytes are archived, never parsed as official reports.')
    return output
