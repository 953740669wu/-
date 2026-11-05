import copy
import contextlib
import io
import json
import os
import socket
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'candidate'))
import runner
import cpu36_contract as cpu
from test_regressions import RunnerChecks


class CPU36Pipeline(RunnerChecks):
    def test_preflight_runtime_schema_reaches_summary(self):
        # Exercise the producer, not a hand-written alternate reference schema.
        runtime = copy.deepcopy(self.results[1, 0]['run']['cpu36']['checkpoints'][-1]['runtime'])
        for name in (str(self.root / 'lib/libkml_sgemm_shim.so'), str(self.root / 'lib/libkblas.so')):
            runtime['libraries'][name] = dict(sha256='a' * 64)
        snap = self.results[1, 0]['run']['cpu36']['checkpoints'][-1]['snapshot']
        torch = SimpleNamespace(get_num_threads=lambda: 36, get_num_interop_threads=lambda: 608)
        with patch.dict(sys.modules, dict(torch=torch, numpy=SimpleNamespace(), kml_ops=SimpleNamespace())), \
             patch.dict(os.environ, dict(cpu.ENVIRONMENT, KML_BLAS_LIB=str(self.root / 'lib/libkblas.so')), clear=True), \
             patch.object(os, 'sched_setaffinity', create=True), \
             patch('importlib.import_module'), patch.object(cpu, 'snapshot_threads', return_value=snap), \
             patch.object(cpu, 'runtime_info', return_value=runtime), patch.object(runner, 'sha', return_value='a' * 64), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(runner.preflight(self.root, {0: self.spec['cpu_contracts']['0']}, {}, {}, 'synthetic-job'), 0)
        reference = runner.read_json(output.getvalue().strip())
        self.spec['runtime_reference'] = reference['runtime']
        for data in self.results.values():
            for checkpoint in data['run']['cpu36']['checkpoints']:
                checkpoint['runtime'] = copy.deepcopy(runtime)
        self.test_complete_three_rounds_and_metrics()

    def test_actual_domain_selection_preserves_last_two_and_authority(self):
        domain = list(range(76, 114))
        siblings = {i: [i] for i in domain}
        receipt = cpu.select_cpus(domain, domain, siblings)
        self.assertEqual(receipt['selected'], list(range(76, 112)))
        self.assertEqual(receipt['reserved'], [112, 113])
        self.assertEqual(cpu.select_cpus(domain[:36], domain, siblings)['selected'], domain[:36])

    def test_insufficient_cross_domain_or_reserved_allocation_rejected(self):
        domain = list(range(38))
        for allocated in [domain[:35], domain[:37], domain[:37] + [50], domain[2:]]:
            with self.assertRaises(ValueError):
                cpu.select_cpus(allocated, domain, {i: [i] for i in domain})

    def test_smt_duplicate_physical_core_rejected(self):
        domain = list(range(38))
        siblings = {i: [i] for i in domain}
        siblings[0] = siblings[1] = [0, 1]
        with self.assertRaises(ValueError):
            cpu.select_cpus(domain, domain, siblings)

    def test_live_supervisor_monitor_accepts_and_rejects_real_children(self):
        context = self.spec['cpu_contexts']['1']['0']
        child = ('import json,os,pathlib,sys,time; c=json.loads(pathlib.Path(sys.argv[1]).read_text()); '
                 'pathlib.Path(sys.argv[2]).write_text(json.dumps({"context":c,"checkpoints":[{"pid":os.getpid()}]})); '
                 'time.sleep(0.3)')
        for mode in ('good', 'out_of_bounds', 'missing'):
            directory = self.root / mode
            directory.mkdir()
            path = directory / 'cpu36_d0.json'
            runner.atomic_json(path, context)
            env = os.environ.copy()
            env['CPU36_CONTEXT'] = str(path)
            def snap(pid):
                return dict(complete=mode != 'missing', threads=[] if mode == 'missing' else
                            [dict(tid=pid, affinity=[36] if mode == 'out_of_bounds' else [0])], vanished=[], errors=[])
            with patch.object(cpu, 'snapshot_threads', side_effect=snap):
                states = runner.supervise({0: [sys.executable, '-c', child, str(path), str(directory / 'thread_rank0.json')]},
                                          {0: env}, directory, 2)
            self.assertEqual(states[0]['exit_code'] == 0, mode == 'good')
            if mode == 'good':
                self.assertGreater(states[0]['thread_monitor']['snapshots'], 0)
            else:
                self.assertTrue((directory / 'ABORT.json').exists())

    def test_each_tid_bound_one_cpu_is_valid(self):
        self.test_complete_three_rounds_and_metrics()

    def test_missing_actual_torch_or_one_thread_cannot_pass(self):
        for value in [None, 1]:
            self.results[1, 1]['run']['cpu36']['checkpoints'][-1]['torch_intraop'] = value
            self.rejected()

    def test_reserved_core_in_any_checkpoint_is_rejected(self):
        self.results[1, 1]['run']['cpu36']['checkpoints'][2]['snapshot']['threads'][1]['affinity'] = [75]
        self.rejected()

    def test_parent_monitor_detects_transient_violation(self):
        self.statuses[1, 1]['thread_monitor']['threads'][1]['masks'].append([500])
        self.rejected()

    def test_missing_checkpoint_or_incomplete_snapshot_is_rejected(self):
        records = self.results[1, 1]['run']['cpu36']['checkpoints']
        old = records[1]['snapshot']['complete']
        records[1]['snapshot']['complete'] = False
        self.rejected()
        records[1]['snapshot']['complete'] = old
        records.pop(2)
        self.rejected()

    def test_checkpoint_wrong_order_or_stale_time_is_rejected(self):
        records = self.results[1, 1]['run']['cpu36']['checkpoints']
        records[2], records[3] = records[3], records[2]
        self.rejected()
        records[2], records[3] = records[3], records[2]
        records[-1]['time'] = 1
        self.rejected()

    def test_environment_conflict_rejected(self):
        self.results[1, 1]['run']['cpu36']['checkpoints'][-1]['environment']['MKL_NUM_THREADS'] = '1'
        self.rejected()

    def test_runtime_library_or_module_identity_rejected(self):
        record = self.results[1, 1]['run']['cpu36']['checkpoints'][-1]
        record['runtime']['libraries']['/synthetic/libomp.so']['sha256'] = 'b' * 64
        self.rejected()

    def test_receipt_cannot_use_reserved_or_unallocated_cpu(self):
        self.results[1, 1]['run']['cpu36']['context']['receipt']['selected'][-1] = 75
        self.rejected()

    def test_missing_monitor_rejected(self):
        del self.statuses[1, 1]['thread_monitor']
        self.rejected()

    def test_publication_and_summary_use_real_contract_path(self):
        self.results = {(1, 0): self.results[1, 0]}
        self.statuses = {(1, 0): self.statuses[1, 0]}
        self.spec['domains'] = [0]
        self.spec['host'] = socket.gethostname()
        self.spec['cpu_contexts']['1']['0']['host'] = socket.gethostname()
        self.write_fixture()
        context_path = self.root / 'context.json'
        runner.atomic_json(context_path, self.spec['cpu_contexts']['1']['0'])
        env = dict(RUN_ID=self.spec['run_id'], RUN_ROUND='1', SYNC_RANK='0', SYNC_DIR=str(self.root),
                   CPU36_CONTEXT=str(context_path), OMP_NUM_THREADS='36', MKL_NUM_THREADS='36',
                   OPENBLAS_NUM_THREADS='1', OMP_PLACES='cores', OMP_PROC_BIND='close',
                   INPUT_PROTOCOL=self.spec['input_protocol'], TIMING_OUT='r1_d0.json')
        sample = self.results[1, 0]['run']['cpu36']['checkpoints'][-1]
        pid = os.getpid()
        snap = copy.deepcopy(sample['snapshot'])
        for i, row in enumerate(snap['threads']):
            row['tid'] = pid + i
        with patch.dict(os.environ, env, clear=True), patch.object(cpu, 'snapshot_threads', return_value=snap), \
             patch.object(cpu, 'runtime_info', return_value=sample['runtime']), \
             patch.object(os, 'sched_getaffinity', return_value={0}, create=True):
            runner.thread_checkpoint('before_framework')
            for name in cpu.required_checkpoints(self.spec):
                if name not in ('before_framework', 'publish'):
                    runner.thread_checkpoint(name, 36, 608, 'SYNTHETIC')
            target = self.root / 'reports'
            target.mkdir()
            out = {key: value for key, value in self.results[1, 0].items() if key != 'run'}
            runner.publish_result(out, self.root, 36, 608, 'SYNTHETIC')
        self.assertEqual(out['run']['cpu36']['checkpoints'][-1]['name'], 'publish')
        self.assertEqual(out['run']['affinity'], [0])
        # The real result must be accepted through the SAME summarize entry, not a test-only predicate.
        data = json.loads((target / 'r1_d0.json').read_text())
        self.results[1, 0] = data
        self.statuses[1, 0].update(pid=pid, started=data['run']['started'] - 1, finished=data['run']['finished'] + 1)
        self.statuses[1, 0]['thread_monitor'].update(pid=pid, threads=[dict(tid=pid, masks=[[0]])])
        self.write_fixture()
        # Restore real-file mtime; the generic fixture intentionally uses a historical synthetic clock.
        os.utime(self.root / 'r1_d0.json', (data['run']['finished'], data['run']['finished']))
        result = runner.summarize(self.root, completed_rounds=1)
        self.assertEqual(result['status'], 'INCOMPLETE', result)
        with patch.dict(os.environ, dict(env, MKL_NUM_THREADS='1'), clear=True), \
             patch.object(cpu, 'snapshot_threads', return_value=snap), \
             patch.object(cpu, 'runtime_info', return_value=sample['runtime']), \
             patch.object(os, 'sched_getaffinity', return_value={0}, create=True):
            with self.assertRaises(ValueError):
                runner.thread_checkpoint('invalid_environment', 36, 608, 'SYNTHETIC')


if __name__ == '__main__':
    unittest.main(verbosity=2)
