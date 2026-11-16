"""Test whether the SDPA slowdown is specific to the single-domain allocation."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent=HERE/'R8_F2_DIAG';binding=json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'));original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items());source=dict(original)
    code=change(source['launch.py'].decode(),'binding["mode"] == "checkpoint_tail_skip_ab" and count == 1','binding["mode"] == "checkpoint_tail_skip_ab" and count == 4')
    source['launch.py']=code.encode()
    code=change(source['payload/worker.py'].decode(),'    if strict:\n        residency(args.output, "strict_end")', '''    if strict:
        expected_model5 = "2e777d61801988322e0709d078b7364629fa01ebd83b8001d5d5f1acfcd12a05"
        if any(v != expected_model5 for v in result["final_model_sha256"].values()):
            raise ValueError("historical original model5 SHA differs")
        result["historical_original_model5_exact"] = True
        residency(args.output, "strict_end")''')
    source['payload/worker.py']=code.encode();out=HERE/'R13_FOUR_DOMAIN_TAIL';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(parent/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,feature_version=(3,9))
        if raw!=original[n]:diffs.extend(unified_diff(original[n].decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8');write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote=old.replace(parent.name,out.name)
    replacements={'1800':'1200','cpu=38,mem=24576MB':'cpu=152,mem=98304MB','mem=24576MB':'mem=98304MB','numa[count=1,distribution=pack]':'numa[count=4,distribution=pack]'}
    binding['native_argv']=[replacements.get(a,a).replace(old,remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding['allocation_contract'].update(DDR_limit_MB=98304,DDR_request_MB=98304,HBM_max_MiB_total=15200,allocated_cpus=152,compute_cpus=144,domains=4,reserved_cpus=8)
    binding.update(version=out.name,remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   submission_ordinal=15,wall_seconds=1200,domain_count=4,max_model_updates=240,strict_storage_min_bytes=4*6442450944,diff_base=parent.name,
                   retry_reason='Single-domain SDPA slowdown survives host, checkpoint, wait-policy, serial-forward and direct KML control-state checks. Compare all four physical domains in one die under one allocation; retain every domain and abort if any baseline first step exceeds 90s. Original math/precision and historical model5 hash remain required.',
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding);print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
