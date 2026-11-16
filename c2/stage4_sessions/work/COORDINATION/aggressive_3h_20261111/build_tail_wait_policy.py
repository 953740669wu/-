"""Test passive OpenMP waiting after observed 30-second SDPA gaps."""
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
    source['run_worker.sh'] = change(source['run_worker.sh'].decode(),
        'export HBM=0 CKPT=0 COMPILE=0',
        'export HBM=0 CKPT=0 COMPILE=0\nexport OMP_WAIT_POLICY=PASSIVE GOMP_SPINCOUNT=0 KMP_BLOCKTIME=0').encode()
    source['payload/worker.py'] = change(source['payload/worker.py'].decode(),
        '    strict = args.phase == "strict"', '''    waiting = {k: os.environ.get(k) for k in ("OMP_WAIT_POLICY", "GOMP_SPINCOUNT", "KMP_BLOCKTIME")}
    if waiting != dict(OMP_WAIT_POLICY="PASSIVE", GOMP_SPINCOUNT="0", KMP_BLOCKTIME="0"):
        raise ValueError("passive wait policy missing")
    result["thread_wait_policy"] = waiting
    strict = args.phase == "strict"''').encode()
    out = HERE / 'R8_F3_PASSIVE'
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
                   allocator_origin=binding['allocator_origin'].replace(old, remote), submission_ordinal=10,
                   diff_base=parent.name, retry_reason='Actual baseline traceback is SDPA; first native calls are fast, inter-GEMM attention gaps approximately 30 seconds. Test passive waiting in both arms; causal hypothesis, not proven mechanism.',
                   thread_wait_policy=dict(OMP_WAIT_POLICY='PASSIVE', GOMP_SPINCOUNT='0', KMP_BLOCKTIME='0'),
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote': remote, 'pin': sha((out / 'RUN_BINDING.json').read_bytes()), 'package': binding['package_sha256']}))


if __name__ == '__main__':
    main()
