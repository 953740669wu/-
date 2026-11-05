"""Build and verify this source-only checkpoint/memory preparation package."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'round5_cpu36_20261105T032617Z'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


payload = ['diagnose_update.py', 'diagnostic_common.py', 'projection_trace.py', 'cpu36_guard.py',
    'cpu36_contract.py', 'run_c2_diagnostic.sh', 'run_s00_job.sh', 'run_c2_memory.sh',
    'train_memory.py', 'memory_metrics.py', 'memory_gate.py', 'interfaces/cluster_runtime.env',
    'baseline/s4_models.py', 'baseline/kml_ops.py', 'candidate/training_step.py',
    'candidate/full_batch_step.py', 'candidate/paired_inputs.py', 'tests/check_equivalence.py',
    'tests/paired_fixture.py', 'tests/test_cpu36_guard.py', 'tests/check_checkpoint_step.py',
    'tests/test_memory_metrics.py', 'tests/test_memory_gate.py', 'VALIDATION_PLAN.md',
    'INPUT_PAIRING_PROTOCOL.md', 'CASE_MANIFEST.json', 'C2_HANDOFF.md']
save(ROOT / 'SOURCE_SHA256.json', {name: sha(ROOT / name) for name in payload})
payload += ['SOURCE_SHA256.json']
entries = {}
patch = []
for name in sorted(payload):
    path, origin = ROOT / name, OLD / name
    same = origin.exists() and path.read_bytes() == origin.read_bytes()
    entries[name] = dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path),
        origin=str(origin.resolve()) if origin.exists() else 'NEW_S02_R6',
        origin_sha256=sha(origin) if origin.exists() else None,
        relation='BYTE_IDENTICAL' if same else 'R5_REVISION' if origin.exists() else 'NEW_S02_R6')
    if path.suffix == '.py':
        ast.parse(path.read_text('utf-8'), feature_version=(3, 9))
    if path.suffix in ('.sh', '.env'):
        assert b'\r' not in path.read_bytes()
    if path.suffix in ('.py', '.sh') and not same:
        patch.extend(difflib.unified_diff(origin.read_text('utf-8').splitlines(True) if origin.exists() else [],
            path.read_text('utf-8').splitlines(True), fromfile='R5/' + name if origin.exists() else '/dev/null',
            tofile='R6/' + name))
(ROOT / 'diff/R5_TO_R6_CODE.patch').write_text(''.join(patch), encoding='utf-8', newline='\n')
archive = ROOT / 'package/S02_CKPT64_R6_CODE.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in sorted(payload):
        info = zipfile.ZipInfo(name, date_time=(2026, 11, 5, 4, 30, 38))
        info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
        z.writestr(info, (ROOT / name).read_bytes())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist())) == len(payload)
    assert all(hashlib.sha256(z.read(name)).hexdigest() == entries[name]['sha256'] for name in payload)
manifest = dict(version='S02_CKPT64_R6_20261105', status='PREPARED_LOCAL_ONLY_NO_C2_NO_MEMORY_RUN',
    archive=archive.name, archive_sha256=sha(archive), archive_bytes=archive.stat().st_size, entries=entries,
    separate_case=dict(json.loads((ROOT / 'CASE_MANIFEST.json').read_text()),
        local_source=str((ROOT.parent / 'round3_20261104T134939Z/case/fixed_16_pre.pt').resolve())),
    numerical_pair=dict(belt='16_adjacent', part='pre', batch=64, microbatch=64,
        reference_checkpoint=False, candidate_checkpoint=True, backend='kml', mode='checkpoint_strict',
        precision='fp32', history='fresh', loss='original_mean', optimizer='unchanged_fresh_AdamW'),
    memory_entry=dict(prepared_only=True, independent_processes=2, steps_each=1, warmup=0,
        retains_comparison_snapshots=False, strict_candidate_pass_required=True, hbm=False,
        initialization_and_training_reported_separately=True, units=['bytes', 'MiB', 'seconds']),
    resources=dict(allocated_preferred=38, selected_physical_cores=36, reserved=2,
        memory_MB=24576, memory_limit_MB=24576, job_seconds=900),
    environment=dict(OMP_NUM_THREADS='36', MKL_NUM_THREADS='36', OPENBLAS_NUM_THREADS='1',
                     OMP_PLACES='cores', OMP_PROC_BIND='close'))
save(ROOT / 'package/PACKAGE_MANIFEST.json', manifest)
(ROOT / 'package/S02_CKPT64_R6_CODE.zip.sha256').write_text(sha(archive) + '  ' + archive.name + '\n', encoding='ascii')
save(ROOT / 'evidence/package_validation.json', dict(status='PASS_CRC_SHA_SIZE_SOURCE_IDENTITY_ONLY',
    archive_sha256=sha(archive), archive_bytes=archive.stat().st_size, entries=len(entries),
    source_entries=len(payload)-1, case_copied=False, full_model_runs=0, c2_runs=0, memory_runs=0))
print(json.dumps(dict(archive=str(archive.resolve()), sha256=sha(archive),
                     bytes=archive.stat().st_size, entries=len(entries)), indent=2))
