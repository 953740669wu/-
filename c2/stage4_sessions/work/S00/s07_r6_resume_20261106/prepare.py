"""Pin the new readiness inner package; never import frameworks or submit jobs."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ARCHIVE = 'S07_ALIGNED_STACK_R6.zip'
OBSERVER_SHA = '5b3ad54e675a293e3eb51d292b149c6939bbdc52b68322f340eb76be3b02b875'
INNER_SHA = '32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1'
BASE = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
PREFIX = 'S07_STACK_R6_'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_members(archive, manifest):
    entries = archive.infolist()
    delivery = manifest['delivery_files']
    expected = {x['path'] for x in delivery} | {'SOURCE_MANIFEST.json', 'evidence/'}
    if (len(delivery) != 14 or len(entries) != 16 or len(expected) != 16
            or set(archive.namelist()) != expected
            or sum(not x.is_dir() for x in entries) != 15
            or sum(x.is_dir() for x in entries) != 1):
        raise ValueError('require exactly 15 R6 files, 14 manifest entries and evidence/')
    if any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n or ':' in n for n in archive.namelist()):
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
    if archive.stat().st_size != 43727 or sha(archive) != INNER_SHA:
        raise ValueError('wrong diagnostic package bytes/SHA; older inner packages are not accepted')
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('SOURCE_MANIFEST.json'))
        check_members(z, manifest)
        payload = root / 'payload'; payload.mkdir(exist_ok=False)
        z.extractall(payload)


def main(root):
    if root.parent != BASE or not root.name.startswith(PREFIX):
        raise ValueError('new S00 stack R6 staging directory required')
    for name,digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():
        if sha(root/name)!=digest:raise ValueError('deployment source drift: '+name)
    unpack(root)
    payload = root / 'payload'
    for p in list(payload.rglob('*.py')) + list(root.glob('*.py')) + list(root.glob('*.sh')):
        if b'\r' in p.read_bytes(): raise ValueError('non-LF execution source: ' + str(p))
        if p.suffix == '.py': ast.parse(p.read_text(), filename=str(p), feature_version=(3, 9))
        else: subprocess.run(['bash', '-n', str(p)], check=True)
    pre = dict(status='PASS_NEW_INNER_SHA_MANIFEST_AND_SYNTAX_ONLY', package_name=ARCHIVE,
        package_sha256=INNER_SHA, package_bytes=43727, package_files=15, manifest_entries=14,
        payload_files={p.relative_to(root).as_posix(): sha(p) for p in payload.rglob('*') if p.is_file()},
        wrapper_files={p.name: sha(p) for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.sh')})
    (root / 'pre_submit_checks.json').write_text(json.dumps(pre, indent=2) + '\n')
    verify_prepared(root)


def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def verify_prepared(root):
    for name,digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():
        if sha(root/name)!=digest:raise ValueError('deployment source drift: '+name)
    pre=json.loads((root/'pre_submit_checks.json').read_text(encoding='utf-8'))
    if pre['package_files']!=15 or pre['manifest_entries']!=14 or len(pre['payload_files'])!=15:raise ValueError('R6 delivery count changed')
    for name,digest in pre['payload_files'].items():
        if sha(root/name)!=digest:raise ValueError('payload source drift: '+name)
    if sha(root/'payload/candidate/stack_observer.py')!=OBSERVER_SHA:raise ValueError('observer source changed')

def check_root(root):
    if root.parent!=BASE or not root.name.startswith(PREFIX):raise ValueError('new S00 R6 root required')

if __name__ == '__main__': main(Path(__file__).resolve().parent)
