"""Capture a native SDPA stack in one bounded diagnostic allocation."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent=HERE/'R8_F2_DIAG';binding=json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'));original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items());source=dict(original)
    source['native_trace.c']=(HERE/'native_trace.c').read_bytes()
    code=source['launch.py'].decode()
    code=change(code,'        contracts = allocation(binding)', '''        contracts = allocation(binding)
        execute(EVIDENCE, "native_trace_compile", ["/usr/bin/gcc", "-shared", "-fPIC", "-O0", "-g", "-pthread",
                str(ROOT/"native_trace.c"), "-o", str(EVIDENCE/"libnative_trace.so")], min(end,time.monotonic()+30))
        save(EVIDENCE/"NATIVE_TRACE_BUILD.json", dict(source_sha256=sha(ROOT/"native_trace.c"),
             library_sha256=sha(EVIDENCE/"libnative_trace.so")))''')
    source['launch.py']=code.encode()
    code=source['payload/worker.py'].decode()
    code=change(code,'                    faulthandler.dump_traceback_later(30, repeat=False)', '''                    native_trace = ctypes.CDLL(str(ROOT.parent/"job_evidence/libnative_trace.so"))
                    if native_trace.trace_start() != 0:
                        raise RuntimeError("native trace timer failed")
                    faulthandler.dump_traceback_later(30, repeat=False)''')
    code=change(code,'                        faulthandler.cancel_dump_traceback_later()', '''                        native_trace.trace_stop()
                        faulthandler.cancel_dump_traceback_later()''')
    source['payload/worker.py']=code.encode()
    out=HERE/'R11_NATIVE_TRACE';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(parent/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,feature_version=(3,9))
        if raw!=original.get(n):diffs.extend(unified_diff(original.get(n,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote=old.replace(parent.name,out.name)
    binding['native_argv']=[a.replace(old,remote) if a!='1800' else '300' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version=out.name,remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   submission_ordinal=13,wall_seconds=300,diff_base=parent.name,
                   diagnostic_only=True,retry_reason='SDPA delay survives passive waiting, removal from checkpoint and serial forward. Capture native training-thread stack at 25 seconds; no training math changes.',
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
