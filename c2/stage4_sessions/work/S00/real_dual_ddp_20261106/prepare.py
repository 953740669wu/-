"""Frozen two-package deployment verification; never import a framework."""
import ast
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import zipfile

BASE = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
PREFIX = 'REAL_DUAL_DDP_'
DEPLOYMENT = 'S00_REAL_DUAL_DDP_DEPLOYMENT.zip'
RESOURCES = dict(domains=2, allocated_per_domain=38, actual_per_domain=36, reserved_per_domain=2,
                 allocated_cores=76, actual_physical_cores=72, reserved_cores=4, memory_MB=24576,
                 memory_limit_MB=24576, exclusive=True, HBM=0, job_seconds=900,
                 whole_entry_timeout=840, cleanup_seconds=30, closing_seconds=30, pg_timeout_seconds=120)
WORKLOAD = dict(local_batch=32, global_batch=64, strict_reference_updates=5, max_global_updates=25,
                max_rank_updates=50, max_reference_updates=5, max_full_encoder_updates=55,
                unique_training_frames=1600, extra_reference_frames=320, optimizer_restore_updates=0,
                stage_order=['strict5', 'continue_same_state_to25', 'checkpoint', 'zero_update_restore'],
                comparator='ORIGINAL_UNCHANGED', formal_split_status='UNKNOWN',
                linux_preflight_methods=26, linux_preflight_skipped=0,
                upstream_local_numerical_gate='FAIL_ORIGINAL_THRESHOLDS_PRESERVED')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def check_root(root):
    if root.parent != BASE or not root.name.startswith(PREFIX):
        raise ValueError('fresh owned REAL_DUAL_DDP directory required')


def pinned(root):
    return json.loads((root/'PINNED_INPUTS.json').read_text(encoding='utf-8'))


def check_archive(path, files):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or any(
                name.startswith('/') or '..' in Path(name).parts or '\\' in name or ':' in name
                for name in names):
            raise ValueError('unsafe/duplicate package entry')
        if any(stat.S_ISLNK(info.external_attr >> 16) for info in z.infolist()):
            raise ValueError('package symlinks forbidden')
        actual = {name: hashlib.sha256(z.read(name)).hexdigest()
                  for name in names if not name.endswith('/')}
        if actual != files: raise ValueError('package file set or bytes differ from pinned source index')
        return actual


def verify_prepared(root):
    for name, digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():
        if sha(root/name) != digest: raise ValueError('deployment source drift: '+name)
    pins = pinned(root)
    for package in pins['packages']:
        if sha(root/package['archive']) != package['sha256']: raise ValueError('inner ZIP drift')
        for name, digest in package['files'].items():
            if sha(root/'payload'/package['destination']/name) != digest:
                raise ValueError('unpacked source drift: '+name)
    return pins


def prepare(root):
    check_root(root)
    if (root/'payload').exists(): raise FileExistsError('deployment is not reusable')
    pins = pinned(root)
    for name, digest in json.loads((root/'ARTIFACT_SHA256.json').read_text(encoding='utf-8')).items():
        if sha(root/name) != digest: raise ValueError('outer source drift: '+name)
    for package in pins['packages']:
        path = root/package['archive']
        if sha(path) != package['sha256']: raise ValueError('inner package SHA mismatch')
        check_archive(path, package['files'])
        destination = root/'payload'/package['destination']
        destination.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(path) as z: z.extractall(destination)
        (destination/'evidence').mkdir(exist_ok=True)
    checked = []
    for path in [*root.glob('*.py'), *root.glob('*.sh'), *root.glob('*.env'), *root.glob('tests/*.py'),
                 *root.glob('payload/**/*.py'), *root.glob('payload/**/*.sh')]:
        raw = path.read_bytes()
        if b'\r' in raw: raise ValueError('non-LF executable source: '+str(path))
        if path.suffix == '.py': ast.parse(raw.decode('utf-8'), feature_version=(3,9))
        else: subprocess.run(['bash', '-n', str(path)], check=True, timeout=5)
        checked.append(path.relative_to(root).as_posix())
    verify_prepared(root)
    save(root/'pre_submit_checks.json', dict(status='SHA_AST39_LF_BASH_N_ONLY_NO_MODEL',
         checked=checked, package_file_counts={p['destination']: len(p['files']) for p in pins['packages']}))


if __name__ == '__main__': prepare(Path(__file__).resolve().parent)
