"""Derive one FFN-checkpoint A/B from the actual C1 engineering package."""
import ast
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent / 'S00/hbm_lib_cert_and_bf16_20261111/C1'


def sha(raw):
    return sha256(raw).hexdigest()


def write(path, value):
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def change(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def main():
    binding = json.loads((BASE / 'RUN_BINDING.json').read_bytes())
    manifest = json.loads((BASE / 'SOURCE_SHA256.json').read_bytes())
    assert sha((BASE / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(BASE / 'FULL16_PAYLOAD.zip') as archive:
        source = {name: archive.read(name) for name in manifest}
    assert all(sha(raw) == manifest[name] for name, raw in source.items())
    original = source.copy()
    source['payload/checkpoint_layers.py'] = (HERE / 'checkpoint_layers.py').read_bytes().replace(b'\r\n', b'\n')
    code = source['payload/worker.py'].decode()
    code = change(code, '    enable_checkpoint(models[args.variant])',
                  '    scope = "ffn" if args.variant == "candidate" else "full"\n'
                  '    enable_checkpoint(models[args.variant], scope)\n'
                  '    result["checkpoint_scope"] = scope')
    code = change(code, '                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]',
                  '''                    expected_shapes = dict(pinned["native_shapes"])
                    expected_calls = pinned["kml_calls"]
                    if scope == "ffn":
                        # Only the QKV and attention output forward GEMMs stop being recomputed.
                        for width in (1536, 512):
                            key = str((101, 111, 112, batch*928, width, 512, 1.0, 512, 512, 1.0, width))
                            if expected_shapes[key] != 24:
                                raise ValueError("unexpected frozen attention forward multiplicity")
                            expected_shapes[key] -= 12
                        expected_calls -= 24
                    trace_matches = logical == expected_calls and shapes == expected_shapes''')
    source['payload/worker.py'] = code.encode()
    code = source['launch.py'].decode()
    code = change(code, '        cert = binding["mode"] == "hbm_lib_cert"', '        cert = False')
    code = change(code, '''        need((cert and count == 1 or binding["mode"] == "bf16_bq16" and count in (1,4))
             and 120 < wall <= (1800 if count == 1 else 7200), "wrong wall or mode")''',
                  '''        need(binding["mode"] == "ffn_checkpoint_ab" and count == 1
             and 120 < wall <= 1800, "wrong wall or mode")''')
    code = change(code, '        need(rounds == (0 if binding["domain_count"] == 1 else 3), "invalid pair plan")',
                  '        need(rounds == 1, "one paired measurement only")')
    code = change(code, '            need(selections["baseline"] == selections["candidate"], "BF16 pair must use one HBM selection")\n            build_attention(binding, end)',
                  '            need(selections["baseline"] == selections["candidate"], "pair must use one HBM selection")')
    source['launch.py'] = code.encode()
    source['prepare.py'] = source['prepare.py'].replace(b'HBM_CERT_20261111_', b'AGGRESSIVE3H_20261111_')
    # Private experiment keeps the certified allocator path; this is not a formal-entry adoption.
    out = HERE / 'R1'
    out.mkdir()
    remote = '/home/share/wujunyi/opt/stage4_sessions/S00/AGGRESSIVE3H_20261111_R1'
    for name, expected in binding['frozen_sidecars'].items():
        raw = (BASE / name).read_bytes()
        assert sha(raw) == expected
        (out / name).write_bytes(raw)
    diffs = []
    for name in sorted(source):
        if source[name] != original[name]:
            diffs.extend(unified_diff(original[name].decode().splitlines(True), source[name].decode().splitlines(True),
                                      'a/' + name, 'b/' + name))
        if name.endswith('.py'):
            ast.parse(source[name], filename=name, feature_version=(3,9))
        if name.endswith(('.py', '.sh', '.c')):
            assert b'\r' not in source[name]
    (out / 'MINIMAL.diff').write_bytes(''.join(diffs).encode())
    write(out / 'SOURCE_SHA256.json', {name: sha(raw) for name, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as archive:
        for name, raw in sorted(source.items()):
            archive.writestr(name, raw)
        archive.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    argv = [a.replace(binding['remote_root'], remote) for a in binding['native_argv']]
    selected = dict(HBM_LIB=None, allocator_origin=remote + '/FROZEN_HBM_ALLOCATOR.so', allocator_sha256=binding['allocator_sha256'])
    binding.update(version='R1', engineering_revision='FFN_ONLY_CHECKPOINT_R1', remote_root=remote,
                   mode='ffn_checkpoint_ab', pairs=1, max_model_updates=60, native_argv=argv,
                   allocator_origin=selected['allocator_origin'], hbm_selections={s:selected for s in ('baseline','candidate')},
                   first_pair_projection_seconds=600, batch_deadline_utc='2026-11-10T22:08:49+00:00',
                   remaining_queue_seconds=600, submission_ordinal=1,
                   archived_base_job='2086632', archived_base_package_sha256=binding['package_sha256'],
                   checkpoint_scopes={'baseline':'full','candidate':'ffn'},
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()),
                   stability={'rounds':1,'status':'NOT_REQUIRED_FOR_PROVISIONAL_USE'})
    write(out / 'RUN_BINDING.json', binding)
    assert source['payload/tests/check_equivalence.py'] == original['payload/tests/check_equivalence.py']
    print(json.dumps({'remote':remote,'pin':sha((out/'RUN_BINDING.json').read_bytes()),
                      'package':binding['package_sha256'],'changed_sources':[n for n in source if source[n]!=original[n]]}))


if __name__ == '__main__':
    main()
