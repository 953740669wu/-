"""Local wrapper validation only. Does not import a framework or run a model."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'round3_20261104T134939Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


record = dict(python=sys.executable, framework_imported=False, model_runs=0, c2_runs=0)
unchanged = ['baseline/s4_models.py', 'baseline/kml_ops.py', 'candidate/training_step.py',
             'candidate/paired_inputs.py', 'tests/check_equivalence.py', 'tests/paired_fixture.py',
             'projection_trace.py', 'VALIDATION_PLAN.md', 'INPUT_PAIRING_PROTOCOL.md', 'CASE_MANIFEST.json']
record['unchanged_r3'] = {name: sha(ROOT / name) for name in unchanged}
assert all(sha(ROOT / name) == sha(OLD / name) for name in unchanged)
record['unchanged_numerical_functions'] = []
for filename, names in {'diagnose_update.py': ['run', 'compare_snapshots', 'optimizer_details', 'case_identity'],
                        'diagnostic_common.py': ['errors', 'first_update', 'tensor_sha']}.items():
    def functions(path):
        return {node.name: ast.dump(node) for node in ast.parse(path.read_text('utf-8')).body
                if isinstance(node, ast.FunctionDef)}
    old, new = functions(OLD / filename), functions(ROOT / filename)
    for name in names:
        assert old[name] == new[name], name
        record['unchanged_numerical_functions'].append(filename + ':' + name)
record['python39_syntax'] = []
for path in sorted(ROOT.rglob('*.py')):
    ast.parse(path.read_text('utf-8'), filename=str(path), feature_version=(3, 9))
    record['python39_syntax'].append(str(path.relative_to(ROOT)))
bash = Path('C:/Program Files/Git/bin/bash.exe')
record['shell_checks'] = []
for name in ['run_c2_diagnostic.sh', 'run_s00_job.sh', 'interfaces/cluster_runtime.env']:
    path = ROOT / name
    assert b'\r' not in path.read_bytes(), name
    run = subprocess.run([str(bash), '-n', str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    record['shell_checks'].append(dict(file=name, cr_bytes=0, git_bash_n_exit=run.returncode,
                                       stdout=run.stdout, stderr=run.stderr))
wrong = ROOT / 'evidence/wrong_platform.json'
run = subprocess.run([sys.executable, '-B', str(ROOT / 'diagnose_update.py'), '--backend', 'kml',
                      '--mode', 'strict', '--output', str(wrong)], capture_output=True, text=True)
(ROOT / 'evidence/wrong_platform_stdout.txt').write_text(run.stdout + run.stderr, encoding='utf-8')
result = json.loads(wrong.read_text())
assert run.returncode == 2 and result['status'] == 'ERROR_RUNTIME_OR_INPUT' and 'Linux' in result['error']
record['wrong_platform'] = dict(exit=run.returncode, status=result['status'], error=result['error'])
# The KML branch rejects Windows before importing torch or doing a model calculation.
assert 'torch' not in sys.modules and 'numpy' not in sys.modules
record['status'] = 'PASS_LOCAL_WRAPPER_ONLY'
(ROOT / 'evidence/local_validation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
