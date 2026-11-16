"""Avoid SDPA inside checkpoint; test tail replay omission against the FFN baseline."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent = HERE / 'R8_F2_DIAG'
    binding = json.loads((parent / 'RUN_BINDING.json').read_bytes())
    assert sha((parent / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent / 'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        original = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in original.items())
    source = dict(original)
    code = source['payload/checkpoint_tail.py'].decode()
    code = change(code, 'original_layer = layer.forward', 'original_layer = layer._ff_block')
    code = change(code, 'layer.forward = lambda', 'layer._ff_block = lambda')
    source['payload/checkpoint_tail.py'] = code.encode()
    code = source['payload/worker.py'].decode()
    code = change(code, '        enable_checkpoint(models[args.variant])', '        enable_checkpoint(models[args.variant], "ffn")')
    code = change(code, '"full_tail_skip" if tail_counts is not None else "full"', '"ffn_tail_skip" if tail_counts is not None else "ffn"')
    code = change(code, 'unexpected full-checkpoint FFN2 multiplicity', 'unexpected FFN-checkpoint projection multiplicity')
    source['payload/worker.py'] = code.encode()
    out = HERE / 'R9_FFN_TAIL'
    out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        raw = (parent / name).read_bytes()
        assert sha(raw) == expected
        (out / name).write_bytes(raw)
    diffs = []
    for n, raw in source.items():
        if n.endswith('.py'):
            ast.parse(raw, feature_version=(3, 9))
        if raw != original[n]:
            diffs.extend(unified_diff(original[n].decode().splitlines(True), raw.decode().splitlines(True), 'a/'+n, 'b/'+n))
    (out / 'MINIMAL.diff').write_text(''.join(diffs), encoding='utf-8')
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()):
            z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    old = binding['remote_root']; remote = old.replace(parent.name, out.name)
    binding['native_argv'] = [a.replace(old, remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():
        row['allocator_origin'] = row['allocator_origin'].replace(old, remote)
    binding.update(version=out.name, remote_root=remote,
                   allocator_origin=binding['allocator_origin'].replace(old, remote), submission_ordinal=11,
                   active_reference='R1_F1/candidate',
                   checkpoint_scopes={'baseline':'ffn','candidate':'ffn_tail_skip'},
                   diff_base=parent.name, retry_reason='Localize whether SDPA inside whole-layer checkpoint causes long waits; use the already accepted FFN-only baseline in both arms, then test omission of final FFN2 replay GEMM. Default thread waiting, not unproven R8_F3 policy.',
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote': remote, 'pin': sha((out / 'RUN_BINDING.json').read_bytes()), 'package': binding['package_sha256']}))


if __name__ == '__main__':
    main()
