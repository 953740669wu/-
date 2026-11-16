"""Detect and restore KML caller control-state changes; keep original training math."""
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
    source['kml_control_guard.c']=(HERE/'kml_control_guard.c').read_bytes()
    code=source['launch.py'].decode()
    code=change(code,'        contracts = allocation(binding)', '''        contracts = allocation(binding)
        execute(EVIDENCE, "control_guard_compile", ["/usr/bin/gcc", "-shared", "-fPIC", "-O2",
                str(ROOT/"kml_control_guard.c"), "-o", str(EVIDENCE/"libcontrol_guard.so")], min(end,time.monotonic()+30))
        save(EVIDENCE/"CONTROL_GUARD_BUILD.json", dict(source_sha256=sha(ROOT/"kml_control_guard.c"),
             library_sha256=sha(EVIDENCE/"libcontrol_guard.so")))''')
    source['launch.py']=code.encode()
    code=source['payload/worker.py'].decode()
    code=change(code,'    native = module._sgemm', '''    control = ctypes.CDLL(str(ROOT.parent/"job_evidence/libcontrol_guard.so"))
    control.read_fpcr.restype = control.read_svcr.restype = ctypes.c_uint64
    control.restore_fpcr.argtypes = [ctypes.c_uint64]
    control.restore_fpcr.restype = control.stop_streaming.restype = None
    result["control_restores"] = dict(fpcr=0, sm=0)
    native = module._sgemm''')
    code=change(code,'        answer = native(*values)', '''        fpcr_before, svcr_before = control.read_fpcr(), control.read_svcr()
        answer = native(*values)
        fpcr_after, svcr_after = control.read_fpcr(), control.read_svcr()
        if fpcr_before != fpcr_after:
            control.restore_fpcr(fpcr_before)
            result["control_restores"]["fpcr"] += 1
        if not svcr_before & 1 and svcr_after & 1:
            control.stop_streaming()
            result["control_restores"]["sm"] += 1
        if native_diagnostic is not None:
            print(json.dumps(dict(event="control", fpcr_before=fpcr_before, fpcr_after=fpcr_after,
                 svcr_before=svcr_before, svcr_after=svcr_after)), file=native_diagnostic, flush=True)''')
    code=change(code,'    if strict:\n        residency(args.output, "strict_end")', '''    if strict:
        expected_model5 = "2e777d61801988322e0709d078b7364629fa01ebd83b8001d5d5f1acfcd12a05"
        if any(v != expected_model5 for v in result["final_model_sha256"].values()):
            raise ValueError("historical original model5 SHA differs")
        result["historical_original_model5_exact"] = True
        residency(args.output, "strict_end")''')
    source['payload/worker.py']=code.encode();out=HERE/'R12_CONTROL_GUARD';out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw=(parent/name).read_bytes();assert sha(raw)==expected;(out/name).write_bytes(raw)
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,feature_version=(3,9))
        if raw!=original.get(n):diffs.extend(unified_diff(original.get(n,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8');write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote=old.replace(parent.name,out.name)
    binding['native_argv']=[a.replace(old,remote) if a!='1800' else '1200' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.update(version=out.name,remote_root=remote,allocator_origin=binding['allocator_origin'].replace(old,remote),
                   submission_ordinal=14,wall_seconds=1200,diff_base=parent.name,
                   retry_reason='R11 stack at SLEEF NEON frintn. Observe FPCR/SVCR around native KML and restore only leaked caller state; require archived model5 hash and original full strict comparison.',
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding);print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__=='__main__':main()
