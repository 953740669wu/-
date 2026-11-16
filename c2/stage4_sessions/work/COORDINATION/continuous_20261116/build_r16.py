"""Bind the validated replay omission to an independent strict check on 16 domains."""
import ast
from difflib import unified_diff
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'aggressive_3h_20261111/R15_INDEPENDENT_DOMAINS'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def change(code, old, new):
    assert code.count(old) == 1, old
    return code.replace(old, new)


def main():
    binding = json.loads((PARENT / 'RUN_BINDING.json').read_bytes())
    assert sha((PARENT / 'FULL16_PAYLOAD.zip').read_bytes()) == binding['package_sha256']
    with ZipFile(PARENT / 'FULL16_PAYLOAD.zip') as z:
        manifest = json.loads(z.read('SOURCE_SHA256.json'))
        original = {n: z.read(n) for n in manifest}
    assert all(sha(raw) == manifest[n] for n, raw in original.items())
    source = dict(original)
    code = source['launch.py'].decode()
    code = change(code, 'and count == 4', 'and count == 16')
    code = change(code, '10*count + 30*count*binding["pairs"]', '10*count')
    code = change(code, 'need(rounds == 1, "one paired measurement only")',
                  'need(rounds == 0, "strict-only scope")')
    start = code.index('                for variant in ("candidate","baseline"):')
    end = code.index('                report.update(status="PASS_STRICT5_AND_PERF15"', start)
    code = code[:start] + code[end:]
    code = code.replace('PASS_STRICT5_AND_PERF15', 'PASS_STRICT5_ALL_METRICS')
    source['launch.py'] = code.encode()
    source['prepare.py'] = change(source['prepare.py'].decode(),
        'AGGRESSIVE3H_20261111_', 'CONTINUOUS_20261116_').encode()
    code = source['submit_once.py'].decode()
    old = '''    until = datetime.fromisoformat(binding["batch_deadline_utc"])
    room = (until - datetime.now(timezone.utc)).total_seconds()
    need(room > binding["wall_seconds"] + 120, "insufficient batch time to execute full job")
    stop_queue = time.monotonic() + min(binding["remaining_queue_seconds"],room-binding["wall_seconds"]-120)'''
    code = change(code, old, '''    need(binding["batch_deadline_utc"] is None and binding["wall_seconds"] == 1800,
         "unlimited campaign requires bounded individual job")
    stop_queue = time.monotonic() + binding["remaining_queue_seconds"]''')
    source['submit_once.py'] = code.encode()
    out = HERE / 'R16_FULL16_STRICT'
    out.mkdir()
    for name, expected in binding['frozen_sidecars'].items():
        raw = (PARENT / name).read_bytes()
        assert sha(raw) == expected
        (out / name).write_bytes(raw)
    diffs = []
    for n, raw in source.items():
        if n.endswith('.py'):
            ast.parse(raw, filename=n, feature_version=(3, 9))
        if raw != original[n]:
            diffs.extend(unified_diff(original[n].decode().splitlines(True),
                                     raw.decode().splitlines(True), 'a/'+n, 'b/'+n))
    (out / 'MINIMAL.diff').write_text(''.join(diffs), encoding='utf-8')
    write(out / 'SOURCE_SHA256.json', {n: sha(raw) for n, raw in source.items()})
    with ZipFile(out / 'FULL16_PAYLOAD.zip', 'x', ZIP_DEFLATED) as z:
        for n, raw in sorted(source.items()):
            z.writestr(n, raw)
        z.write(out / 'SOURCE_SHA256.json', 'SOURCE_SHA256.json')
    old = binding['remote_root']
    remote = '/home/share/wujunyi/opt/stage4_sessions/S00/CONTINUOUS_20261116_R16_FULL16_STRICT'
    replacements = {'cpu=152,mem=98304MB':'cpu=608,mem=393216MB', 'mem=98304MB':'mem=393216MB',
                    'numa[count=4,distribution=pack]':'numa[count=16,distribution=pack]', '720':'1800'}
    binding['native_argv'] = [replacements.get(a, a).replace(old, remote) for a in binding['native_argv']]
    for row in binding['hbm_selections'].values():
        row['allocator_origin'] = row['allocator_origin'].replace(old, remote)
    binding['allocation_contract'].update(DDR_limit_MB=393216, DDR_request_MB=393216,
        HBM_max_MiB_total=60800, allocated_cpus=608, compute_cpus=576, domains=16, reserved_cpus=32)
    binding.update(version=out.name, remote_root=remote, domain_count=16,
        allocator_origin=binding['allocator_origin'].replace(old, remote), submission_ordinal=1,
        wall_seconds=1800, max_model_updates=160, pairs=0, performance_steps=0,
        performance_warmup=0, performance_samples=0, performance_order=[],
        batch_deadline_utc=None, strict_storage_min_bytes=96*1024**3,
        domain_schedule='independent_strict5_only', diff_base=PARENT.name,
        retry_reason='New full16 numerical coverage before fixed-window tail replay comparison; no accuracy relaxation.',
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),
        package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()))
    write(out/'RUN_BINDING.json', binding)
    print(json.dumps(dict(remote=remote, pin=sha((out/'RUN_BINDING.json').read_bytes()),
                          package=binding['package_sha256'])))


if __name__ == '__main__':
    main()
