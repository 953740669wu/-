"""Pinned engineering deployment; no models or scheduler submission."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

BASE=Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
PREFIX='S02_GEMM5_'
DEPLOYMENT='S00_R11_GEMM5_DEPLOYMENT.zip'
RESOURCES=dict(allocated_cores=38,actual_physical_cores=36,reserved_cores=2,memory_MB=24576,
 memory_limit_MB=24576,exclusive=True,job_seconds=900,whole_entry_timeout=840,cleanup_seconds=30,closing_seconds=30,stop_new_update_after_seconds=720,HBM=0)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def check_root(root):
    if root.parent!=BASE or not root.name.startswith(PREFIX):raise ValueError('new unique S00 engineering directory required')


def pinned(root):return json.loads((root/'PINNED_INPUTS.json').read_text(encoding='utf-8'))


def verify_prepared(root):
    pins=pinned(root)
    index=json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8'))
    for name,digest in index.items():
        if sha(root/name)!=digest:raise ValueError('deployment source drift: '+name)
    for name,digest in json.loads((root/'pre_submit_checks.json').read_text())['payload_files'].items():
        if sha(root/name)!=digest:raise ValueError('code source drift: '+name)
    for name,digest in [('ENGINEERING_DESCRIPTOR.json',pins['descriptor_sha256']),('INTERFACE.json',pins['interface_sha256']),
                        (pins['code_archive'],pins['code_package_sha256'])]:
        if sha(root/name)!=digest:raise ValueError('pinned input drift: '+name)
    return pins


def prepare(root):
    check_root(root)
    if (root/'pre_submit_checks.json').exists():raise FileExistsError('prepared directory is not reusable')
    pins=pinned(root)
    index=json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8'))
    for name,digest in index.items():
        if sha(root/name)!=digest:raise ValueError('deployment SHA mismatch: '+name)
    if sha(root/pins['code_archive'])!=pins['code_package_sha256']:raise ValueError('S02 code ZIP drift')
    with zipfile.ZipFile(root/pins['code_archive']) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or any(Path(n).is_absolute() or '..' in Path(n).parts or '\\' in n or ':' in n for n in names):raise ValueError('unsafe/duplicate code ZIP entry')
        payload=root/'payload';payload.mkdir(exist_ok=False);z.extractall(payload)
    manifest=payload/pins['code_source_manifest_name']
    if sha(manifest)!=pins['code_source_manifest_sha256']:raise ValueError('S02 source manifest drift')
    source=json.loads(manifest.read_text(encoding='utf-8'))
    for name,digest in source.items():
        if sha(payload/name)!=digest:raise ValueError('S02 source differs: '+name)
    for path in [*root.glob('*.py'),*root.glob('*.sh'),*root.glob('payload/**/*.py'),*root.glob('payload/**/*.sh')]:
        raw=path.read_bytes()
        if b'\r' in raw:raise ValueError('non-LF execution source: '+str(path))
        if path.suffix=='.py':ast.parse(raw.decode('utf-8'),feature_version=(3,9))
        if path.suffix=='.sh':subprocess.run(['bash','-n',str(path)],check=True,timeout=5)
    (payload/'outputs').mkdir(exist_ok=True)
    save(root/'pre_submit_checks.json',dict(status='SHA_SYNTAX_ONLY_NO_MODEL',
      payload_files={p.relative_to(root).as_posix():sha(p) for p in payload.rglob('*') if p.is_file()}))
    verify_prepared(root)


if __name__=='__main__':prepare(Path(__file__).resolve().parent)
