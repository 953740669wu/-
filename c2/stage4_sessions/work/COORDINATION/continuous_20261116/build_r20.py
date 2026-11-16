"""Full16 timing: validated tail replay on fifteen domains, original on node4."""
import ast
from difflib import unified_diff
import json
from zipfile import ZipFile, ZIP_DEFLATED
from build_r16 import HERE, sha, write, change


def main():
    strict = HERE/'R16_FULL16_STRICT'
    gate = json.loads((strict/'REVIEW.json').read_bytes())
    tail_domains = [i for i in range(16) if gate['domains'][f'node{i}']['strict5_passed']]
    assert tail_domains == [i for i in range(16) if i != 4]
    assert gate['cleanup_passed'] and gate['job_id'] == '2146931'
    assert all(d['phases']['baseline']['passed'] for d in gate['domains'].values())
    for i in tail_domains:
        phase = gate['domains'][f'node{i}']['phases']['candidate']
        assert phase['metrics'] == 3880 and not phase['failed_metrics']
    parent = HERE.parent/'aggressive_3h_20261111/R5_FULL16'
    binding = json.loads((parent/'RUN_BINDING.json').read_bytes())
    assert sha((parent/'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent/'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        original = {n:z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n,raw in original.items())
    source = dict(original)
    strict_binding = json.loads((strict/'RUN_BINDING.json').read_bytes())
    assert sha((strict/'FULL16_PAYLOAD.zip').read_bytes()) == strict_binding['package_sha256']
    assert strict_binding['numerical'] == binding['numerical']
    with ZipFile(strict/'FULL16_PAYLOAD.zip') as z:
        sm = json.loads(z.read('SOURCE_SHA256.json'))
        for n in ('payload/baseline/kml_ops.py','payload/baseline/s4_models.py',
                  'payload/engineering_training.py','payload/tests/check_equivalence.py'):
            assert source[n] == z.read(n) and sha(source[n]) == sm[n]
        for n in ('payload/checkpoint_tail.py','payload/checkpoint_layers.py'):
            raw = z.read(n); assert sha(raw) == sm[n]; source[n] = raw
        submit = z.read('submit_once.py').decode()
    code = change(source['payload/worker.py'].decode(),
        'from checkpoint_layers import enable_checkpoint',
        'from checkpoint_layers import enable_checkpoint\nfrom checkpoint_tail import enable_checkpoint_tail')
    code = change(code, 'ckpt_layers != (12 if args.arm == "A" else 0)', 'ckpt_layers != 12')
    code = change(code, '''    if args.arm == "A":
        enable_checkpoint(models[args.variant])
    result["checkpoint_scope"] = "full" if args.arm == "A" else "none"''', '''    profile = json.loads((args.descriptor.parent / "PROFILE_GATE.json").read_bytes())
    node = guard["receipt"]["node"]
    if args.output.name != "node" + str(node):
        raise ValueError("profile domain differs from actual CPU allocation")
    use_tail = args.arm == "B" and node in profile["tail_domains"]
    tail_counts = None
    if use_tail:
        tail_counts = enable_checkpoint_tail(models[args.variant])
    else:
        enable_checkpoint(models[args.variant])
    result["checkpoint_scope"] = "full_tail_skip" if use_tail else "full"
    result["profile_domain"] = node''')
    code = change(code, 'if args.arm == "B":', 'if use_tail:')
    code = change(code, '((1536,512),(512,512),(2048,512),(512,2048))', '((512,2048),)')
    code = change(code, 'expected_calls -= 48', 'expected_calls -= 12')
    code = change(code, '    finish_backend(runtime, expected)', '''    if tail_counts is not None:
        result["checkpoint_tail_counts"] = dict(tail_counts)
        if tail_counts != dict(skipped=12*result["completed_updates"], escaped=0):
            raise ValueError("tail replay count or early-stop guard differs")
    finish_backend(runtime, expected)''')
    source['payload/worker.py'] = code.encode()
    source['launch.py'] = change(source['launch.py'].decode(),
        'S00_MATCHED_CKPT="12" if arm == "A" else "0"', 'S00_MATCHED_CKPT="12"').encode()
    code = change(source['prepare.py'].decode(), 'AGGRESSIVE3H_20261111_R5_', 'CONTINUOUS_20261116_')
    code = change(code, '    return binding', '''    gate = json.loads((root/"STRICT16_REVIEW.json").read_bytes())
    profile = json.loads((root/"PROFILE_GATE.json").read_bytes())
    need(profile["tail_domains"] == [i for i in range(16) if i != 4]
         and profile["original_domains"] == [4], "wrong mixed profile")
    need(gate["cleanup_passed"] and gate["job_id"] == "2146931", "strict source not closed")
    need(all(d["phases"]["baseline"]["passed"] for d in gate["domains"].values()), "original coverage incomplete")
    for node in profile["tail_domains"]:
        value = gate["domains"]["node"+str(node)]
        phase = value["phases"]["candidate"]
        need(value["strict5_passed"] and phase["metrics"] == 3880
             and not phase["failed_metrics"], "changed domain strict gate incomplete")
    return binding''')
    source['prepare.py'] = code.encode()
    source['submit_once.py'] = change(submit,
        'binding["wall_seconds"] == 1800', 'binding["wall_seconds"] == 7200').encode()
    out = HERE/'R20_MIXED_TAIL_WINDOW'
    out.mkdir()
    for name,expected in binding['frozen_sidecars'].items():
        raw = (parent/name).read_bytes(); assert sha(raw) == expected; (out/name).write_bytes(raw)
    (out/'STRICT16_REVIEW.json').write_bytes((strict/'REVIEW.json').read_bytes())
    profile = dict(tail_domains=tail_domains,original_domains=[4],source_job_id='2146931',
        strict_review_sha256=sha((strict/'REVIEW.json').read_bytes()),
        strict_binding_sha256=sha((strict/'RUN_BINDING.json').read_bytes()),
        helper_sha256={n:sha(source[n]) for n in ('payload/checkpoint_layers.py','payload/checkpoint_tail.py')},
        host='cn22035',no_ftz=True,no_foreach=True)
    write(out/'PROFILE_GATE.json',profile)
    for name in ('STRICT16_REVIEW.json','PROFILE_GATE.json'):
        binding['frozen_sidecars'][name] = sha((out/name).read_bytes())
    diffs=[]
    for n,raw in source.items():
        if n.endswith('.py'): ast.parse(raw,filename=n,feature_version=(3,9))
        if raw != original.get(n):
            diffs.extend(unified_diff(original.get(n,b'').decode().splitlines(True),raw.decode().splitlines(True),'a/'+n,'b/'+n))
    (out/'MINIMAL.diff').write_text(''.join(diffs),encoding='utf-8')
    write(out/'SOURCE_SHA256.json',{n:sha(raw) for n,raw in source.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,raw in sorted(source.items()): z.writestr(n,raw)
        z.write(out/'SOURCE_SHA256.json','SOURCE_SHA256.json')
    old=binding['remote_root'];remote='/home/share/wujunyi/opt/stage4_sessions/S00/CONTINUOUS_20261116_R20_MIXED_TAIL_WINDOW'
    binding['native_argv']=[a.replace(old,remote).replace('cn22036','cn22035') for a in binding['native_argv']]
    binding['native_argv'][binding['native_argv'].index('-T')+1]='7200'
    binding.update(version=out.name,remote_root=remote,eligible_hosts=['cn22035'],
        allocator_origin=binding['allocator_origin'].replace(old,remote),batch_deadline_utc=None,
        wall_seconds=7200,submission_ordinal=4,active_reference='R5_FULL16/A',
        checkpoint_layers={'A':12,'B':12},
        numerical_scope='R16 original strict gates for each changed domain; original unchanged on node4; first5 frozen loss checks in both timing arms',
        mixed_profile=profile,
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json',binding)
    print(json.dumps(dict(remote=remote,pin=sha((out/'RUN_BINDING.json').read_bytes()),package=binding['package_sha256'])))


if __name__ == '__main__':
    main()
