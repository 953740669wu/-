"""A deliberately scoped domain-1 candidate test; never report full-node throughput."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent=HERE/'R13_FOUR_DOMAIN_TAIL';binding=json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'));source={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in source.items())
    original=source['launch.py'].decode();code=change(original,
        'need(binding["max_model_updates"] == 10*count + 50*count*binding["pairs"], "wrong update bound")',
        'need(binding["max_model_updates"] == 60 and binding["active_domain_count"] == 1, "wrong scoped update bound")')
    code=change(code,'        contracts = allocation(binding)', '''        allocated_contracts = allocation(binding)
        need(binding["active_cpu_node"] == 1 and 1 in allocated_contracts, "domain1 not allocated")
        contracts = {1: allocated_contracts[1]}
        save(EVIDENCE/"ACTIVE_CONTRACTS.json", dict(allocated=allocated_contracts, active=contracts,
             active_compute_cpus=36, native_allocated_cpus=152,
             scope="domain1 only; remaining allocated domains intentionally idle; no whole-node throughput claim"))''')
    ast.parse(code,feature_version=(3,9));source['launch.py']=code.encode();out=HERE/'R14_DOMAIN1_TAIL';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(parent/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    (out/'MINIMAL.diff').write_text(''.join(unified_diff(original.splitlines(True),code.splitlines(True),'a/launch.py','b/launch.py')),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote=old.replace(parent.name,out.name)
    binding['native_argv']=[a.replace(old,remote) if a!='1200' else '900' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding['allocation_contract'].update(compute_cpus=36,reserved_cpus=116,active_domains=1,active_HBM_cap_MiB=3800)
    binding.update(version=out.name,remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   submission_ordinal=16,wall_seconds=900,active_domain_count=1,active_cpu_node=1,max_model_updates=60,
                   strict_storage_min_bytes=6442450944,diff_base=parent.name,
                   retry_reason='R13 retained all four domains; domain0 stalled in update2 while domains1-3 completed near9s. This separate experiment explicitly uses domain1 only within a native4-domain allocation. It cannot support four-/sixteen-domain throughput or per-allocation efficiency claims.',
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding);print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
