"""Build a source-only handoff; never generates case tensors or imports torch."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'round3_20261104T134939Z'
WORK = ROOT.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


payload = ['diagnose_update.py', 'diagnostic_common.py', 'projection_trace.py', 'run_c2_diagnostic.sh',
    'cpu36_guard.py', 'cpu36_contract.py', 'run_s00_job.sh', 'interfaces/cluster_runtime.env',
    'baseline/s4_models.py', 'baseline/kml_ops.py', 'candidate/training_step.py',
    'candidate/paired_inputs.py', 'tests/check_equivalence.py', 'tests/paired_fixture.py',
    'tests/test_cpu36_guard.py', 'VALIDATION_PLAN.md', 'INPUT_PAIRING_PROTOCOL.md',
    'CASE_MANIFEST.json', 'C2_HANDOFF.md']
source = {name: sha(ROOT / name) for name in payload}
write_json(ROOT / 'SOURCE_SHA256.json', source)
payload += ['SOURCE_SHA256.json']
provenance = {}
for name in payload:
    if name == 'cpu36_contract.py':
        origin = WORK / 'S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z/candidate/cpu36_contract.py'
    elif name == 'interfaces/cluster_runtime.env':
        origin = WORK / 'S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z/interfaces/cluster_runtime.env'
    else:
        origin = OLD / name
    same = origin.is_file() and sha(origin) == sha(ROOT / name)
    provenance[name] = dict(path=str((ROOT / name).resolve()), bytes=(ROOT / name).stat().st_size,
        sha256=sha(ROOT / name), origin=str(origin.resolve()) if origin.exists() else 'NEW_S02_R5',
        origin_sha256=sha(origin) if origin.is_file() else None,
        relation='BYTE_IDENTICAL' if same else 'R3_WRAPPER_REVISION' if origin.exists() else 'NEW_S02_R5')
for name in ['cpu36_contract.py', 'interfaces/cluster_runtime.env']:
    assert provenance[name]['relation'] == 'BYTE_IDENTICAL'
for name in payload:
    path = ROOT / name
    if path.suffix in ('.sh', '.env'):
        assert b'\r' not in path.read_bytes()
    if path.suffix == '.py':
        ast.parse(path.read_text('utf-8'), feature_version=(3, 9))
archive = ROOT / 'package/S02_CPU36_R5_CODE.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for name in sorted(payload):
        info = zipfile.ZipInfo(name, date_time=(2026, 11, 5, 3, 26, 18))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        z.writestr(info, (ROOT / name).read_bytes())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist())) == len(payload)
    assert set(z.namelist()) == set(payload)
    assert all(hashlib.sha256(z.read(n)).hexdigest() == sha(ROOT / n) for n in payload)
manifest = dict(version='S02_CPU36_R5_20261105', status='LOCAL_WRAPPER_READY_C2_NOT_RUN',
    code_archive=archive.name, code_archive_sha256=sha(archive), code_archive_bytes=archive.stat().st_size,
    entries=provenance, separate_case=dict(json.loads((ROOT / 'CASE_MANIFEST.json').read_text()),
        local_source=str((OLD / 'case/fixed_16_pre.pt').resolve())),
    constraints=dict(allocated_preferred=38, selected_physical_cores=36, reserved=2,
        memory_MB=24576, memory_limit_MB=24576, job_seconds=900, checker_timeout_seconds=780,
        kill_after_seconds=15, hbm=False, belt='16_adjacent', part='pre', effective_batch=64,
        microbatch=32, checkpoint=False, history='fresh', precision='fp32', backend='kml', mode='strict',
        training_memory_test=False),
    environment=dict(OMP_NUM_THREADS='36', MKL_NUM_THREADS='36', OPENBLAS_NUM_THREADS='1',
                     OMP_PLACES='cores', OMP_PROC_BIND='close'))
write_json(ROOT / 'package/PACKAGE_MANIFEST.json', manifest)
(ROOT / 'package/S02_CPU36_R5_CODE.zip.sha256').write_text(sha(archive) + '  ' + archive.name + '\n', encoding='ascii')
diff = []
for name in ['diagnose_update.py', 'diagnostic_common.py', 'run_c2_diagnostic.sh']:
    diff.extend(difflib.unified_diff((OLD / name).read_text('utf-8').splitlines(True),
        (ROOT / name).read_text('utf-8').splitlines(True), fromfile='R3/' + name, tofile='R5/' + name))
(ROOT / 'diff/R3_WRAPPER_ONLY.patch').write_text(''.join(diff), encoding='utf-8', newline='\n')
write_json(ROOT / 'evidence/package_validation.json', dict(status='PASS_SHA_SIZE_CRC_SOURCE_MATCH',
    code_archive_sha256=sha(archive), bytes=archive.stat().st_size, entries=len(payload),
    case_included=False, source_entries_verified=len(source), no_cr_shell_files=True,
    numerical_validation=False, c2_run=False))
print(json.dumps(dict(archive=str(archive.resolve()), sha256=sha(archive),
                     bytes=archive.stat().st_size, entries=len(payload)), indent=2))
