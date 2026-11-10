"""Add one first-update trace to the previously verified single-domain package."""
import ast
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'namespace_continue_20261110'
BASE=OLD/'M1_NS1_D1'
COORD=HERE.parent.parent.parent/'COORDINATION'
REVIEW=COORD/'S00_FP32_ATTN_NS_REVIEW_20261110.json'
VERSION='M1_FIRST_ERROR_D1'


def sha(b):
    return sha256(b).hexdigest()


def read(p):
    return json.loads(p.read_bytes())


def write(p,x):
    p.write_bytes((json.dumps(x,indent=2,sort_keys=True)+'\n').encode())


def swap(code,old,new):
    if code.count(old)!=1:
        raise ValueError('source anchor absent or ambiguous: '+old)
    return code.replace(old,new)


def worker(code):
    code=swap(code,'    planned = 5 if strict else 25','    if not strict:\n        raise ValueError("diagnostic permits only the first strict update")\n    planned = 1')
    code=swap(code,'        if len(reference_steps) != 5:','        if len(reference_steps) != planned:')
    code=swap(code,'    enable_checkpoint(models[args.variant])','''    enable_checkpoint(models[args.variant])
    from first_error_trace import FirstErrorTrace
    trace = FirstErrorTrace(args, result, models[args.variant])''')
    code=swap(code,'''                strict_evidence(torch, accepted, args, result, step, models[args.variant], opts[args.variant],
                                initial, captures[args.variant], losses[args.variant], values[args.variant])''',
              '                trace.finish(result, captures[args.variant], accepted)')
    return swap(code,'"PASS_STRICT_REFERENCE5" if args.variant == "baseline" else "PASS_STRICT_ENCODER5"',
                '"PASS_STRICT_REFERENCE1_DIAGNOSTIC" if args.variant == "baseline" else "DIAGNOSTIC_FIRST_STEP_OBSERVED"')


def launch(code):
    code=swap(code,'            if step <= (5 if name == "strict" else 26):','            if step == 1:')
    code=swap(code,'    need(step == (6 if name == "strict" else 27), "incomplete full-node rendezvous")',
              '    need(step == 2, "incomplete first-step rendezvous")')
    code=swap(code,'("PASS_STRICT_REFERENCE5" if variant == "baseline" else "PASS_STRICT_ENCODER5", 5)',
              '("PASS_STRICT_REFERENCE1_DIAGNOSTIC" if variant == "baseline" else "DIAGNOSTIC_FIRST_STEP_OBSERVED", 1)')
    code=swap(code,'glob("node*/strict_step*.pt")','glob("node*/*.pt")')
    code=swap(code,'        need(120 < wall <= 7200 and binding["mode"] == "external_fp32_attn_ab", "wrong wall or mode")',
              '        need(120 < wall <= 900 and binding["domain_count"] == 1 and binding["pairs"] == 0\n'
              '             and binding["diagnostic_compute_seconds"] == 300, "wrong diagnostic scope or deadline")')
    code=swap(code,'        end = START + wall - 120','        end = min(START + wall - 120, START + binding["diagnostic_compute_seconds"])')
    code=swap(code,'            outcome["steps"][f"strict_{variant}_each_domain"] = 5',
              '            outcome["steps"][f"strict_{variant}_each_domain"] = 1')
    code=swap(code,'        outcome["status"] = "PASS_FULL_NODE_COMPLETED_PHASES"',
              '        outcome["status"] = "DIAGNOSTIC_BOTH_ARMS_COMPLETED"')
    code=swap(code,'    finally:\n        signal.setitimer', '    finally:\n        outcome["compute_finished"] = time.monotonic()\n        signal.setitimer')
    return swap(code,'    return 0 if outcome["status"] == "PASS_FULL_NODE_COMPLETED_PHASES" else 2',
                '    return 0 if outcome["status"] == "DIAGNOSTIC_BOTH_ARMS_COMPLETED" else 2')


def freeze():
    review=read(REVIEW)
    assert sha((OLD/'FP32_ATTN_AB_RESULT.json').read_bytes())==review['result_sha256']
    for file,digest in review['verified_refs'].items():
        assert sha(Path(file).read_bytes())==digest,file
    ledger=read(OLD/'BUDGET_LEDGER.json')
    assert (len(ledger['attempts']),ledger['allocation_seconds'],ledger['queue_seconds'],ledger['model_updates'])==(3,247,8,20)
    assert ledger['deadline_utc']=='2026-11-12T14:04:34+00:00' and 21600-ledger['allocation_seconds']>=900
    assert (datetime.fromisoformat(ledger['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()>1020
    bind=read(BASE/'RUN_BINDING.json')
    manifest=read(BASE/'SOURCE_SHA256.json')
    assert sha((BASE/'FULL16_PAYLOAD.zip').read_bytes())==bind['package_sha256']
    assert sha((BASE/'SOURCE_SHA256.json').read_bytes())==bind['source_manifest_sha256']
    with ZipFile(BASE/'FULL16_PAYLOAD.zip') as z:
        assert set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'} and len(z.namelist())==len(manifest)+1
        sources={k:z.read(k) for k in manifest}
    assert all(sha(b)==manifest[k] for k,b in sources.items())
    diff=[]
    for name,patch in {'payload/worker.py':worker,'launch.py':launch}.items():
        old=sources[name].decode(); new=patch(old)
        diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),f'a/{name}',f'b/{name}'))
        sources[name]=new.encode()
    name='payload/first_error_trace.py'
    trace=(HERE/'first_error_trace.py').read_text(encoding='utf-8')
    sources[name]=trace.encode(); diff.extend(unified_diff([],trace.splitlines(True),'/dev/null','b/'+name))
    assert sha(sources['kml_attn.c'])==bind['kernel_source_sha256']
    assert sha(sources['payload/attn_dispatch.py'])==bind['dispatch_sha256']
    out=HERE/VERSION; out.mkdir()
    for name,digest in bind['frozen_sidecars'].items():
        data=(BASE/name).read_bytes(); assert sha(data)==digest; (out/name).write_bytes(data)
    (out/'MINIMAL.diff').write_bytes(''.join(diff).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(b) for n,b in sources.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,b in sorted(sources.items()):
            if n.endswith('.py'): ast.parse(b,filename=n,feature_version=(3,9))
            if n.endswith(('.py','.sh','.c')): assert b'\r' not in b
            z.writestr(n,b)
        z.writestr('SOURCE_SHA256.json',(out/'SOURCE_SHA256.json').read_bytes())
    old=bind['remote_root']; remote=old.rsplit('/',1)[0]+'/ATTN_R1_'+VERSION
    argv=[x.replace(old,remote) for x in bind['native_argv']]
    argv[argv.index('-T')+1]='900'
    bind.update(version=VERSION,remote_root=remote,allocator_origin=remote+'/FROZEN_HBM_ALLOCATOR.so',
        native_argv=argv,wall_seconds=900,diagnostic_compute_seconds=300,strict_storage_min_bytes=2**30,
        max_model_updates=2,submission_ordinal=4,remaining_queue_seconds=86400-ledger['queue_seconds'],
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),diagnostic_source_sha256=sha(sources['payload/first_error_trace.py']))
    write(out/'RUN_BINDING.json',bind)
    ledger.update(status='PREPARED_FIRST_ERROR_DIAGNOSTIC',diagnostic=dict(version=VERSION,max_jobs=1,max_allocation_seconds=900,max_compute_seconds=300))
    write(HERE/'BUDGET_LEDGER.json',ledger)
    write(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB_INITIAL_LIVE_QUEUE'))
    print('RUN='+remote+'\nPIN='+sha((out/'RUN_BINDING.json').read_bytes())+'\nPKG='+bind['package_sha256'])


if __name__=='__main__':
    freeze()
