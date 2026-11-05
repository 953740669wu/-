"""Linux-only affinity guard tests using a tiny checker fixture, never a model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
allowed = sorted(os.sched_getaffinity(0))
assert len(allowed) >= 5
cpus = allowed[:4]
helper = root / 'S02/run_s02_checker_bound.py'
results = []
with tempfile.TemporaryDirectory(prefix='affinity_fixture_', dir=root) as temp:
    temp = Path(temp)
    (temp / 'tests').mkdir()
    (temp / 'torch.py').write_text('def set_num_threads(n):\n    assert n == 4\n')
    (temp / 'numpy.py').write_text('# no numerical work\n')
    for scenario in ['same_process_pass', 'wrong_expected_set', 'checker_changes_affinity']:
        checker = temp / 'tests/check_equivalence.py'
        checker.write_text('import os,json\nfrom pathlib import Path\n'
                          'Path(os.environ["FIXTURE_PID"]).write_text(str(os.getpid()))\n'
                          + ('os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})\n'
                             if scenario == 'checker_changes_affinity' else ''))
        expected = cpus if scenario != 'wrong_expected_set' else cpus[:3] + [allowed[4]]
        report = root / (scenario + '.json')
        pid_path = temp / (scenario + '_pid')
        env = dict(os.environ, PYTHONPATH=str(temp), PYTHONDONTWRITEBYTECODE='1',
                   S02_RUN=str(temp), S02_CPUSET=','.join(map(str, expected)),
                   S02_AFFINITY_REPORT=str(report), FIXTURE_PID=str(pid_path))
        env.pop('LD_PRELOAD', None)
        proc = subprocess.run(['taskset', '-c', ','.join(map(str, cpus)), sys.executable,
                               '-B', str(helper)], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
        actual = json.loads(report.read_text())
        if scenario == 'same_process_pass':
            assert proc.returncode == 0, proc.stderr
            assert actual['pid'] == int(pid_path.read_text())
            assert len(actual['stages']) == 3
            assert all(s['actual_cpus'] == cpus for s in actual['stages'])
        else:
            assert proc.returncode != 0
            assert 'checker CPU set' in proc.stderr
        results.append(dict(scenario=scenario, exit_code=proc.returncode,
                            guard_result='PASS' if proc.returncode == 0 else 'EXPECTED_REJECTION',
                            affinity_report=actual, stderr=proc.stderr))
(root / 'affinity_guard_tests.json').write_text(json.dumps(dict(
    status='PASS', scope='Linux standard-library fixture and fake torch/numpy; NOT full real checker/model execution',
    allowed_test_cpus=cpus, cases=results), indent=2) + '\n')
print('S02_AFFINITY_GUARD_TESTS_PASS')
