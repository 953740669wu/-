"""Bound SDPA parallelism after approximately 30-second stalls in that operator."""
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
        source = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in source.items())
    original = source['payload/worker.py'].decode()
    code = change(original, '    module = sys.modules["kml_ops"]', '''    original_sdpa = torch.nn.functional.scaled_dot_product_attention
    result["sdpa_thread_cap"] = dict(inside=1, outside=36, calls=0)
    def serial_sdpa(*a, **k):
        if torch.get_num_threads() != 36:
            raise RuntimeError("unexpected outside SDPA thread count")
        torch.set_num_threads(1)
        try:
            answer = original_sdpa(*a, **k)
            result["sdpa_thread_cap"]["calls"] += 1
            return answer
        finally:
            torch.set_num_threads(36)
    torch.nn.functional.scaled_dot_product_attention = serial_sdpa
    module = sys.modules["kml_ops"]''')
    code = change(code, '    if strict:\n        residency(args.output, "strict_end")', '''    if strict:
        historical = "2e777d61801988322e0709d078b7364629fa01ebd83b8001d5d5f1acfcd12a05"
        result["historical_original_model5_exact"] = all(v == historical for v in result["final_model_sha256"].values())
        if not result["historical_original_model5_exact"]:
            raise ValueError("five-step model differs from archived original R1_F1 baseline")
        residency(args.output, "strict_end")''')
    ast.parse(code, feature_version=(3, 9));source['payload/worker.py'] = code.encode()
    out = HERE / 'R10_SDPA_SERIAL';out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        raw = (parent / name).read_bytes();assert sha(raw) == expected;(out / name).write_bytes(raw)
    (out / 'MINIMAL.diff').write_text(''.join(unified_diff(original.splitlines(True), code.splitlines(True), 'a/payload/worker.py', 'b/payload/worker.py')), encoding='utf-8')
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()):z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    old = binding['remote_root'];remote = old.replace(parent.name, out.name)
    binding['native_argv'] = [a.replace(old, remote) if a != '1800' else '1200' for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():row['allocator_origin'] = row['allocator_origin'].replace(old, remote)
    binding.update(version=out.name, remote_root=remote,
                   allocator_origin=binding['allocator_origin'].replace(old, remote), submission_ordinal=12, wall_seconds=1200,
                   diff_base=parent.name, retry_reason='SDPA delay persists outside checkpoint and with passive wait. Test serial SDPA forward inside the original 36-core model to avoid nested parallel contention; also require historical original model5 exact SHA.',
                   sdpa_threads=1, original_model5_sha256='2e777d61801988322e0709d078b7364629fa01ebd83b8001d5d5f1acfcd12a05',
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote': remote, 'pin': sha((out / 'RUN_BINDING.json').read_bytes()), 'package': binding['package_sha256']}))


if __name__ == '__main__':main()
