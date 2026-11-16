"""Test FP32 denormal flushing against pinned completed original snapshots."""
import ast
from difflib import unified_diff
import json
from zipfile import ZipFile, ZIP_DEFLATED
from build_r16 import HERE, sha, write, change


def main():
    parent=HERE/'R16_FULL16_STRICT'
    review=json.loads((parent/'REVIEW.json').read_bytes())
    assert review['cleanup_passed'] and review['domains']['node4']['phases']['baseline']['passed']
    ref=parent/'received/FROZEN_REFERENCE_NODE4'
    provenance=json.loads((ref/'PROVENANCE.json').read_bytes())
    assert provenance['matches_completed_reference_receipt'] and provenance['job_id']=='2146931'
    binding=json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest=json.loads(z.read('SOURCE_SHA256.json'));original={n:z.read(n) for n in manifest}
    assert all(sha(raw)==manifest[n] for n,raw in original.items())
    source=dict(original)
    code=source['payload/worker.py'].decode()
    code=change(code,'    import torch\n','''    import torch
    if not strict or args.variant != "candidate":
        raise ValueError("FTZ experiment requires the bound strict-only candidate")
    if not torch.set_flush_denormal(True):
        raise RuntimeError("denormal flush unsupported by this runtime")
    result["flush_denormal_requested"] = True
''')
    code=change(code,'    result["runtime"] = runtime','''    result["runtime"] = runtime
    probe = torch.ones(36*4096, dtype=torch.int32).view(torch.float32)
    flushed = probe * 2.0
    nonzero = int(torch.count_nonzero(flushed.view(torch.int32)))
    result["denormal_probe"] = dict(input_bits=1, elements=probe.numel(), nonzero_output_bits=nonzero)
    if nonzero:
        raise RuntimeError("denormal flush not effective for the exercised CPU tensor lanes")
    del probe, flushed''')
    code=change(code,'args.reference / args.output.name / f"strict_step{step}.pt"','args.reference / f"strict_step{step}.pt"')
    code=change(code,'ref_dir = args.reference / args.output.name','ref_dir = args.reference')
    code=change(code,'''    tail_counts = None
    if args.variant == "candidate":
        from checkpoint_tail import enable_checkpoint_tail
        tail_counts = enable_checkpoint_tail(models[args.variant])
    else:
        enable_checkpoint(models[args.variant])''','''    tail_counts = None
    enable_checkpoint(models[args.variant])''')
    code=change(code,'''                    if args.variant == "candidate":
                        key = str((101,111,112,batch*928,512,2048,1.0,2048,2048,1.0,512))
                        if expected_shapes[key] != 24:
                            raise ValueError("unexpected full-checkpoint FFN2 multiplicity")
                        expected_shapes[key] -= 12
                        expected_calls -= 12
''','')
    source['payload/worker.py']=code.encode()
    code=source['launch.py'].decode()
    code=change(code,'"checkpoint_tail_skip_ab"','"fp32_flush_denormal_reference"')
    code=change(code,'binding["max_model_updates"] == 10*count','binding["max_model_updates"] == 5*count')
    code=change(code,'for variant in ("baseline","candidate"):','for variant in ("candidate",):')
    code=change(code,'str(EVIDENCE / "strict_baseline")]','binding["external_reference_root"]]')
    a=code.index('            if name == "strict" and variant == "baseline" and step == 2:')
    b=code.index('            if now >= deadline:',a)
    code=code[:a]+'''            if name == "strict" and step > 1:
                released = read(barriers / f"{step-1}.release")["release_at_ns"] / 1e9
                if now - released > binding["update_timeout_seconds"] and any(
                    len((out/f"node{n}"/"steps.jsonl").read_text().splitlines()) < step-1 for n in proc
                ):
                    raise TimeoutError("candidate update exceeded 120 seconds; stop this domain")
'''+code[b:]
    source['launch.py']=code.encode()
    code=source['prepare.py'].decode()
    code=change(code,'    return binding','''    ref = json.loads((root/"EXTERNAL_REFERENCE.json").read_bytes())
    external = Path(binding["external_reference_root"])
    need(str(external) == ref["remote_root"], "external reference directory differs")
    for name, expected in ref["metadata_sha256"].items():
        need(sha(external/name) == expected, "external reference metadata changed: " + name)
    receipt = json.loads((external/"result.json").read_bytes())
    need(receipt["status"] == "PASS_STRICT_REFERENCE5" and receipt["completed_updates"] == 5,
         "external reference is incomplete")
    need([(r["bytes"],r["sha256"]) for r in ref["snapshots"]] ==
         [(r["bytes"],r["sha256"]) for r in receipt["reference_snapshots"]], "reference identities differ")
    for row in ref["snapshots"]:
        need((external/row["name"]).stat().st_size == row["bytes"], "reference snapshot size changed")
    return binding''')
    source['prepare.py']=code.encode()
    source['submit_once.py']=change(source['submit_once.py'].decode(),
        'binding["wall_seconds"] == 1800','binding["wall_seconds"] == 900').encode()
    out=HERE/'R19_FTZ_REFERENCE';out.mkdir()
    for n,expected in binding['frozen_sidecars'].items():
        raw=(parent/n).read_bytes();assert sha(raw)==expected;(out/n).write_bytes(raw)
    external=binding['remote_root']+'/FROZEN_REFERENCE_NODE4'
    write(out/'EXTERNAL_REFERENCE.json',dict(job_id='2146931',host='cn22035',node=4,remote_root=external,
        source_review_sha256=sha((parent/'REVIEW.json').read_bytes()),
        metadata_sha256={n:sha((ref/n).read_bytes()) for n in ('PROVENANCE.json','result.json','PAIRING.json','steps.jsonl')},
        snapshots=provenance['files']))
    binding['frozen_sidecars']['EXTERNAL_REFERENCE.json']=sha((out/'EXTERNAL_REFERENCE.json').read_bytes())
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'):ast.parse(raw,filename=n,feature_version=(3,9))
        if raw!=original[n]:diffs.extend(unified_diff(original[n].decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()):z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote='/home/share/wujunyi/opt/stage4_sessions/S00/CONTINUOUS_20261116_R19_FTZ_REFERENCE'
    binding['native_argv']=[a.replace(old,remote) if a!='1800' else '900' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin']=row['allocator_origin'].replace(old,remote)
    binding.pop('baseline_first_update_timeout_seconds',None)
    binding.update(version=out.name,remote_root=remote,mode='fp32_flush_denormal_reference',wall_seconds=900,
        allocator_origin=binding['allocator_origin'].replace(old,remote),max_model_updates=80,
        checkpoint_scopes={'baseline':'full','candidate':'full'},engineering_revision='FP32_FTZ_REFERENCE_CHECK',
        submission_ordinal=4,external_reference_root=external,update_timeout_seconds=120,
        strict_storage_min_bytes=1024**3,diff_base=parent.name,
        retry_reason='Test whether denormal flushing resolves slow original FP32 computation. Hypothesis only; require effective tensor probe and unchanged full numerical gates, using exact completed original references.',
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps(dict(remote=remote,pin=sha((out/'RUN_BINDING.json').read_bytes()),package=binding['package_sha256'])))


if __name__=='__main__':main()
