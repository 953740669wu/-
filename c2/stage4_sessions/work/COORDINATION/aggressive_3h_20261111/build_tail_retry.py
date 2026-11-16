"""Retry the unreached tail candidate on cn22035 with a baseline stall bound."""
import ast
import json
from difflib import unified_diff
from zipfile import ZipFile, ZIP_DEFLATED
from build_r1 import HERE, sha, write, change


def main():
    parent = HERE / 'R8_TAIL_SKIP'
    binding = json.loads((parent / 'RUN_BINDING.json').read_bytes())
    assert sha((parent / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(parent / 'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        source = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in source.items())
    old_code = source['launch.py'].decode()
    code = change(old_code, '            if now >= deadline:', '''            if name == "strict" and variant == "baseline" and step == 2:
                released = read(barriers / "1.release")["release_at_ns"] / 1e9
                if now - released > 90 and any(
                    (out / f"node{n}" / "steps.jsonl").stat().st_size == 0 for n in proc
                ):
                    raise TimeoutError("baseline first update exceeded 90 seconds; candidate not reached")
            if now >= deadline:''')
    ast.parse(code, feature_version=(3, 9))
    source['launch.py'] = code.encode()
    out = HERE / 'R8_F1_TAIL_SKIP'
    out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        raw = (parent / name).read_bytes()
        assert sha(raw) == expected
        (out / name).write_bytes(raw)
    diff = ''.join(unified_diff(old_code.splitlines(True), code.splitlines(True), 'a/launch.py', 'b/launch.py'))
    (out / 'MINIMAL.diff').write_bytes(diff.encode())
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()):
            z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    old = binding['remote_root']
    remote = old.replace('R8_TAIL_SKIP', 'R8_F1_TAIL_SKIP')
    binding['native_argv'] = [a.replace(old, remote).replace('cn22036', 'cn22035') for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():
        row['allocator_origin'] = row['allocator_origin'].replace(old, remote)
    binding.update(version=out.name, remote_root=remote, eligible_hosts=['cn22035'],
                   allocator_origin=binding['allocator_origin'].replace(old, remote),
                   submission_ordinal=8, diff_base=parent.name,
                   retry_reason='2088546 baseline first update stalled; candidate never reached',
                   baseline_first_update_timeout_seconds=90,
                   diff_sha256=sha((out / 'MINIMAL.diff').read_bytes()),
                   source_manifest_sha256=sha((out / 'SOURCE_SHA256.json').read_bytes()),
                   package_sha256=sha((out / 'FULL16_PAYLOAD.zip').read_bytes()))
    write(out / 'RUN_BINDING.json', binding)
    print(json.dumps({'remote': remote, 'pin': sha((out / 'RUN_BINDING.json').read_bytes()), 'package': binding['package_sha256']}))


if __name__ == '__main__':
    main()
