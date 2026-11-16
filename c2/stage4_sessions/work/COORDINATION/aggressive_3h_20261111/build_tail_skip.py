"""Keep whole-layer checkpoint memory while omitting its unused final projection replay."""
import ast
from difflib import unified_diff
import json
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    template=HERE/'R4_HBM_POLICY'
    binding=json.loads((template/'RUN_BINDING.json').read_bytes())
    assert sha((template/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(template/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'))
        original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items())
    source=dict(original)
    source['payload/checkpoint_tail.py']=(HERE/'checkpoint_tail.py').read_bytes()
    code=source['payload/worker.py'].decode()
    code=change(code,'    if batch != 32 or ckpt_layers != 0:', '    if batch != 32 or ckpt_layers != 12:')
    code=change(code,'    result["checkpoint_scope"] = "none"', '''    tail_counts = None
    if args.variant == "candidate":
        from checkpoint_tail import enable_checkpoint_tail
        tail_counts = enable_checkpoint_tail(models[args.variant])
    else:
        enable_checkpoint(models[args.variant])
    result["checkpoint_scope"] = "full_tail_skip" if tail_counts is not None else "full"''')
    code=change(code,'                training.validate_update(torch, model, opts[role], values[role], step)', '''                if tail_counts is not None:
                    if tail_counts != {"skipped": step*12, "escaped": 0}:
                        raise RuntimeError("checkpoint tail did not stop exactly once per block: " + repr(tail_counts))
                    result["checkpoint_tail_counts"] = dict(tail_counts)
                training.validate_update(torch, model, opts[role], values[role], step)''')
    code=change(code,'                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]', '''                    expected_shapes = dict(pinned["native_shapes"])
                    expected_calls = pinned["kml_calls"]
                    if args.variant == "candidate":
                        key = str((101,111,112,batch*928,512,2048,1.0,2048,2048,1.0,512))
                        if expected_shapes[key] != 24:
                            raise ValueError("unexpected full-checkpoint FFN2 multiplicity")
                        expected_shapes[key] -= 12
                        expected_calls -= 12
                    trace_matches = logical == expected_calls and shapes == expected_shapes''')
    source['payload/worker.py']=code.encode()
    code=source['launch.py'].decode()
    code=change(code,'"hbm_large_activation_priority"','"checkpoint_tail_skip_ab"')
    code=change(code,'HBM_MIN_KB="256" if variant == "baseline" else "8192"','HBM_MIN_KB="256"')
    source['launch.py']=code.encode()
    out=HERE/'R8_TAIL_SKIP';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(template/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for name,raw in sorted(source.items()):
        if raw!=original.get(name):
            diffs.extend(unified_diff(original.get(name,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+name,'b/'+name))
        if name.endswith('.py'):ast.parse(raw,filename=name,feature_version=(3,9))
    (out/'MINIMAL.diff').write_bytes(''.join(diffs).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    remote='/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R8_TAIL_SKIP';old=binding['remote_root']
    binding['native_argv']=[a.replace(old,remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version='R8_TAIL_SKIP',remote_root=remote,mode='checkpoint_tail_skip_ab',
                   allocator_origin=binding['allocator_origin'].replace(old,remote),active_reference='R5_FULL16/A',
                   checkpoint_layers=12,checkpoint_scopes={'baseline':'full','candidate':'full_tail_skip'},
                   hbm_min_request_KiB={s:256 for s in ('baseline','candidate')},submission_ordinal=7,
                   engineering_revision='CHECKPOINT_LAST_PROJECTION_REPLAY_SKIP',
                   diff_base='R4_HBM_POLICY',diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
