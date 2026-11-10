"""Freeze one fixed-window A/B from the reviewed original 16-domain B32 package."""
import ast
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

HERE=Path(__file__).resolve().parent
R1=HERE.parent/'full_node_16domain_hbm_ckpt_r1_20261108'
BASE=R1/'H1_32B32_B'
HANDOFF=HERE.parent/'external_fp32_attn_ab_r1_20261110/V2_D1/received/scheduler_handoff.py'
REVIEW=HERE.parent.parent/'COORDINATION/S00_FULL16_REVIEW_20261110.json'
DEADLINE='2026-11-12T14:04:34+00:00'


def sha(data): return sha256(data).hexdigest()
def read(p): return json.loads(p.read_bytes())
def write(p,data): p.write_bytes((json.dumps(data,sort_keys=True,indent=2)+'\n').encode())


def swap(code,old,new):
    if code.count(old)!=1:
        raise ValueError('source anchor absent or ambiguous: '+old)
    return code.replace(old,new)


def worker(code):
    code=swap(code,'import hashlib','import hashlib\nfrom itertools import count')
    code=swap(code,'from checkpoint_layers import enable_checkpoint','from checkpoint_layers import enable_checkpoint\nfrom window_control import Window')
    begin=code.index('def barrier(args, step):'); end=code.index('def runtime_check(',begin)
    code=code[:begin]+code[end:]
    code=swap(code,'    planned = 5 if strict else 25','    if strict or args.variant != "candidate":\n        raise ValueError("fixed-window job requires original HBM performance worker")\n    window = Window(args, result, write)')
    code=swap(code,'    ref_dir = args.reference / args.output.name','    ref_dir = args.reference')
    code=swap(code,'        for step in range(1, planned + 1):','        for step in count(1):\n            if window.closed():\n                break')
    code=swap(code,'            ids = order[(step-1)*batch:step*batch]\n            mask = masks[step-1]',
              '            slot = (step-1) % 25\n            ids = order[slot*batch:(slot+1)*batch]\n            mask = masks[slot]')
    code=swap(code,'            mask_sha = pairing["mask_sha256"][step-1]','            mask_sha = pairing["mask_sha256"][slot]')
    code=swap(code,'                release = barrier(args, step)','''                release = window.rendezvous(step)
                if release is None or window.closed():
                    break''')
    code=swap(code,'                begin = time.monotonic_ns()\n                try:', '''                if not window.reserve_update():
                    break
                begin = time.monotonic_ns()
                if window.record and begin >= window.record["close_ns"]:
                    result["reserved_but_not_started"] = step
                    break
                try:''')
    code=swap(code,'native trace differs from same-job 32E DDR','native trace differs from frozen 32E DDR reference')
    code=swap(code,'                                 start_ns=begin, end_ns=end, release_ns=release, step_seconds=(end-begin)/1e9,',
              '''                                 start_ns=begin, end_ns=end, release_ns=release or None, step_seconds=(end-begin)/1e9,
                                 sequence_slot=slot+1, sequence_cycle=(step-1)//25,''')
    code=swap(code,'            for row in rows:\n                log.write', '''            if not rows:
                result["prepared_but_not_started"] = step
                ledger.value["in_flight"] = None
                ledger.save()
                break
            for row in rows:
                log.write''')
    code=swap(code,'    if not strict:\n        barrier(args, 26)\n        residency(args.output, "observe_end")',
              '    if not window.closed():\n        raise RuntimeError("fixed window did not finish")\n    residency(args.output, "observe_end")')
    code=swap(code,'        result["status"] = "PASS_PERF25"','        result["status"] = "PASS_FIXED_WINDOW"')
    code=swap(code,'    args = parser.parse_args()', '    parser.add_argument("--arm", choices=("A", "B"), required=True)\n    parser.add_argument("--counter", type=Path, required=True)\n    args = parser.parse_args()')
    return code


def launch(code):
    code=swap(code,'import subprocess','import subprocess\nimport tempfile')
    code=swap(code,'from cpu36_contract import cpu_list, discover_contracts','from cpu36_contract import cpu_list, discover_contracts\nfrom window_control import WINDOW_NS, PER_ARM_CAP')
    code=swap(code,'    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT)',
              '    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT) and raw["user"] == binding["scheduler_user"]')
    code=swap(code,'''def phase(name, variant, contracts, owner, binding, deadline, placements, run=None):
    label = f"{name}_{variant}"
    out = EVIDENCE / (label if run is None else f"{label}_r{run}")''',
              '''def phase(arm, contracts, owner, binding, deadline, placements, counter):
    name, variant = "perf", "candidate"
    out = EVIDENCE / arm''')
    code=swap(code,'                "--reference",str(EVIDENCE / "strict_baseline")]',
              '                "--reference",str(ROOT / "FROZEN_REFERENCE"),"--arm",arm,"--counter",str(counter)]')
    code=swap(code,'    step, sampled_at = 1, 0','    step, sampled_at = 1, 0\n    window = None')
    code=swap(code,'            if step <= (5 if name == "strict" else 26):',
              '            if step <= 6 or (arm == "A" and time.monotonic_ns() < window["close_ns"]):')
    start=code.index('                    if step == 1 and name == "strict"')
    end=code.index('                    step += 1',start)
    code=code[:start]+'''                    release = time.monotonic_ns()+100_000_000
                    if step == 6:
                        window = dict(open_ns=release,close_ns=release+WINDOW_NS)
                        need(window["close_ns"]/1e9 < deadline, "not enough time for a complete 600-second window")
                        save(out/"WINDOW.json",window)
                    if step <= 6 or release < window["close_ns"]:
                        save(barriers / f"{step}.release", dict(step=step, arrivals=arrivals, release_at_ns=release))
''' +code[end:]
    start=code.index('    need(step == (6 if name == "strict"'); end=code.index('\n\ndef stop(',start)
    code=code[:start]+'''    need(window and time.monotonic_ns() >= window["close_ns"], "incomplete fixed window")
    results = [read(out / f"node{n}" / "result.json") for n in contracts]
    need(all(r["status"] == "PASS_FIXED_WINDOW" and r["completed_updates"] >= 5 and r["window"] == window
             and r["job_id"] == os.environ["CCS_JOB_ID"] and r["host"] == os.uname().nodename
             and r["variant"] == variant for r in results), "all 16 fixed-window receipts required")
    save(out / "phase_receipt.json", dict(status="PASS_FIXED_WINDOW", job_id=os.environ["CCS_JOB_ID"],
         window=window, updates_reserved=int(counter.read_text()),
         domains={n:r["completed_updates"] for n,r in zip(contracts,results)}))
''' +code[end:]
    code=swap(code,'    placements = {}\n    try:', '    placements = {}\n    counters = {}\n    local = None\n    try:')
    start=code.index('        need(120 < wall <= 7200'); end=code.index('        libc = ',start)
    code=code[:start]+'''        need(1200+120 < wall <= 7200 and binding["mode"] == "step_barrier_ab_fixed_window"
             and binding["window_seconds"] == 600 and binding["max_model_updates"] == 2*PER_ARM_CAP,
             "wrong authorized A/B scope")
'''+code[end:]
    start=code.index('        for variant in ("baseline","candidate"):'); end=code.index('        outcome["active_phase"] = None',start)
    code=code[:start]+'''        local = tempfile.TemporaryDirectory(prefix="s00_step_ab_",dir="/dev/shm")
        outcome["completed_arms"] = []
        for arm in ("A","B"):
            if end-time.monotonic() <= (1200 if arm == "A" else 600):
                raise TimeoutError("not enough time for complete remaining windows")
            counter = counters[arm] = Path(local.name)/arm
            counter.write_text("0000")
            outcome["active_phase"] = arm
            phase(arm, contracts, owner, binding, end, placements, counter)
            verify_return(placements, arm)
            outcome["completed_arms"].append(arm)
'''+code[end:]
    return swap(code,'            dispose_snapshots()', '''            if local is not None:
                reservations = {arm:int(counter.read_text()) for arm,counter in counters.items()}
                local.cleanup()
                save(EVIDENCE/"update_budget_cleanup.json",dict(reservations=reservations,
                     path=local.name,removed=not Path(local.name).exists()))''')


def freeze():
    assert (datetime.fromisoformat(DEADLINE)-datetime.now(timezone.utc)).total_seconds()>7320
    review=read(REVIEW)
    assert sha((R1/'FULL_NODE_16DOMAIN_RESULT.json').read_bytes())==review['result_sha256']
    assert sha((BASE/'RUN_BINDING.json').read_bytes())==review['verified_references'][str(BASE/'RUN_BINDING.json')]
    bind=read(BASE/'RUN_BINDING.json'); manifest=read(BASE/'SOURCE_SHA256.json')
    assert sha((BASE/'FULL16_PAYLOAD.zip').read_bytes())==bind['package_sha256']
    assert sha((BASE/'SOURCE_SHA256.json').read_bytes())==bind['source_manifest_sha256']
    with ZipFile(BASE/'FULL16_PAYLOAD.zip') as z:
        assert set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'} and len(z.namelist())==len(manifest)+1
        sources={k:z.read(k) for k in manifest}
    assert all(sha(b)==manifest[n] for n,b in sources.items())
    frozen_handoff=HANDOFF.read_bytes()
    handoff_manifest=read(HANDOFF.parents[1]/'SOURCE_SHA256.json')
    assert sha(frozen_handoff)==handoff_manifest['scheduler_handoff.py']
    changes={'launch.py':launch,'payload/worker.py':worker,'scheduler_handoff.py':lambda _:frozen_handoff.decode(),
      'prepare.py':lambda c:swap(swap(c,'FULL16_R1_','STEP_AB_R1_'),'/home/share/dengqingtian/opt/stage4_sessions/S00','/home/share/wujunyi/opt/stage4_sessions/S00'),
      'run_job.sh':lambda c:swap(c,'HOME=/home/share/dengqingtian USER=dengqingtian','HOME=/home/share/wujunyi USER=wujunyi'),
      'submit_once.py':lambda c:swap(c,'    return (row["execPath"]','    return (row["user"] == binding["scheduler_user"] and row["execPath"]')}
    diff=[]
    for n,change in changes.items():
        old=sources[n].decode(); new=change(old)
        diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),f'a/{n}',f'b/{n}'))
        sources[n]=new.encode()
    helper=(HERE/'window_control.py').read_text(encoding='utf-8'); sources['payload/window_control.py']=helper.encode()
    diff.extend(unified_diff([],helper.splitlines(True),'/dev/null','b/payload/window_control.py'))
    src_ref=BASE/'received/job_evidence/strict_baseline/node0'
    archive=BASE/'JOB_2064138_TRANSFER.tgz'
    assert sha(archive.read_bytes())==review['verified_references'][str(archive)]
    import tarfile
    from io import BytesIO
    with tarfile.open(archive) as t, ZipFile(BytesIO(t.extractfile('JOB_2064138_evidence.zip').read())) as z:
        for n in ('PAIRING.json','steps.jsonl'):
            data=(src_ref/n).read_bytes()
            assert data==z.read('job_evidence/strict_baseline/node0/'+n)
            sources['FROZEN_REFERENCE/'+n]=data
    assert json.loads(sources['FROZEN_REFERENCE/PAIRING.json'])==read(BASE/'PRIOR_PAIRING.json')
    out=HERE/'AB_D16'; out.mkdir()
    for name,digest in bind['frozen_sidecars'].items():
        data=(BASE/name).read_bytes(); assert sha(data)==digest; (out/name).write_bytes(data)
    allocator=(BASE/'received/job_evidence/libhbm_alloc_s03_round2.so').read_bytes()
    assert sha(allocator)==bind['allocator_sha256']; (out/'FROZEN_HBM_ALLOCATOR.so').write_bytes(allocator)
    bind['frozen_sidecars']['FROZEN_HBM_ALLOCATOR.so']=sha(allocator)
    (out/'MINIMAL.diff').write_bytes(''.join(diff).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(b) for n,b in sources.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,b in sorted(sources.items()):
            if n.endswith('.py'): ast.parse(b,filename=n,feature_version=(3,9))
            if n.endswith(('.py','.sh','.c')): assert b'\r' not in b
            z.writestr(n,b)
        z.writestr('SOURCE_SHA256.json',(out/'SOURCE_SHA256.json').read_bytes())
    remote='/home/share/wujunyi/opt/stage4_sessions/S00/STEP_AB_R1_20261111_D16'
    oldroot=bind['remote_root']; argv=[a.replace(oldroot,remote) for a in bind['native_argv']]
    argv[argv.index('-nl')+1]='cn22035 !cn21341 !cn22044'
    assert argv[argv.index('-T')+1]=='7200'
    for k in ('ddr_perf_control','first_hbm_round','hbm_rounds_max','strict_storage_min_bytes'):
        del bind[k]
    bind.update(version='AB_D16',scheduler_user='wujunyi',mode='step_barrier_ab_fixed_window',window_seconds=600,
      max_model_updates=4000,per_arm_update_cap=2000,arm_order=['A','B'],warmup_steps=5,eligible_hosts=['cn22035'],
      excluded_hosts=['cn21341','cn22044'],remote_root=remote,allocator_origin=remote+'/FROZEN_HBM_ALLOCATOR.so',
      native_argv=argv,submission_ordinal=1,remaining_queue_seconds=86400,batch_deadline_utc=DEADLINE,
      source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()),
      diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),archived_reference_job='2064138',
      archived_reference_bundle_sha256=sha(archive.read_bytes()),archived_result_sha256=review['result_sha256'])
    write(out/'RUN_BINDING.json',bind)
    write(HERE/'BUDGET_LEDGER.json',dict(status='PREPARED',deadline_utc=DEADLINE,max_submissions=1,max_allocation_seconds=7200,
          max_updates=4000,cleanup_reserve_seconds=120,attempts=[],allocation_seconds=0,updates=0))
    write(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB_INITIAL_LIVE_QUEUE'))
    print('RUN='+remote+'\nPIN='+sha((out/'RUN_BINDING.json').read_bytes())+'\nPKG='+bind['package_sha256'])


if __name__=='__main__': freeze()
