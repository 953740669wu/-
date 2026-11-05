"""Stage original accepted ZIP bytes and check Linux syntax; never submit/run models."""
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from bounded_round_step import sha, save

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2]
base = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.parent == base and kind in ('memory3', 's07')
assert root.name.startswith('S02_R6_MEMORY3_' if kind == 'memory3' else 'S07_R2_TWODOMAIN_')
archive_name = 'S02_CKPT64_R6_CODE.zip' if kind == 'memory3' else 'S07_R2_VALIDATION.zip'
expected = ('26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f' if kind == 'memory3'
            else '9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367')
archive = root / archive_name
if kind == 'memory3':
    original = base / 'S02_CKPT64_R6_20261105T060434Z' / archive_name
    assert sha(original) == expected
    shutil.copyfile(original, archive)
assert sha(archive) == expected
payloads = [root / ('pair' + str(i)) / 'payload' for i in range(1, 4)] if kind == 'memory3' else [root / 'payload']
files = {}
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    assert len(names) == (28 if kind == 'memory3' else 34)
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
    if kind == 's07':
        assert archive.stat().st_size == 59801
        manifest = json.loads(z.read('SOURCE_MANIFEST.json'))
        assert len(manifest['delivery_files']) == 33
    for payload in payloads:
        payload.mkdir(parents=True, exist_ok=False)
        z.extractall(payload)
        if kind == 's07':
            assert all(sha(payload / row['path']) == row['sha256'] for row in manifest['delivery_files'])
        else:
            sources = json.loads((payload / 'SOURCE_SHA256.json').read_text())
            assert all(sha(payload / n) == h for n, h in sources.items())
        for p in payload.rglob('*'):
            if p.is_file():
                files[str(p.relative_to(root))] = sha(p)
for p in [root / n for n in files] + list(root.glob('*.py')) + list(root.glob('*.sh')):
    if p.suffix in ('.py', '.sh', '.env'):
        assert b'\r' not in p.read_bytes(), str(p)
        if p.suffix == '.py':
            ast.parse(p.read_text(), filename=str(p), feature_version=(3, 9))
        else:
            subprocess.run(['bash', '-n', str(p)], check=True)
pre = dict(status='PASS_REMOTE_ORIGINAL_SHA_LF_LINUX_SYNTAX', captured_utc=datetime.now(timezone.utc).isoformat(),
    kind=kind, package=archive_name, package_sha256=expected, payload_files=files,
    wrapper_files={p.name: sha(p) for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.sh')})
if kind == 'memory3':
    case = base / 'S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt'
    frozen = json.loads((payloads[0] / 'CASE_MANIFEST.json').read_text())
    assert sha(case) == frozen['sha256'] and case.stat().st_size == frozen['bytes']
    strict = base / 'S02_CKPT64_R6_20261105T060434Z/payload/evidence/c2_2037034_checkpoint_strict/result.json'
    assert sha(strict) == '1f2aac7dee498cd839b696d1305e80236227c445da69e26ffd38f5c80c9aba17'
    pre.update(case_path=str(case), case_sha256=sha(case), case_bytes=case.stat().st_size,
        case_mtime_ns=case.stat().st_mtime_ns, strict_result_path=str(strict), strict_result_sha256=sha(strict))
save(root / 'pre_submit_checks.json', pre)
print(json.dumps(dict(status=pre['status'], kind=kind, original_files=len(files), package_sha256=expected)))
