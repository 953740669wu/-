"""Prepare FP32 math SDPA against the same exact original five-step reference."""
import ast
from difflib import unified_diff
import json
from zipfile import ZipFile, ZIP_DEFLATED
from build_r16 import HERE, sha, write, change


def main():
    parent = HERE/'R19_FTZ_REFERENCE'
    binding = json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert json.loads((parent/'REVIEW.json').read_bytes())['cleanup_passed']
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        original = {n:z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n,raw in original.items())
    source = dict(original)
    code = source['payload/worker.py'].decode()
    code = change(code, '''    if not strict or args.variant != "candidate":
        raise ValueError("FTZ experiment requires the bound strict-only candidate")
    if not torch.set_flush_denormal(True):
        raise RuntimeError("denormal flush unsupported by this runtime")
    result["flush_denormal_requested"] = True
''', '''    if not strict or args.variant != "candidate":
        raise ValueError("math SDPA requires the bound strict-only candidate")
    from torch.nn.attention import sdpa_kernel, SDPBackend
    original_sdpa = torch.nn.functional.scaled_dot_product_attention
    result["math_sdpa"] = dict(calls=0, backend="MATH", dtype="float32")

    def math_sdpa(q, k, v, *positional, **keywords):
        if any(t.device.type != "cpu" or t.dtype != torch.float32 for t in (q,k,v)):
            raise ValueError("math SDPA input must be CPU FP32")
        with sdpa_kernel(SDPBackend.MATH):
            flags = dict(math=torch.backends.cuda.math_sdp_enabled(),
                         flash=torch.backends.cuda.flash_sdp_enabled(),
                         efficient=torch.backends.cuda.mem_efficient_sdp_enabled(),
                         cudnn=torch.backends.cuda.cudnn_sdp_enabled())
            if flags != dict(math=True,flash=False,efficient=False,cudnn=False):
                raise ValueError("math-only SDPA dispatch not established")
            result["math_sdpa"]["flags"] = flags
            result["math_sdpa"]["calls"] += 1
            return original_sdpa(q, k, v, *positional, **keywords)

    torch.nn.functional.scaled_dot_product_attention = math_sdpa
''')
    start = code.index('    probe = torch.ones(36*4096, dtype=torch.int32)')
    end = code.index('    del probe, flushed', start) + len('    del probe, flushed\n')
    code = code[:start] + code[end:]
    code = change(code, '''        if any(v != expected_model5 for v in result["final_model_sha256"].values()):
            raise ValueError("historical original model5 SHA differs")
        result["historical_original_model5_exact"] = True''', '''        result["historical_original_model5_exact"] = all(
            v == expected_model5 for v in result["final_model_sha256"].values())
        if result["math_sdpa"]["calls"] != 24 * result["completed_updates"]:
            raise ValueError("full checkpoint math SDPA call coverage differs")''')
    source['payload/worker.py'] = code.encode()
    source['launch.py'] = change(source['launch.py'].decode(),
        'fp32_flush_denormal_reference', 'fp32_math_sdpa_reference').encode()
    out = HERE/'R21_MATH_SDPA_REFERENCE'; out.mkdir()
    for n,expected in binding['frozen_sidecars'].items():
        raw=(parent/n).read_bytes(); assert sha(raw)==expected; (out/n).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'): ast.parse(raw,filename=n,feature_version=(3,9))
        if raw != original[n]:
            diffs.extend(unified_diff(original[n].decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()): z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old = binding['remote_root']; remote='/home/share/wujunyi/opt/stage4_sessions/S00/CONTINUOUS_20261116_R21_MATH_SDPA_REFERENCE'
    binding['native_argv']=[a.replace(old,remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values(): row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version=out.name,remote_root=remote,mode='fp32_math_sdpa_reference',
        allocator_origin=binding['allocator_origin'].replace(old,remote),submission_ordinal=5,
        engineering_revision='FP32_MATH_SDPA_REFERENCE_CHECK',diff_base=parent.name,
        retry_reason='Separate FP32 math SDPA candidate after FTZ did not resolve slow CPU flash. Original tensor/state/relative/exact-step gates unchanged; historical model SHA diagnostic only, as arithmetic ordering may differ. No timing adoption on numerical failure.',
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps(dict(remote=remote,pin=sha((out/'RUN_BINDING.json').read_bytes()),package=binding['package_sha256'])))


if __name__ == '__main__':
    main()
