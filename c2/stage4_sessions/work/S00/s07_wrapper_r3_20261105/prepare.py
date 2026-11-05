"""Stage the exact accepted S07 R2 payload; no submission, import or workers."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parent
assert root.parent == Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
assert root.name.startswith('S07_R2_TWODOMAIN_R3_')
archive = root / 'S07_R2_VALIDATION.zip'
assert archive.stat().st_size == 59801
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367'
payload = root / 'payload'
payload.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == 34
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(payload)
manifest = json.loads((payload / 'SOURCE_MANIFEST.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(payload / x['path']) == x['sha256'] for x in manifest['delivery_files'])
for p in list(payload.rglob('*.py')) + list(root.glob('*.py')) + list(root.glob('*.sh')):
    assert b'\r' not in p.read_bytes(), str(p)
    if p.suffix == '.py':
        ast.parse(p.read_text(), filename=str(p), feature_version=(3, 9))
    else:
        subprocess.run(['bash', '-n', str(p)], check=True)
pre = dict(status='PASS_ORIGINAL_R2_AND_NEW_WRAPPER_SYNTAX_ONLY',
    package_sha256=sha(archive), payload_files={str(p.relative_to(root)): sha(p) for p in payload.rglob('*') if p.is_file()},
    wrapper_files={p.name: sha(p) for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.sh')})
(root / 'pre_submit_checks.json').write_text(json.dumps(pre, indent=2) + '\n')
