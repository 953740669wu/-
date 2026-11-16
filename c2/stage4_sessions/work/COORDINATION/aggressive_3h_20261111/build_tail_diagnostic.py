"""Locate the reproduced baseline stall without changing training mathematics."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent = HERE / 'R8_F1_TAIL_SKIP'
    binding = json.loads((parent / 'RUN_BINDING.json').read_bytes())
    assert sha((parent / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent / 'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        source = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in source.items())
    original = source['payload/worker.py'].decode()
    code = change(original, 'import ctypes\n', 'import ctypes\nimport faulthandler\n')
    code = change(code, '    shapes = {}', '''    shapes = {}
    native_diagnostic = None''')
    code = change(code, '        return native(*values)', '''        if native_diagnostic is not None:
            print(json.dumps(dict(event="enter", shape=key, at_ns=time.monotonic_ns())), file=native_diagnostic, flush=True)
        answer = native(*values)
        if native_diagnostic is not None:
            print(json.dumps(dict(event="exit", shape=key, at_ns=time.monotonic_ns())), file=native_diagnostic, flush=True)
        return answer''')
    code = change(code, '                begin = time.monotonic_ns()', '''                diagnostic_first = strict and args.variant == "baseline" and step == 1
                if diagnostic_first:
                    native_diagnostic = (args.output / "native_first_step.jsonl").open("x")
                    faulthandler.dump_traceback_later(30, repeat=False)
                begin = time.monotonic_ns()''')
    code = change(code, '                finally:\n                    for handle in handles:', '''                finally:
                    if diagnostic_first:
                        faulthandler.cancel_dump_traceback_later()
                        native_diagnostic.close()
                        native_diagnostic = None
                    for handle in handles:''')
    ast.parse(code, feature_version=(3, 9))
    source['payload/worker.py'] = code.encode()
    out = HERE / 'R8_F2_DIAG'
    out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        raw = (parent / name).read_bytes()
        assert sha(raw) == expected
        (out / name).write_bytes(raw)
    (out / 'MINIMAL.diff').write_text(''.join(unified_diff(original.splitlines(True), code.splitlines(True), 'a/payload/worker.py', 'b/payload/worker.py')), encoding='utf-8')
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()):
            z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    old = binding['remote_root']; remote = old.replace('R8_F1_TAIL_SKIP', out.name)
    binding['native_argv'] = [a.replace(old, remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():
        row['allocator_origin'] = row['allocator_origin'].replace(old, remote)
    binding.update(version=out.name, remote_root=remote,
                   allocator_origin=binding['allocator_origin'].replace(old, remote), submission_ordinal=9,
                   diff_base=parent.name, retry_reason='Baseline first-step stall reproduced on cn22035; add 30-second Python traceback and strict first-step native call entry/exit records, no performance-loop instrumentation.',
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote': remote, 'pin': sha((out / 'RUN_BINDING.json').read_bytes()), 'package': binding['package_sha256']}))


if __name__ == '__main__':
    main()
