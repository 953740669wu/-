"""Read only the R6 crash evidence needed for the R7 publication review."""
import hashlib
import json
from pathlib import Path

OWN=Path(__file__).resolve().parent
WORK=OWN.parent.parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset(path):
    path=Path(path)
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))


def main():
    root=WORK/'S00/s07_r6_resume_20261106'
    complete=root/'RUN_COMPLETE.json';run=json.loads(complete.read_text())
    inputs=[asset(complete)]
    index_path=Path(run['evidence_index']['path']);assert asset(index_path)==run['evidence_index']
    inputs.append(asset(index_path));index=json.loads(index_path.read_text())['files']
    received=root/'evidence/received';names=['checks.json','crash/rank0.json',
        'crash/rank1.json','crash/rank0.events.jsonl','crash/rank1.events.jsonl',
        'crash/supervisor.events.jsonl','crash/summary.json']
    files={}
    for name in names:
        relative='payload/checks_current_job/'+name;path=received/relative
        entry=asset(path);expected=index[relative]
        assert all(entry[k]==expected[k] for k in ('bytes','sha256')),name
        inputs.append(entry);files[name]=path
    assert files['crash/rank0.json'].read_bytes()==b''
    checks=json.loads(files['checks.json'].read_text())
    assert checks['status']=='FAIL' and [c['case'] for c in checks['cases']]==['normal']
    assert run['analysis_inputs']['not_run_cases']==['collective-timeout','watchdog']
    rows=lambda name:[json.loads(line) for line in files[name].read_text().splitlines()]
    rank0=rows('crash/rank0.events.jsonl');rank1=rows('crash/rank1.events.jsonl');parent=rows('crash/supervisor.events.jsonl')
    error=next(r for r in rank0 if r['event']=='worker_error')
    checkpoint=[r for r in rank0 if r['event']=='checkpoint_end'][-1]
    cleanup=next(r for r in parent if r['event']=='cleanup_begin')
    term=next(r for r in parent if r['event']=='signal_sent' and r['child_pid']==error['pid'] and r['signal']==15)
    summary=json.loads(files['crash/summary.json'].read_text())['supervisor']
    assert checkpoint['stage']==error['stage']=='broadcast'
    assert any(r['event']=='checkpoint_end' and r['stage']=='injected_crash' for r in rank1)
    assert summary['reason']=='child_failed' and summary['exit_codes']==[-15,17] and summary['all_reaped']
    source=WORK/'S07/round6_aligned_stack_20261105/candidate/comm_probe.py'
    assert sha(source)=='c9efa0c9d4ba05c8fb4501ce75f2dd60e6268d732c707cc3beef133330a356dd'
    inputs.append(asset(source))
    value=dict(status='R6_NARROW_FAILURE_EVIDENCE_VERIFIED',job_id=run['job_id'],
        formal_rank0_bytes=0,checks='FAIL',accepted_cases=['normal'],not_run_cases=run['analysis_inputs']['not_run_cases'],
        rank0_last_checkpoint=checkpoint,rank0_error=error,parent_cleanup=cleanup,parent_term=term,
        error_to_cleanup_ms=(cleanup['monotonic_ns']-error['monotonic_ns'])/1e6,
        error_to_TERM_ms=(term['monotonic_ns']-error['monotonic_ns'])/1e6,
        exact_interrupted_write_syscall='NOT_OBSERVED; truncate-and-interruption is a source-supported mechanism, not a proven syscall location',
        original_files_modified=False,new_jobs=0,inputs=inputs)
    (OWN/'BASELINE_FAILURE.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('inputs','rank0_last_checkpoint','rank0_error','parent_cleanup','parent_term')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
