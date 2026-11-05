"""Real stdlib subprocess/file checks. Synthetic timings never validate C2 performance."""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'candidate'))
import runner
from cpu_fixtures import augment
BASELINE = WORK.parents[2] / 'S00/baseline'


class RunnerChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK / 'tests')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec = dict(run_id='synthetic-only', host='local-test', domains=[0, 1], rounds=3,
                         input_protocol='SYNTHETIC_RUNNER_PROTOCOL_ONLY',
                         belts=['16_adjacent', '32_skip4'], parts=['pre', 'dec'],
                         config=dict(amp='fp32', batch=32, channels_last=False, compile=False,
                                     reps=5, kml_conv=False, kml_blas='test-library', ckpt=False,
                                     kml_linear=True, linear_dtype='fp32'), device='cpu',
                         cases=['s0322p0', 's0322p1'])
        self.results = {}
        self.statuses = {}
        for r in range(1, 4):
            for d in (0, 1):
                result = dict(config=copy.deepcopy(self.spec['config']), device='cpu',
                              cases=self.spec['cases'], torch='synthetic-test',
                              run=dict(run_id=self.spec['run_id'], host=self.spec['host'], round=r,
                                       input_protocol=self.spec['input_protocol'],
                                       rank=d, pid=100 + d, started=1000, finished=1001),
                              **{b: dict(pretrain_frames_per_s=16, decoder_frames_per_s=8,
                                         pretrain_step_s_B32=2, decoder_step_s_B32=4, peak_mem_GB=1)
                                 for b in self.spec['belts']})
                self.results[r, d] = result
                self.statuses[r, d] = dict(pid=100 + d, exit_code=0, started=999, finished=1002,
                                           timed_out=False)
        augment(self.spec, self.results, self.statuses, runner)

    def write_fixture(self):
        runner.atomic_json(self.root / 'manifest.json', self.spec)
        for (r, d), data in self.results.items():
            # Deliberately bypass the candidate writer: malformed external files must be rejected too.
            (self.root / f'r{r}_d{d}.json').write_text(json.dumps(data), encoding='utf-8')
            os.utime(self.root / f'r{r}_d{d}.json', (1001, 1001))
        for (r, d), data in self.statuses.items():
            runner.atomic_json(self.root / f'r{r}_d{d}.status.json', data)

    def rejected(self):
        self.write_fixture()
        result = runner.summarize(self.root)
        self.assertEqual(result['status'], 'FAIL', result)
        self.assertNotIn('metrics', result)
        self.assertTrue(result['errors'])

    def test_complete_three_rounds_and_metrics(self):
        self.write_fixture()
        result = runner.summarize(self.root)
        self.assertEqual(result['status'], 'PASS')
        metric = result['metrics']['16_adjacent/pre']
        self.assertEqual(metric['sums'], [32, 32, 32])
        self.assertEqual(metric['conservative'], [32, 32, 32])
        self.assertEqual(metric['spread'], 0)
        self.assertEqual(metric['rounds'][0]['domains'], 2)
        self.assertEqual(metric['rounds'][0]['median'], 16)

    def test_missing_rank(self):
        del self.results[1, 1]
        self.rejected()

    def test_failed_exit_despite_valid_result(self):
        self.statuses[1, 1]['exit_code'] = 7
        self.rejected()

    def test_timeout_despite_valid_result(self):
        self.statuses[1, 1]['timed_out'] = True
        self.rejected()

    def test_missing_status(self):
        del self.statuses[1, 1]
        self.rejected()

    def test_stale_timestamp(self):
        self.results[1, 1]['run']['started'] = 1
        self.rejected()

    def test_stale_mtime(self):
        self.write_fixture()
        os.utime(self.root / 'r1_d1.json', (1, 1))
        self.assertEqual(runner.summarize(self.root)['status'], 'FAIL')

    def test_wrong_run_host_round_rank_or_pid(self):
        for key, value in [('run_id', 'old'), ('host', 'other'), ('round', 8), ('rank', 8), ('pid', 8)]:
            with self.subTest(key=key):
                old = self.results[1, 1]['run'][key]
                self.results[1, 1]['run'][key] = value
                self.rejected()
                self.results[1, 1]['run'][key] = old

    def test_partial_belt_or_part(self):
        del self.results[1, 1]['32_skip4']['decoder_frames_per_s']
        self.rejected()
        del self.results[1, 1]['16_adjacent']
        self.rejected()

    def test_config_mismatch(self):
        self.results[1, 1]['config']['ckpt'] = True
        self.rejected()

    def test_config_type_mismatch(self):
        self.results[1, 1]['config']['ckpt'] = 0
        self.rejected()

    def test_invalid_pid(self):
        self.statuses[1, 1]['pid'] = None
        self.results[1, 1]['run']['pid'] = None
        self.rejected()

    def test_source_hash_or_actual_affinity_mismatch(self):
        self.spec['source_sha256'] = {'runner.py': 'frozen'}
        for data in self.results.values():
            data['run']['source_sha256'] = {'runner.py': 'frozen'}
        self.results[1, 1]['run']['source_sha256'] = {'runner.py': 'changed'}
        self.rejected()
        self.results[1, 1]['run']['source_sha256'] = {'runner.py': 'frozen'}
        self.spec['cpus'] = {str(r): {str(d): [d] for d in (0, 1)} for r in (1, 2, 3)}
        for (r, d), data in self.results.items():
            data['run'].update(affinity=[d], omp_threads=1)
        self.results[1, 1]['run']['affinity'] = [99]
        self.rejected()

    def test_wrong_input_or_device_or_runtime(self):
        for key, value in [('cases', ['other']), ('device', 'cuda'), ('torch', 'other')]:
            old = self.results[1, 1][key]
            self.results[1, 1][key] = value
            self.rejected()
            self.results[1, 1][key] = old

    def test_nonfinite_zero_negative_or_boolean_measurement(self):
        for value in [float('nan'), float('inf'), 0, -1, True, '16']:
            with self.subTest(value=value):
                self.results[1, 1]['16_adjacent']['pretrain_frames_per_s'] = value
                self.rejected()

    def test_rate_step_inconsistency(self):
        self.results[1, 1]['16_adjacent']['pretrain_step_s_B32'] = 3
        self.rejected()

    def test_corrupt_or_duplicate_key_json(self):
        self.write_fixture()
        for content in ['{', '{"run":{},"run":{}}', '[]']:
            (self.root / 'r1_d1.json').write_text(content)
            self.assertEqual(runner.summarize(self.root)['status'], 'FAIL')

    def test_extra_rank_or_round(self):
        self.write_fixture()
        runner.atomic_json(self.root / 'r1_d99.json', self.results[1, 1])
        self.assertEqual(runner.summarize(self.root)['status'], 'FAIL')

    def test_less_than_three_rounds(self):
        self.spec['rounds'] = 1
        self.rejected()

    def test_intermediate_round_is_checked_but_cannot_pass(self):
        self.results = {key: value for key, value in self.results.items() if key[0] == 1}
        self.statuses = {key: value for key, value in self.statuses.items() if key[0] == 1}
        self.write_fixture()
        result = runner.summarize(self.root, completed_rounds=1)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertNotIn('metrics', result)
        (self.root / 'r1_d1.json').unlink()
        self.assertEqual(runner.summarize(self.root, completed_rounds=1)['status'], 'FAIL')

    def test_unstable_three_rounds(self):
        self.results[3, 1]['16_adjacent'].update(pretrain_frames_per_s=32, pretrain_step_s_B32=1)
        self.write_fixture()
        self.assertEqual(runner.summarize(self.root)['status'], 'UNSTABLE')

    def test_requested_belt_subset_is_explicit(self):
        self.spec['belts'] = ['32_skip4']
        self.spec['parts'] = ['dec']
        self.write_fixture()
        result = runner.summarize(self.root)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(list(result['metrics']), ['32_skip4/dec'])

    def test_zero_cores_and_affinity(self):
        import cpu36_contract
        domain = list(range(38))
        for allowed in [[], [0], list(range(35))]:
            with self.assertRaises(ValueError):
                cpu36_contract.select_cpus(allowed, domain, {i: [i] for i in domain})

    def test_atomic_result_publication(self):
        target = self.root / 'result.json'
        runner.atomic_json(target, {'ok': 1})
        with self.assertRaises(ValueError):
            runner.atomic_json(target, {'bad': float('nan')})
        self.assertEqual(json.loads(target.read_text()), {'ok': 1})
        self.assertFalse(list(self.root.glob('*.tmp')))

    def test_barrier_success_stale_peer_abort_timeout(self):
        env = dict(SYNC_DIR=str(self.root), SYNC_N='2', SYNC_RANKS='0,1', SYNC_RANK='0',
                   RUN_ID='synthetic', SYNC_TIMEOUT='0.15')
        with patch.dict(os.environ, env, clear=True):
            runner.atomic_json(self.root / 'ready.1.json', {'run_id': 'synthetic', 'rank': 1})
            runner.barrier('ready')
            runner.atomic_json(self.root / 'old.1.json', {'run_id': 'previous', 'rank': 1})
            with self.assertRaises(RuntimeError):
                runner.barrier('old')
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                runner.barrier('never')
            self.assertLess(time.monotonic() - start, 1)
            runner.atomic_json(self.root / 'ABORT.json', {'reason': 'peer failed'})
            with self.assertRaises(RuntimeError):
                runner.barrier('aborted')

    def test_barrier_counts_expected_ranks_only(self):
        env = dict(SYNC_DIR=str(self.root), SYNC_N='2', SYNC_RANKS='0,1', SYNC_RANK='0',
                   RUN_ID='synthetic', SYNC_TIMEOUT='0.1')
        runner.atomic_json(self.root / 'ready.99.json', {'run_id': 'synthetic', 'rank': 99})
        with patch.dict(os.environ, env, clear=True), self.assertRaises(TimeoutError):
            runner.barrier('ready')

    def test_real_subprocess_failure_cancels_only_owned_peer(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
        self.addCleanup(lambda: (unrelated.kill(), unrelated.wait()) if unrelated.poll() is None else None)
        commands = {0: [sys.executable, '-c', 'import time; time.sleep(.1); raise SystemExit(7)'],
                    1: [sys.executable, '-c', 'import time; time.sleep(20)']}
        start = time.monotonic()
        states = runner.supervise(commands, {d: os.environ.copy() for d in commands}, self.root, 2)
        self.assertEqual(states[0]['exit_code'], 7)
        self.assertNotEqual(states[1]['exit_code'], 0)
        self.assertLess(time.monotonic() - start, 4)
        self.assertIsNone(unrelated.poll())
        self.assertTrue((self.root / 'ABORT.json').exists())

    def test_real_subprocess_timeout_and_success(self):
        commands = {0: [sys.executable, '-c', 'import time; time.sleep(20)']}
        states = runner.supervise(commands, {0: os.environ.copy()}, self.root, 0.2)
        self.assertTrue(states[0]['timed_out'])
        commands = {0: [sys.executable, '-c', 'print("synthetic process success")']}
        states = runner.supervise(commands, {0: os.environ.copy()}, self.root, 2)
        self.assertEqual(states[0]['exit_code'], 0)

    def test_spawn_error_is_recorded_and_peer_stopped(self):
        commands = {0: [sys.executable, '-c', 'import time; time.sleep(20)'],
                    1: [str(self.root / 'missing-executable')]}
        states = runner.supervise(commands, {d: os.environ.copy() for d in commands}, self.root, 2)
        self.assertNotEqual(states[0]['exit_code'], 0)
        self.assertNotEqual(states[1]['exit_code'], 0)

    def test_model_compute_ast_is_unchanged(self):
        source = BASELINE / 's4_models.py'
        candidate = WORK / 'candidate/s4_models.py'
        def computation(path):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            class RemoveCheckpoints(ast.NodeTransformer):
                def visit_Expr(self, node):
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'thread_checkpoint':
                        return None
                    return self.generic_visit(node)
            tree = RemoveCheckpoints().visit(tree)
            tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.module == 'runner')]
            tree.body = [n for n in tree.body if not (
                isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Tuple) and
                [x.id for x in n.targets[0].elts if isinstance(x, ast.Name)] == ['SYNC_DIR', 'SYNC_N'])]
            # Only barrier implementation, result metadata and final atomic publication may differ.
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == 'barrier':
                    node.body = [ast.Pass()]
                if isinstance(node, ast.FunctionDef) and node.name == 'main':
                    node.body = [n for n in node.body if not (
                        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                        (isinstance(n.value.func, ast.Name) and n.value.func.id == 'publish_result' or
                         isinstance(n.value.func, ast.Attribute) and isinstance(n.value.func.value, ast.Name)
                         and n.value.func.value.id == 'json' and n.value.func.attr == 'dump'))]
            return ast.dump(tree, include_attributes=False)
        self.assertEqual(computation(source), computation(candidate))

    def test_candidate_paths_are_isolated(self):
        shell = (WORK / 'candidate/run_node16.sh').read_text()
        self.assertIn('exec python3 "$S01_RUN/candidate/runner.py"', shell)
        self.assertIn('PYTHONPATH=$H/sw/torch_kml:$S01_RUN/candidate', shell)
        for shared in ('$H/opt/code', '$H/opt/s4', '$H/sw/hbm_alloc', '$H/sw/kml_shim'):
            self.assertNotIn(shared, shell)
        self.assertEqual((WORK / 'candidate/kml_ops.py').read_bytes(),
                         (BASELINE / 'kml_ops.py').read_bytes())

    @unittest.skipUnless(os.name == 'posix', 'Linux process-group branch not available on Windows')
    def test_posix_descendant_cleanup(self):
        # A child which spawns a descendant: only the owned session should be terminated.
        pidfile = self.root / 'descendant.pid'
        code = ('import subprocess,sys,time; from pathlib import Path; '
                'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(20)"]); '
                'Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(20)')
        commands = {0: [sys.executable, '-c', code, str(pidfile)]}
        states = runner.supervise(commands, {0: os.environ.copy()}, self.root, 0.5)
        self.assertTrue(states[0]['timed_out'])
        descendant = int(pidfile.read_text())
        stat = Path(f'/proc/{descendant}/stat')
        self.assertTrue(not stat.exists() or stat.read_text().split()[2] == 'Z')


if __name__ == '__main__':
    unittest.main(verbosity=2)
