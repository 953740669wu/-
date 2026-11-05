"""Preparation checks; these require no torch and do not establish numerical parity."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import probe
import run_probe


@contextmanager
def fixture_dir():
    # Keep all fixtures and bounded cleanup inside this task's evidence directory.
    path = ROOT / 'evidence' / ('test_' + uuid.uuid4().hex)
    path.parent.mkdir(exist_ok=True)
    path.mkdir()
    try:
        yield str(path)
    finally:
        if path.resolve().parent != (ROOT / 'evidence').resolve():
            raise RuntimeError('fixture cleanup outside evidence directory')
        shutil.rmtree(path)


class ProbeChecks(unittest.TestCase):
    def test_isolation_requires_I_and_S(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import probe; '
                'probe.isolate([])')
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'candidate')],
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RuntimeError: Use Python -I -S -B; -s or -I alone does not '
                      'exclude system site-packages', result.stderr)

    def test_isolated_bootstrap_ignores_pythonpath_and_pth(self):
        with fixture_dir() as td:
            root = Path(td)
            (root / 'sitecustomize.py').write_text('raise RuntimeError("ambient import")')
            (root / 'evil.pth').write_text('import sys; raise RuntimeError("pth executed")')
            env = dict(os.environ, PYTHONPATH=td)
            code = ('import sys; sys.path.insert(0, sys.argv[1]); import probe; '
                    'probe.isolate([sys.argv[2]]); import json; print(json.dumps(sys.path))')
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code,
                                     str(ROOT / 'candidate'), td], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            paths = json.loads(result.stdout)
            self.assertEqual(paths[0], str(root.resolve()))
            self.assertFalse(any('site-packages' in p for p in paths[1:]))

    def test_nonexistent_package_root_fails(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import probe; '
                'probe.isolate([sys.argv[2]])')
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code,
                                 str(ROOT / 'candidate'), str(ROOT / 'missing_dependency')],
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FileNotFoundError', result.stderr)

    def test_source_identity_detects_change(self):
        with fixture_dir() as td:
            path = Path(td) / 'source.py'
            path.write_text('original')
            expected = probe.sha256(path)
            path.write_text('changed')
            with self.assertRaisesRegex(RuntimeError, 'SHA256'):
                probe.verify_source(path, expected)

    def test_child_failure_is_not_pass(self):
        with fixture_dir() as td:
            result = run_probe.run_child([sys.executable, '-I', '-S', '-c',
                                          'raise RuntimeError("compile blocked")'], Path(td), 10)
            self.assertEqual(result['status'], 'FAILED')
            self.assertNotEqual(result['exit_code'], 0)
            self.assertIn('compile blocked', (Path(td) / 'stderr.txt').read_text())

    def test_timeout_is_not_pass(self):
        with fixture_dir() as td:
            result = run_probe.run_child([sys.executable, '-I', '-S', '-c',
                                          'import time; time.sleep(10)'], Path(td), 0.1)
            self.assertEqual(result['status'], 'TIMEOUT')
            self.assertNotEqual(result['exit_code'], 0)

    def test_frozen_sources_match_identity_and_optional_project(self):
        expected = json.loads((ROOT / 'source_identity.json').read_text())
        project = Path(os.environ['S06_PROJECT_ROOT']) if os.environ.get('S06_PROJECT_ROOT') else None
        for name, digest in expected['baseline_sha256'].items():
            probe.verify_source(ROOT / 'baseline' / name, digest)
            if project is not None:
                probe.verify_source(project / name, digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
