"""Test giving scarce HBM to large activations instead of small parameter/state buffers."""
import ast
from difflib import unified_diff
import json
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, BASE, sha, write, change


def main(active):
    assert active in ('R1_F1','R3_THREEWAY')
    decision=json.loads((HERE/active/'ADOPTION.json').read_bytes())
    assert decision['decision']=='PROVISIONALLY_ADOPTED'
    scope=decision.get('checkpoint_scope','ffn')
    assert scope in ('ffn','none')
    binding=json.loads((HERE/'R1_F1/RUN_BINDING.json').read_bytes())
    with ZipFile(HERE/'R1_F1/FULL16_PAYLOAD.zip') as z:
        source={n:z.read(n) for n in json.loads(z.read('SOURCE_SHA256.json'))}
    with ZipFile(BASE/'FULL16_PAYLOAD.zip') as z:
        original={n:z.read(n) for n in json.loads(z.read('SOURCE_SHA256.json'))}
    code=original['payload/worker.py'].decode()
    code=change(code,'    if batch not in (32,64) or ckpt_layers != 12:',
                f'    if batch != 32 or ckpt_layers != {12 if scope=="ffn" else 0}:')
    install='    enable_checkpoint(models[args.variant], "ffn")\n' if scope=='ffn' else ''
    code=change(code,'    enable_checkpoint(models[args.variant])',install+f'    result["checkpoint_scope"] = "{scope}"')
    code=change(code,'    result["hbm_allocator"] = hbm',
                '    hbm["min_request_KiB"] = int(os.environ["HBM_MIN_KB"])\n    result["hbm_allocator"] = hbm')
    source['payload/worker.py']=code.encode()
    code=source['launch.py'].decode()
    code=change(code,'"ffn_checkpoint_ab"','"hbm_large_activation_priority"')
    code=change(code,'HBM_MIN_KB="256", HBM_STATS="1"',
                'HBM_MIN_KB="256" if variant == "baseline" else "8192", HBM_STATS="1"')
    code=change(code,'order = ("baseline","candidate") if run % 2 else ("candidate","baseline")',
                'order = ("candidate","baseline")')
    source['launch.py']=code.encode()
    out=HERE/'R4_HBM_POLICY';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(BASE/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for name,raw in sorted(source.items()):
        if raw!=original.get(name):diffs.extend(unified_diff(original.get(name,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+name,'b/'+name))
        if name.endswith('.py'):ast.parse(raw,filename=name,feature_version=(3,9))
    (out/'MINIMAL.diff').write_bytes(''.join(diffs).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    remote='/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R4_HBM_POLICY';old=binding['remote_root']
    binding['native_argv']=[a.replace(old,remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version='R4_HBM_POLICY',remote_root=remote,mode='hbm_large_activation_priority',
        allocator_origin=binding['allocator_origin'].replace(old,remote),active_reference=active,
        checkpoint_layers=12 if scope=='ffn' else 0,checkpoint_scopes={s:scope for s in ('baseline','candidate')},
        hbm_min_request_KiB={'baseline':256,'candidate':8192},submission_ordinal=5,
        performance_order=['candidate','baseline'],
        engineering_revision='HBM_LARGE_ACTIVATION_PRIORITY',
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main(sys.argv[1])
