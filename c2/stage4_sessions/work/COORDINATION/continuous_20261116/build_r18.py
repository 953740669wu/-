"""Isolate CPU foreach AdamW on the full-checkpoint baseline, four independent domains."""
import ast
from difflib import unified_diff
import json
from zipfile import ZipFile, ZIP_DEFLATED
from build_r16 import HERE, PARENT, sha, write, change


def main():
    binding = json.loads((PARENT/'RUN_BINDING.json').read_bytes())
    assert sha((PARENT/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(PARENT/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'))
        original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items())
    source=dict(original)
    code=source['payload/worker.py'].decode()
    code=change(code, '    initial = {n: p.detach().clone()', '''    import importlib
    adam = importlib.import_module("torch.optim.adam")
    optimizer_calls = {"single": 0, "multi": 0}
    def counted_optimizer(name, fn):
        def call(*a, **k):
            optimizer_calls[name] += 1
            return fn(*a, **k)
        return call
    adam._single_tensor_adam = counted_optimizer("single", adam._single_tensor_adam)
    adam._multi_tensor_adam = counted_optimizer("multi", adam._multi_tensor_adam)
    if args.variant == "candidate":
        opts[args.variant].defaults["foreach"] = True
        for group in opts[args.variant].param_groups:
            group["foreach"] = True
    result["optimizer_impl"] = "foreach" if args.variant == "candidate" else "original"
    initial = {n: p.detach().clone()''')
    code=change(code, '''    tail_counts = None
    if args.variant == "candidate":
        from checkpoint_tail import enable_checkpoint_tail
        tail_counts = enable_checkpoint_tail(models[args.variant])
    else:
        enable_checkpoint(models[args.variant])''', '''    tail_counts = None
    enable_checkpoint(models[args.variant])''')
    code=change(code, '''                    if args.variant == "candidate":
                        key = str((101,111,112,batch*928,512,2048,1.0,2048,2048,1.0,512))
                        if expected_shapes[key] != 24:
                            raise ValueError("unexpected full-checkpoint FFN2 multiplicity")
                        expected_shapes[key] -= 12
                        expected_calls -= 12
''', '')
    code=change(code, '                training.validate_update(torch, model, opts[role], values[role], step)', '''                wanted = {"single": 0, "multi": step} if args.variant == "candidate" else {"single": step, "multi": 0}
                if optimizer_calls != wanted:
                    raise ValueError("actual AdamW dispatch differs: " + repr(optimizer_calls))
                result["optimizer_calls"] = dict(optimizer_calls)
                training.validate_update(torch, model, opts[role], values[role], step)''')
    code=change(code, '''        if any(v != expected_model5 for v in result["final_model_sha256"].values()):
            raise ValueError("historical original model5 SHA differs")
        result["historical_original_model5_exact"] = True''', '''        exact_model5 = all(v == expected_model5 for v in result["final_model_sha256"].values())
        if args.variant == "baseline" and not exact_model5:
            raise ValueError("historical original baseline model5 SHA differs")
        # Candidate acceptance uses all original strict tensor/state/L2 and exact-step gates.
        # Model byte identity is additionally reported, not substituted for those gates.
        result["historical_original_model5_exact"] = exact_model5''')
    source['payload/worker.py']=code.encode()
    source['launch.py']=change(source['launch.py'].decode(), '"checkpoint_tail_skip_ab"', '"foreach_adamw_ab"').encode()
    source['prepare.py']=change(source['prepare.py'].decode(),'AGGRESSIVE3H_20261111_','CONTINUOUS_20261116_').encode()
    with ZipFile(HERE/'R16_FULL16_STRICT/FULL16_PAYLOAD.zip') as z:
        source['submit_once.py']=z.read('submit_once.py')
    out=HERE/'R18_FOREACH_FULL_CKPT';out.mkdir()
    for n,expected in binding['frozen_sidecars'].items():
        raw=(PARENT/n).read_bytes();assert sha(raw)==expected;(out/n).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,filename=n,feature_version=(3,9))
        if raw!=original[n]:diffs.extend(unified_diff(original[n].decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote='/home/share/wujunyi/opt/stage4_sessions/S00/CONTINUOUS_20261116_R18_FOREACH_FULL_CKPT'
    binding['native_argv']=[a.replace(old,remote) if a!='720' else '1800' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version=out.name,remote_root=remote,mode='foreach_adamw_ab',wall_seconds=1800,
        allocator_origin=binding['allocator_origin'].replace(old,remote),batch_deadline_utc=None,
        checkpoint_scopes={'baseline':'full','candidate':'full'},optimizer_impl={'baseline':'original','candidate':'foreach'},
        engineering_revision='CPU_FOREACH_ADAMW_FULL_CHECKPOINT',submission_ordinal=3,
        active_reference='R5_FULL16/A',diff_base=PARENT.name,
        retry_reason='Previously unsubmitted foreach proposal; actual optimizer dispatch plus original full numerical gates; four-domain full-checkpoint comparison.',
        model5_hash_policy='Baseline must equal historical model; candidate hash is reported. Candidate must pass all original numerical and exact optimizer-step gates.',
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps(dict(remote=remote,pin=sha((out/'RUN_BINDING.json').read_bytes()),package=binding['package_sha256'])))


if __name__=='__main__':main()
