"""Run the unchanged S02 checker in this process and verify its CPU affinity."""
import json
import os
from pathlib import Path
import runpy
import sys

expected = {int(cpu) for cpu in os.environ['S02_CPUSET'].split(',')}
assert len(expected) == 4
out = Path(os.environ['S02_AFFINITY_REPORT'])
record = {'pid': os.getpid(), 'expected_cpus': sorted(expected), 'stages': []}


def verify(stage):
    actual = set(os.sched_getaffinity(0))
    threads = {p.name: sorted(os.sched_getaffinity(int(p.name)))
               for p in Path('/proc/self/task').iterdir()}
    record['stages'].append({'stage': stage, 'actual_cpus': sorted(actual),
                             'thread_cpus': threads})
    out.write_text(json.dumps(record, indent=2) + '\n')
    assert actual == expected, f'{stage}: checker CPU set {actual} != {expected}'
    assert all(set(cpus) <= expected for cpus in threads.values()), 'thread escaped allocated CPUs'


verify('checker_process_before_import')
import torch
import numpy
# OMP_PROC_BIND=false preserves the explicit four-CPU process mask.
torch.set_num_threads(4)
verify('checker_process_after_torch_thread_setup')
checker = Path(os.environ['S02_RUN']) / 'tests/check_equivalence.py'
sys.path.insert(0, str(checker.parent))
sys.argv = [str(checker), *sys.argv[1:]]
try:
    runpy.run_path(str(checker), run_name='__main__')
finally:
    verify('checker_process_exit')
