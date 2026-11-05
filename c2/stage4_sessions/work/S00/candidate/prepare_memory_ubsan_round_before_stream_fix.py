"""Prepare one immutable-code memory job or one conditional C job; submit neither."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
kind = sys.argv[2]
base = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.parent == base and kind in ('memory', 'ubsan')
assert root.name.startswith('S02_R6_MEMORY_' if kind == 'memory' else 'S03_R2_UBSAN_')
old = base / ('S02_CKPT64_R6_20261105T060434Z' if kind == 'memory' else 'S03_R2_C_20261105T060824Z')
archive_name = 'S02_CKPT64_R6_CODE.zip' if kind == 'memory' else 'S03_ROUND2_C_VALIDATION.zip'
expected = ('26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f' if kind == 'memory'
            else '0fe3eeb3a7ad7fe2fb34eea220f3147edba5b72cdc44f5c7db4fd46d98ea872a')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert root.is_dir() and not (root / 'payload').exists()
assert sha(old / archive_name) == expected
shutil.copyfile(old / archive_name, root / archive_name)
payload = root / 'payload'
payload.mkdir()
with zipfile.ZipFile(root / archive_name) as z:
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(payload)
original = json.loads((old / 'pre_submit_checks.json').read_text())['payload_files']
actual = {str(p.relative_to(payload)): sha(p) for p in payload.rglob('*') if p.is_file()}
assert actual == original
for p in list(payload.rglob('*')) + list(root.glob('*.py')) + list(root.glob('*.sh')):
    if not p.is_file():
        continue
    if p.suffix in ('.sh', '.env', '.py'):
        data = p.read_bytes()
        assert b'\r' not in data, str(p)
        if p.suffix == '.py':
            ast.parse(data.decode('utf-8'), filename=str(p), feature_version=(3, 9))
        else:
            subprocess.run(['bash', '-n', str(p)], check=True)
pre = dict(status='PASS_REMOTE_SHA_LF_LINUX_SYNTAX', kind=kind,
           captured_utc=datetime.now(timezone.utc).isoformat(), package_sha256=expected,
           payload_files=actual, wrapper_files={p.name: sha(p) for p in root.iterdir()
                if p.is_file() and p.suffix in ('.py', '.sh')})
if kind == 'memory':
    case = base / 'S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt'
    manifest = json.loads((payload / 'CASE_MANIFEST.json').read_text())
    assert sha(case) == manifest['sha256'] and case.stat().st_size == manifest['bytes']
    strict = old / 'payload/evidence/c2_2037034_checkpoint_strict/result.json'
    result = json.loads(strict.read_text())
    assert result['status'] == 'PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY'
    pre.update(case_path=str(case), case_sha256=sha(case), case_bytes=case.stat().st_size,
               case_mtime_ns=case.stat().st_mtime_ns, strict_result_path=str(strict),
               strict_result_sha256=sha(strict), strict_job_id='2037034')
(root / 'pre_submit_checks.json').write_text(json.dumps(pre, indent=2) + '\n')
print(json.dumps({k: v for k, v in pre.items() if k not in ('payload_files', 'wrapper_files')}))
