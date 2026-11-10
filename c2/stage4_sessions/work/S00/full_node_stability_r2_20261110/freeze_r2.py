"""Freeze an R2 deployment from the verified 32-electrode R1 package."""
import ast
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
R1 = HERE.parent / 'full_node_16domain_hbm_ckpt_r1_20261108'
REVIEW = HERE.parent.parent / 'COORDINATION' / 'S00_FULL16_REVIEW_20261110.json'
PACKAGE_SHA = '904def960f2c08be24539f2bd978fce3f814bf78bc54e3cbaada3dd846b0fc28'


def sha(data):
    return sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.write_bytes((json.dumps(data, indent=2, sort_keys=True) + '\n').encode())


def swap(code, old, new):
    if code.count(old) != 1:
        raise ValueError('source anchor missing or ambiguous: ' + old)
    return code.replace(old, new)


def worker(code):
    code = swap(code, '    strict = args.phase == "strict"', '''    strict = args.phase == "strict"
    deferred_validation = os.environ.get("S00_VALIDATE_AFTER_ALL_UPDATES") == "1"
    result["validation_after_all_updates"] = deferred_validation''')
    code = swap(code, '                training.validate_update(torch, model, opts[role], values[role], step)', '''                if deferred_validation:
                    barrier(args, f"done-{step}")
                validation_start = time.monotonic_ns()
                training.validate_update(torch, model, opts[role], values[role], step)
                validation_end = time.monotonic_ns()''')
    return swap(code, '                                 rss_before=rss_before,', '''                                 validation_start_ns=validation_start, validation_end_ns=validation_end,
                                 rss_before=rss_before,''')


def launch(code):
    code = swap(code, '''def phase(name, variant, contracts, owner, binding, deadline, placements, run=None):
    label = f"{name}_{variant}"
    out = EVIDENCE / (label if run is None else f"{label}_r{run}")''', '''def phase(name, variant, contracts, owner, binding, deadline, placements, arm=None, run=None):
    label = f"{name}_{variant}" + (f"_{arm}" if arm else "")
    out = EVIDENCE / (label if run is None else f"{label}_r{run}")
    deferred_validation = arm == "deferred"''')
    code = swap(code, '''                   S00_MATCHED_CKPT=str(binding["checkpoint_layers"]))''', '''                   S00_MATCHED_CKPT=str(binding["checkpoint_layers"]),
                   S00_VALIDATE_AFTER_ALL_UPDATES="1" if deferred_validation else "0")''')
    code = swap(code, '    step, sampled_at = 1, 0', '''    keys = []
    for step in range(1, 6 if name == "strict" else 27):
        keys.append(step)
        if deferred_validation and step <= (5 if name == "strict" else 25):
            keys.append(f"done-{step}")
    next_key, sampled_at = 0, 0''')
    code = swap(code, '''            if step <= (5 if name == "strict" else 26):
                ready = {n:barriers / f"{step}.node{n}.ready" for n in proc}''', '''            if next_key < len(keys):
                step = keys[next_key]
                ready = {n:barriers / f"{step}.node{n}.ready" for n in proc}''')
    code = swap(code, '''                         release_at_ns=time.monotonic_ns()+100_000_000))
                    step += 1''', '''                         release_at_ns=time.monotonic_ns()+(100_000_000 if isinstance(step, int) else 0)))
                    next_key += 1''')
    code = swap(code, '    need(step == (6 if name == "strict" else 27), "incomplete full-node rendezvous")',
                '    need(next_key == len(keys), "incomplete full-node rendezvous")')
    code = swap(code, '    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT)',
                '    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT) and raw["user"] == binding["scheduler_user"]')
    code = swap(code, '             and r["host"] == os.uname().nodename and r["variant"] == variant for r in results), "actual result receipts required")',
                '''             and r["host"] == os.uname().nodename and r["variant"] == variant
             and r["validation_after_all_updates"] is deferred_validation for r in results), "actual result receipts required")''')
    code = swap(code, '        need(120 < wall <= 7200 and binding["mode"] == "full_node_hbm_ckpt", "wrong wall or mode")\n        rounds = binding["hbm_rounds_max"]\n        need(1 <= rounds <= 3 and binding["first_hbm_round"] + rounds - 1 <= 3, "invalid HBM round plan")',
                '''        need(120 < wall <= 7200 and binding["mode"] == "full_node_stability_r2", "wrong wall or mode")
        first, rounds = binding["first_pair"], binding["pairs"]
        need(1 <= first <= 3 and 1 <= rounds <= 4-first, "invalid pair plan")''')
    start = code.index('        for variant in ("baseline","candidate"):')
    end = code.index('        outcome["active_phase"] = None', start)
    return code[:start] + '''        for variant, arm in (("baseline", None), ("candidate", "original"), ("candidate", "deferred")):
            label = f"strict_{variant}" + (f"_{arm}" if arm else "")
            outcome["active_phase"] = label
            phase("strict", variant, contracts, owner, binding, end, placements, arm=arm)
            verify_return(placements, label)
            outcome["steps"][label + "_each_domain"] = 5
        dispose_snapshots()
        outcome["completed_pairs"] = []
        required_seconds = 0
        for run in range(first, first+rounds):
            if required_seconds and end-time.monotonic() < required_seconds:
                outcome["next_pair_deferred"] = dict(pair=run, predicted_with_margin_seconds=required_seconds)
                break
            order = ("original", "deferred") if run % 2 else ("deferred", "original")
            t0 = time.monotonic()
            for arm in order:
                label = f"perf_candidate_{arm}_r{run}"
                outcome["active_phase"] = label
                phase("perf", "candidate", contracts, owner, binding, end, placements, arm=arm, run=run)
                verify_return(placements, label)
                outcome["steps"][label + "_each_domain"] = 25
            outcome["completed_pairs"].append(run)
            required_seconds = (time.monotonic()-t0)*1.25 + 60
''' + code[end:]


def freeze(version, batch, host, wall, first=1, pairs=3):
    assert re.fullmatch(r'[A-Z0-9_]+', version) and re.fullmatch(r'cn[0-9]+', host)
    assert batch in (32,64) and host not in ('cn21341','cn22035')
    assert 1 <= first <= 3 and 1 <= pairs <= 4-first
    ledger = load(HERE/'BUDGET_LEDGER.json')
    assert load(HERE/'ACTIVE_JOB.json')['active_job'] is None
    assert len(ledger['attempts']) < 6 and ledger['queue_seconds'] < 86400
    assert 120 < wall <= min(7200, 28800-ledger['allocation_seconds'])
    assert (datetime.fromisoformat(ledger['deadline_utc'])-datetime.now(timezone.utc)).total_seconds() > wall+120
    hosts = {a['host'] for a in ledger['attempts'] if a.get('host')}
    assert len(hosts | {host}) <= 2
    cap = 16*(15+50*pairs)
    assert cap <= 4000 and cap + ledger['model_updates'] <= 16000
    reviewed = load(REVIEW)
    r1_result = R1/'FULL_NODE_16DOMAIN_RESULT.json'
    assert sha(r1_result.read_bytes()) == reviewed['result_sha256']
    if batch == 64:
        assert load(HERE/'B32_ACCEPTANCE.json')['status'] == 'ACCEPTED_PAIRED_STABLE'
    origin = R1/f'H2_32B{batch}_A'
    binding = load(origin/'RUN_BINDING.json')
    assert sha((origin/'RUN_BINDING.json').read_bytes()) == reviewed['verified_references'][str(origin/'RUN_BINDING.json')]
    package = origin/'FULL16_PAYLOAD.zip'
    assert sha(package.read_bytes()) == binding['package_sha256'] == PACKAGE_SHA
    manifest = load(origin/'SOURCE_SHA256.json')
    assert sha((origin/'SOURCE_SHA256.json').read_bytes()) == binding['source_manifest_sha256']
    with ZipFile(package) as z:
        assert len(z.namelist()) == len(manifest)+1 and set(z.namelist()) == set(manifest)|{'SOURCE_SHA256.json'}
        assert z.read('SOURCE_SHA256.json') == (origin/'SOURCE_SHA256.json').read_bytes()
        sources = {name:z.read(name) for name in manifest}
    assert all(sha(raw) == manifest[name] for name,raw in sources.items())
    changed = {
        'launch.py':launch, 'payload/worker.py':worker,
        'prepare.py':lambda code:swap(swap(code,'FULL16_R1_','FULL16_R2_'),
                                    '/home/share/dengqingtian/opt/stage4_sessions/S00',
                                    '/home/share/wujunyi/opt/stage4_sessions/S00'),
        'run_job.sh':lambda code:swap(code,'HOME=/home/share/dengqingtian USER=dengqingtian',
                                      'HOME=/home/share/wujunyi USER=wujunyi'),
        'submit_once.py':lambda code:swap(code,'    return (row["execPath"] == str(ROOT) and shlex.split(row["cmd"])',
            '    return (row["user"] == binding["scheduler_user"] and row["execPath"] == str(ROOT) and shlex.split(row["cmd"])'),
    }
    diff = []
    for name, patch in changed.items():
        old = sources[name].decode()
        new = patch(old)
        diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),f'a/{name}',f'b/{name}'))
        sources[name] = new.encode()
    parsed = []
    for name, raw in sources.items():
        assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
        if name.endswith(('.py','.sh')):
            assert b'\r' not in raw, name
        if name.endswith('.py'):
            parsed.append((name,ast.parse(raw, filename=name, feature_version=(3,9))))
    out = HERE/version
    out.mkdir(exist_ok=False)
    for name,digest in binding['frozen_sidecars'].items():
        raw = (origin/name).read_bytes()
        assert sha(raw) == digest
        (out/name).write_bytes(raw)
    (out/'MINIMAL.diff').write_bytes(''.join(diff).encode())
    write(out/'SOURCE_SHA256.json',{name:sha(raw) for name,raw in sources.items()})
    with ZipFile(out/package.name,'x',ZIP_DEFLATED) as z:
        for name,raw in sorted(sources.items()):
            z.writestr(name,raw)
        z.writestr('SOURCE_SHA256.json',(out/'SOURCE_SHA256.json').read_bytes())
    remote = f'/home/share/wujunyi/opt/stage4_sessions/S00/FULL16_R2_{version}'
    argv = binding['native_argv']
    argv[argv.index('-nl')+1] = f'{host} !cn21341 !cn22035'
    argv[argv.index('-T')+1] = str(wall)
    argv[argv.index('--cwd')+1] = remote
    argv[argv.index('-oo')+1] = remote+'/job.log'
    argv[argv.index('bash')+1] = remote+'/run_job.sh'
    for key in ('first_hbm_round','hbm_rounds_max','ddr_perf_control'):
        del binding[key]
    allocator = origin/'received/job_evidence/libhbm_alloc_s03_round2.so'
    allocator_name = 'FROZEN_HBM_ALLOCATOR.so'
    raw = allocator.read_bytes()
    assert sha(raw) == binding['allocator_sha256']
    (out/allocator_name).write_bytes(raw)
    binding['frozen_sidecars'][allocator_name] = binding['allocator_sha256']
    binding['historical_allocator_origin'] = binding['allocator_origin']
    binding['allocator_origin'] = remote+'/'+allocator_name
    binding.update(version=version,remote_root=remote,mode='full_node_stability_r2',candidate='C1_DEFER_VALIDATION',
                   scheduler_user='wujunyi',
                   first_pair=first,pairs=pairs,max_model_updates=cap,wall_seconds=wall,eligible_hosts=[host],
                   remaining_queue_seconds=86400-ledger['queue_seconds'],batch_deadline_utc=ledger['deadline_utc'],
                   submission_ordinal=len(ledger['attempts'])+1,package_sha256=sha((out/package.name).read_bytes()),
                   source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
                   r1_review_result_sha256=reviewed['result_sha256'],r1_package_sha256=PACKAGE_SHA,
                   candidate_worker_sha256=sha(sources['payload/worker.py']),diff_sha256=sha((out/'MINIMAL.diff').read_bytes()))
    for name, tree in parsed:
        required = {n.slice.value for n in ast.walk(tree) if isinstance(n,ast.Subscript)
                    and isinstance(n.value,ast.Name) and n.value.id=='binding' and isinstance(n.slice,ast.Constant)}
        assert not required-set(binding), (name,required-set(binding))
    write(out/'RUN_BINDING.json',binding)
    print('RUN='+remote)
    print('PIN='+sha((out/'RUN_BINDING.json').read_bytes()))
    print('PKG='+binding['package_sha256'])
    print('WORKER='+binding['candidate_worker_sha256'])


if __name__ == '__main__':
    version,batch,host,wall,*subset = sys.argv[1:]
    freeze(version,int(batch),host,int(wall),*(int(n) for n in subset))
