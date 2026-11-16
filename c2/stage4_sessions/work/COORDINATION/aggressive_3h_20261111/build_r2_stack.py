"""Port the proven 16E fresh-buffer ReLU to the actual 32E checkpointed path."""
import ast
from difflib import unified_diff
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from build_r1 import HERE, BASE, sha, write, change


def main():
    template = HERE / 'R1_F1'
    binding = json.loads((template / 'RUN_BINDING.json').read_bytes())
    with ZipFile(template / 'FULL16_PAYLOAD.zip') as archive:
        manifest = json.loads(archive.read('SOURCE_SHA256.json'))
        source = {n:archive.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in source.items())
    with ZipFile(BASE / 'FULL16_PAYLOAD.zip') as archive:
        original = {n:archive.read(n) for n in json.loads(archive.read('SOURCE_SHA256.json'))}
    code = original['payload/worker.py'].decode()
    code = change(code, '    initial = {n: p.detach().clone()',
                  '''    relu_reuse = None
    if args.variant == "candidate":
        import ffn_relu_reuse as relu_reuse
        relu_reuse.install(models[args.variant])
    initial = {n: p.detach().clone()''')
    code = change(code, '                attn_before = dict(attention.counts) if attention else None',
                  '                relu_before = relu_reuse.calls if relu_reuse else 0\n'
                  '                attn_before = dict(attention.counts) if attention else None')
    code = change(code, '                training.validate_update(torch, model, opts[role], values[role], step)',
                  '''                if relu_reuse:
                    if relu_reuse.calls - relu_before != 24:
                        raise ValueError("ReLU reuse must run for all 12 layers plus checkpoint recomputation")
                    result["relu_reuse_calls"] = relu_reuse.calls
                training.validate_update(torch, model, opts[role], values[role], step)''')
    code = change(code, '    enable_checkpoint(models[args.variant])', '    enable_checkpoint(models[args.variant], "ffn")\n    result["checkpoint_scope"] = "ffn"')
    source['payload/worker.py'] = code.encode()
    old_relu = HERE.parent.parent / 'S00/healthy_node_optimization_20261108/RELU_A/received/payload/ffn_relu_reuse.py'
    raw = old_relu.read_bytes()
    assert sha(raw) == 'c1502a0afd31916fcac38139a17a35d346649b8aff7261e73b945fdcd7a0954e'
    source['payload/ffn_relu_reuse.py'] = change(raw.decode(), '(208,512)', '(928,512)').encode()
    source['launch.py'] = change(source['launch.py'].decode(), '"ffn_checkpoint_ab"', '"relu_reuse_ab"').encode()
    out = HERE / 'R2_STACK'
    out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        data = (BASE / name).read_bytes()
        assert sha(data) == expected
        (out / name).write_bytes(data)
    diffs=[]
    for name,raw in sorted(source.items()):
        if raw != original.get(name):
            diffs.extend(unified_diff(original.get(name,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+name,'b/'+name))
        if name.endswith('.py'):
            ast.parse(raw,filename=name,feature_version=(3,9))
    (out / 'MINIMAL.diff').write_bytes(''.join(diffs).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as archive:
        for name,raw in sorted(source.items()):
            archive.writestr(name,raw)
        archive.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    remote='/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R2_STACK'
    old=binding['remote_root']
    binding['native_argv']=[a.replace(old,remote) for a in binding['native_argv']]
    for selection in binding['hbm_selections'].values():
        selection['allocator_origin']=selection['allocator_origin'].replace(old,remote)
    binding.pop('checkpoint_scopes',None)
    binding.update(version='R2_STACK',mode='relu_reuse_ab',engineering_revision='FFN_CKPT_PLUS_RELU_REUSE_32E_R2',
                   remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   candidate_origin_sha256=sha(old_relu.read_bytes()),
                   submission_ordinal=3,diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    assert source['payload/tests/check_equivalence.py']==original['payload/tests/check_equivalence.py']
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':
    main()
