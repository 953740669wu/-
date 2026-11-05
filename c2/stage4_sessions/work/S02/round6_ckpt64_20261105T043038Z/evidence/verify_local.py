"""Syntax, provenance and saved-evidence checks only; no framework/model/job."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'round5_cpu36_20261105T032617Z'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


unchanged = ['baseline/s4_models.py', 'baseline/kml_ops.py', 'candidate/training_step.py',
    'candidate/paired_inputs.py', 'tests/check_equivalence.py', 'tests/paired_fixture.py',
    'projection_trace.py', 'VALIDATION_PLAN.md', 'INPUT_PAIRING_PROTOCOL.md',
    'CASE_MANIFEST.json', 'diagnostic_common.py', 'cpu36_contract.py', 'interfaces/cluster_runtime.env']
assert all((ROOT / name).read_bytes() == (OLD / name).read_bytes() for name in unchanged)
record = dict(unchanged_from_r5={name: sha(ROOT / name) for name in unchanged}, python39_syntax=[])
for path in ROOT.rglob('*.py'):
    ast.parse(path.read_text('utf-8'), feature_version=(3, 9))
    record['python39_syntax'].append(path.relative_to(ROOT).as_posix())
blocks = re.findall(r'```bash\n(.*?)\n```', (ROOT / 'C2_HANDOFF.md').read_text('utf-8'), re.S)
assert len(blocks) == 2
scripts = [ROOT / name for name in ['run_c2_diagnostic.sh', 'run_s00_job.sh', 'run_c2_memory.sh',
                                   'interfaces/cluster_runtime.env']]
for index, block in enumerate(blocks, 1):
    path = ROOT / f'evidence/S00_COMMANDS_{index}.sh'
    path.write_text(block + '\n', encoding='utf-8', newline='\n'); scripts.append(path)
for block in blocks:
    if "<<'PY'\n" in block:
        code = block.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        ast.parse(code, feature_version=(3, 9))
record['shell_syntax'] = []
for path in scripts:
    assert b'\r' not in path.read_bytes()
    run = subprocess.run(['C:/Program Files/Git/bin/bash.exe', '-n', str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    record['shell_syntax'].append(dict(path=path.relative_to(ROOT).as_posix(), cr_bytes=0,
                                       git_bash_n_exit=run.returncode, stderr=run.stderr))
before = json.loads((ROOT / 'evidence/inputs_before.json').read_text())
protected = {n: value for n, value in before.items() if Path(n).name not in ('SESSION_STATUS.md', 'ROUND_DELTA.md')}
for name, value in protected.items():
    path = Path(name)
    assert dict(bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns, sha256=sha(path)) == value, name
record['protected_inputs_unchanged'] = len(protected)
analysis = json.loads((ROOT / 'evidence/R5_saved_failure_analysis.json').read_text())
record['r5_saved_metrics'] = dict(total=analysis['metrics'], failed=analysis['failures'], families=analysis['families'])
gradients = analysis['failed_gradient_metrics']
record['r5_gradient_failure_modes'] = dict(
    absolute_only=sum(m['max_abs'] > 2e-5 and m['l2_relative'] <= 2e-6 for m in gradients),
    relative_only=sum(m['max_abs'] <= 2e-5 and m['l2_relative'] > 2e-6 for m in gradients),
    both=sum(m['max_abs'] > 2e-5 and m['l2_relative'] > 2e-6 for m in gradients))
record['r5_packed_bias_max_delta_error'] = {block: max(item['blocks'][block]['delta_error_max_abs']
    for item in analysis['optimizer_details']['packed_bias_blocks']) for block in ('Q', 'K', 'V')}
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
record.update(status='PASS_LOCAL_ONLY', full_model_runs=0, c2_runs=0, training_memory_runs=0,
              shell_commands_executed=False)
(ROOT / 'evidence/local_validation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in record.items() if key not in ('unchanged_from_r5', 'python39_syntax')}, indent=2))
