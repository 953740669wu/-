"""Pin the new diagnostic inner package; never import frameworks or submit jobs."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ARCHIVE = 'S07_INIT_DIAGNOSTIC_R3.zip'
INNER_SHA = 'af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45'
BASE = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
PREFIX = 'S07_INIT_DIAG_R4_'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_members(archive, manifest):
    entries = archive.infolist()
    delivery = manifest['delivery_files']
    expected = {x['path'] for x in delivery} | {'SOURCE_MANIFEST.json', 'evidence/'}
    if (len(delivery) != 11 or len(entries) != 13 or len(expected) != 13
            or set(archive.namelist()) != expected
            or sum(not x.is_dir() for x in entries) != 12
            or sum(x.is_dir() for x in entries) != 1):
        raise ValueError('require exactly 12 diagnostic files, 11 manifest entries and evidence/')
    if any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n for n in archive.namelist()):
        raise ValueError('unsafe inner package path')
    for item in delivery:
        data = archive.read(item['path'])
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('inner manifest mismatch: ' + item['path'])
    if (manifest['pg_timeout_seconds'], manifest['deadline_seconds'], manifest['consumer_budget_seconds'],
            manifest['job_proposal_seconds']) != (5, 30, 270, 300):
        raise ValueError('changed original timeout/budget contract')
    if manifest['case_order'] != ['normal', 'crash', 'collective-timeout', 'watchdog']:
        raise ValueError('changed original four-case contract')


def unpack(root):
    archive = root / ARCHIVE
    if archive.stat().st_size != 31262 or sha(archive) != INNER_SHA:
        raise ValueError('wrong diagnostic package bytes/SHA; old R2 is not accepted')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('SOURCE_MANIFEST.json'))
        check_members(z, manifest)
        payload = root / 'payload'; payload.mkdir(exist_ok=False)
        z.extractall(payload)


def main(root):
    if root.parent != BASE or not root.name.startswith(PREFIX):
        raise ValueError('new S00 diagnostic R4 staging directory required')
    unpack(root)
    payload = root / 'payload'
    for p in list(payload.rglob('*.py')) + list(root.glob('*.py')) + list(root.glob('*.sh')):
        if b'\r' in p.read_bytes(): raise ValueError('non-LF execution source: ' + str(p))
        if p.suffix == '.py': ast.parse(p.read_text(), filename=str(p), feature_version=(3, 9))
        else: subprocess.run(['bash', '-n', str(p)], check=True)
    pre = dict(status='PASS_NEW_INNER_SHA_MANIFEST_AND_SYNTAX_ONLY', package_name=ARCHIVE,
        package_sha256=INNER_SHA, package_bytes=31262, package_files=12, manifest_entries=11,
        payload_files={p.relative_to(root).as_posix(): sha(p) for p in payload.rglob('*') if p.is_file()},
        wrapper_files={p.name: sha(p) for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.sh')})
    (root / 'pre_submit_checks.json').write_text(json.dumps(pre, indent=2) + '\n')


if __name__ == '__main__': main(Path(__file__).resolve().parent)
