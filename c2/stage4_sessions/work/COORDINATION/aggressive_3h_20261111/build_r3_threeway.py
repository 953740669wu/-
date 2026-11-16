"""One allocation: original DDR/CKPT0, adopted HBM/FFN, and HBM/CKPT0."""
import ast
from difflib import unified_diff
import json
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from build_r1 import HERE, BASE, sha, write, change


def main(active):
    assert active in ('R1_F1', 'R2_STACK')
    adoption=json.loads((HERE/active/'ADOPTION.json').read_bytes())
    assert adoption['decision']=='PROVISIONALLY_ADOPTED'
    template=HERE/'R1_F1'
    binding=json.loads((template/'RUN_BINDING.json').read_bytes())
    with ZipFile(template/'FULL16_PAYLOAD.zip') as z:
        source={n:z.read(n) for n in json.loads(z.read('SOURCE_SHA256.json'))}
    with ZipFile(BASE/'FULL16_PAYLOAD.zip') as z:
        original={n:z.read(n) for n in json.loads(z.read('SOURCE_SHA256.json'))}
    code=original['payload/worker.py'].decode()
    code=change(code,'    if batch not in (32,64) or ckpt_layers != 12:',
                     '    if batch != 32 or ckpt_layers not in (0,12):')
    code=change(code,'    if args.variant in ("baseline","candidate"):',
                     '    if args.variant in ("ckpt_hbm","candidate"):')
    code=change(code,'    enable_checkpoint(models[args.variant])',
                     '''    if args.variant == "ckpt_hbm":
        enable_checkpoint(models[args.variant], "ffn")
    result["checkpoint_scope"] = "ffn" if args.variant == "ckpt_hbm" else "none"''')
    code=change(code,'                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]',
                     '''                    expected_shapes = dict(pinned["native_shapes"])
                    expected_calls = pinned["kml_calls"]
                    if args.variant == "ckpt_hbm":
                        for width, inputs in ((2048,512),(512,2048)):
                            key = str((101,111,112,batch*928,width,inputs,1.0,inputs,inputs,1.0,width))
                            if expected_shapes[key] != 12:
                                raise ValueError("unexpected original FFN forward multiplicity")
                            expected_shapes[key] += 12
                        expected_calls += 24
                    trace_matches = logical == expected_calls and shapes == expected_shapes''')
    if active=='R2_STACK':
        with ZipFile(HERE/active/'FULL16_PAYLOAD.zip') as z:
            source['payload/ffn_relu_reuse.py']=z.read('payload/ffn_relu_reuse.py')
        code=change(code,'    initial = {n: p.detach().clone()',
                         '''    relu_reuse = None
    if args.variant != "baseline":
        import ffn_relu_reuse as relu_reuse
        relu_reuse.install(models[args.variant])
    initial = {n: p.detach().clone()''')
        code=change(code,'                attn_before = dict(attention.counts) if attention else None',
                         '                relu_before = relu_reuse.calls if relu_reuse else 0\n'
                         '                attn_before = dict(attention.counts) if attention else None')
        code=change(code,'                training.validate_update(torch, model, opts[role], values[role], step)',
                         '''                if relu_reuse:
                    expected_relu = 24 if args.variant == "ckpt_hbm" else 12
                    if relu_reuse.calls - relu_before != expected_relu:
                        raise ValueError("ReLU scope count differs")
                    result["relu_reuse_calls"] = relu_reuse.calls
                training.validate_update(torch, model, opts[role], values[role], step)''')
    source['payload/worker.py']=code.encode()
    code=source['launch.py'].decode()
    code=change(code,'"ffn_checkpoint_ab"','"original_vs_hbm_threeway"')
    code=change(code,'10*count + 50*count*binding["pairs"]','90*count')
    code=change(code,'for variant in ("baseline","candidate"):', 'for variant in ("baseline","ckpt_hbm","candidate"):')
    code=change(code,'order = ("baseline","candidate") if run % 2 else ("candidate","baseline")',
                     'order = ("baseline","ckpt_hbm","candidate")')
    code=change(code,'S00_MATCHED_CKPT=str(binding["checkpoint_layers"])',
                     'S00_MATCHED_CKPT="12" if variant == "ckpt_hbm" else "0"')
    code=change(code,'binding["hbm_selections"][variant]["HBM_LIB"]',
                     'binding["hbm_selections"]["candidate"]["HBM_LIB"]')
    code=change(code,'''        env.update(M23_HBM_LIBRARY=cfg["library"], M23_HBM_LIBRARY_SHA=cfg["library_sha256"],
                   HBM_NODE=str(cfg["hbm_node"]), HBM_MB=str(cfg["cap_MiB"]), HBM_MIN_KB="256", HBM_STATS="1")''',
                     '''        if variant != "baseline":
            env.update(M23_HBM_LIBRARY=cfg["library"], M23_HBM_LIBRARY_SHA=cfg["library_sha256"],
                       HBM_NODE=str(cfg["hbm_node"]), HBM_MB=str(cfg["cap_MiB"]), HBM_MIN_KB="256", HBM_STATS="1")''')
    code=change(code,'        need(0 < resident <= cfg["cap_MiB"], "positive bounded HBM residency required")',
                     '''        need(resident == 0 if variant == "baseline" else 0 < resident <= cfg["cap_MiB"],
             "DDR must have zero hugepage residency; HBM must be positive and bounded")''')
    source['launch.py']=code.encode()
    out=HERE/'R3_THREEWAY';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(BASE/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
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
    remote='/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R3_THREEWAY';old=binding['remote_root']
    binding['native_argv']=[a.replace(old,remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.pop('checkpoint_scopes',None)
    binding.update(version='R3_THREEWAY',remote_root=remote,mode='original_vs_hbm_threeway',
                   allocator_origin=binding['allocator_origin'].replace(old,remote),
                   max_model_updates=90,first_pair_projection_seconds=1000,submission_ordinal=4,
                   active_reference=active,engineering_revision='DDR0_HBM_FFN_HBM0_THREEWAY',
                   phases={'baseline':'DDR CKPT0 original FP32 KML engineering path','ckpt_hbm':'adopted HBM FFN checkpoint','candidate':'HBM CKPT0'},
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main(sys.argv[1])
