"""Compare existing checkpointed HBM with the adopted single-domain configuration."""
import ast
from difflib import unified_diff
import json
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from build_r1 import HERE, sha, write, change

BASE = HERE.parents[1] / 'S00/step_barrier_ab_r1_20261111/AB_D16'


def main(active):
    assert active in ('R3_THREEWAY', 'R4_HBM_POLICY')
    adoption = json.loads((HERE / active / 'ADOPTION.json').read_bytes())
    assert adoption['decision'] == 'PROVISIONALLY_ADOPTED'
    assert adoption['checkpoint_scope'] == 'none'
    minimum = adoption['hbm_min_request_KiB']
    binding = json.loads((BASE / 'RUN_BINDING.json').read_bytes())
    assert sha((BASE / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(BASE / 'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        original = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in original.items())
    source = dict(original)
    code = source['payload/worker.py'].decode()
    code = change(code, '    if batch not in (32,64) or ckpt_layers != 12:',
                  '    if batch != 32 or ckpt_layers != (12 if args.arm == "A" else 0):')
    code = change(code, '    enable_checkpoint(models[args.variant])',
                  '''    if args.arm == "A":
        enable_checkpoint(models[args.variant])
    result["checkpoint_scope"] = "full" if args.arm == "A" else "none"
    result["hbm_min_request_KiB"] = int(os.environ["HBM_MIN_KB"])''')
    code = change(code, '                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]',
                  '''                    expected_shapes = dict(pinned["native_shapes"])
                    expected_calls = pinned["kml_calls"]
                    if args.arm == "B":
                        for width, inputs in ((1536,512),(512,512),(2048,512),(512,2048)):
                            key = str((101,111,112,batch*928,width,inputs,1.0,inputs,inputs,1.0,width))
                            if expected_shapes[key] != 24:
                                raise ValueError("unexpected checkpointed forward multiplicity")
                            expected_shapes[key] -= 12
                        expected_calls -= 48
                    trace_matches = logical == expected_calls and shapes == expected_shapes''')
    source['payload/worker.py'] = code.encode()
    code = source['payload/window_control.py'].decode()
    code = change(code, 'if step > 6 and self.arm == \'B\':', 'if step > 6:')
    code = change(code, 'Common fixed window, plus the A-only per-step rendezvous.',
                  'Common fixed window; both arms advance independently after warmup.')
    source['payload/window_control.py'] = code.encode()
    code = source['launch.py'].decode()
    code = change(code, 'if step <= 6 or (arm == "A" and time.monotonic_ns() < window["close_ns"]):',
                  'if step <= 6:')
    code = change(code, 'HBM_MIN_KB="256", HBM_STATS="1"',
                  'HBM_MIN_KB=str(binding["hbm_min_request_KiB"][arm]), HBM_STATS="1"')
    code = change(code, 'S00_MATCHED_CKPT=str(binding["checkpoint_layers"])',
                  'S00_MATCHED_CKPT="12" if arm == "A" else "0"')
    code = change(code, '"step_barrier_ab_fixed_window"', '"adopted_full16_fixed_window"')
    source['launch.py'] = code.encode()
    code = source['prepare.py'].decode()
    source['prepare.py'] = change(code, 'STEP_AB_R1_', 'AGGRESSIVE3H_20261111_R5_').encode()
    # Before deployment, verify the altered native-call expectation against actual R3 CKPT0 evidence.
    reference = json.loads(source['FROZEN_REFERENCE/steps.jsonl'].splitlines()[0])
    expected = dict(reference['native_shapes'])
    for width, inputs in ((1536,512),(512,512),(2048,512),(512,2048)):
        key = str((101,111,112,32*928,width,inputs,1.0,inputs,inputs,1.0,width))
        assert expected[key] == 24
        expected[key] -= 12
    actual = json.loads((HERE / 'R3_THREEWAY/received/job_evidence/perf_candidate_r1/node0/steps.jsonl').read_bytes().splitlines()[0])
    assert expected == actual['native_shapes'] and reference['kml_calls'] - 48 == actual['kml_calls'] == 149
    out = HERE / 'R5_FULL16'; out.mkdir()
    for name, expected_sha in binding['frozen_sidecars'].items():
        raw = (BASE / name).read_bytes()
        assert sha(raw) == expected_sha
        (out / name).write_bytes(raw)
    diffs = []
    for name, raw in sorted(source.items()):
        if raw != original.get(name):
            diffs.extend(unified_diff(original[name].decode().splitlines(True), raw.decode().splitlines(True), 'a/'+name, 'b/'+name))
        if name.endswith('.py'):
            ast.parse(raw, filename=name, feature_version=(3,9))
    (out / 'MINIMAL.diff').write_bytes(''.join(diffs).encode())
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()): z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    remote = '/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R5_FULL16'
    old = binding['remote_root']
    binding['native_argv'] = [a.replace(old, remote).replace('cn22035', 'cn22036') for a in binding['native_argv']]
    binding['native_argv'][binding['native_argv'].index('-T')+1] = '5400'
    binding.update(version='R5_FULL16', remote_root=remote, mode='adopted_full16_fixed_window',
                   allocator_origin=binding['allocator_origin'].replace(old, remote),
                   batch_deadline_utc='2026-11-10T22:08:49+00:00', remaining_queue_seconds=600,
                   wall_seconds=5400, eligible_hosts=['cn22036'], submission_ordinal=6,
                   active_reference=active, checkpoint_layers={'A':12,'B':0},
                   hbm_min_request_KiB={'A':256,'B':minimum},
                   per_step_barrier={'A':False,'B':False},
                   numerical_scope='single-domain full strict evidence inherited; each full16 domain first5 frozen loss checks',
                   stability={'rounds':1,'status':'NOT_REQUIRED_FOR_PROVISIONAL_USE'},
                   diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),'package':binding['package_sha256']}))


if __name__ == '__main__': main(sys.argv[1])
