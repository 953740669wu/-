"""S02 same-PID CPU36 checks; frozen S01 CPU36_MODEL_V1 supplies the policy."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time

import cpu36_contract as contract


def capture_allocation():
    allowed = sorted(os.sched_getaffinity(0))
    receipts = contract.discover_contracts(allowed, 1)
    receipt = next(iter(receipts.values()))
    if receipt['allocated'] != allowed:
        raise ValueError('S02 requires a single authorized CPU36 domain')
    job = os.environ.get('CCS_JOB_ID')
    if not job:
        raise ValueError('missing actual job identity')
    return dict(job_id=job, host=platform.node(), receipt=receipt)


def validate_checkpoint(record, receipt):
    contract.validate_receipt(receipt)
    contract.validate_checkpoint(record, receipt)


def checkpoint(state, name, torch=None, namespace_probe=None):
    record = dict(name=name, pid=os.getpid(), time=time.time(),
        calling_tid=threading.get_native_id(), calling_affinity=sorted(os.sched_getaffinity(0)),
        environment={key: os.environ.get(key) for key in contract.ENVIRONMENT},
        snapshot=contract.snapshot_threads(os.getpid()))
    if torch is not None:
        record.update(torch_intraop=torch.get_num_threads(), torch_interop=torch.get_num_interop_threads(),
                      parallel_info=torch.__config__.parallel_info(), runtime=contract.runtime_info(namespace_probe))
    state['checkpoints'].append(record)
    try:
        if state['pid'] != record['pid']:
            raise ValueError('CPU guard PID changed')
        validate_checkpoint(record, state['receipt'])
    except Exception as exc:
        state['errors'].append(dict(checkpoint=name, error=repr(exc)))
        raise
    return record


def prepare(expected_cpus, allocation_file, state):
    if sys.platform != 'linux':
        raise ValueError('CPU36/KML requires Linux; no native fallback')
    if any(name in sys.modules for name in ('torch', 'numpy')):
        raise ValueError('capture and bind CPUs before framework import')
    if allocation_file is None:
        raise ValueError('missing pre-framework allocation receipt')
    actual = capture_allocation()
    frozen = json.loads(Path(allocation_file).read_text())
    if actual != frozen:
        raise ValueError('checker allocation/job/host differs from wrapper receipt')
    selected = actual['receipt']['selected']
    if expected_cpus != selected:
        raise ValueError('expected CPUs differ from selected36')
    state.update(version=contract.VERSION, pid=os.getpid(), **actual,
                 allocation_file_sha256=contract.sha(allocation_file), checkpoints=[], errors=[])
    os.sched_setaffinity(0, selected)
    if sorted(os.sched_getaffinity(0)) != selected:
        raise ValueError('pre-framework exact selected36 binding failed')
    checkpoint(state, 'before_framework')


def finish(state, torch):
    checkpoint(state, 'publish', torch)
    names = [item['name'] for item in state['checkpoints']]
    if state['errors'] or names != ['before_framework', 'after_framework', 'after_backend',
                                  'before_reference', 'after_reference', 'after_candidate', 'publish']:
        raise ValueError('missing/out-of-order/failed same-PID CPU36 evidence')


def finish_memory(state, torch):
    checkpoint(state, 'publish', torch)
    names = [item['name'] for item in state['checkpoints']]
    if state['errors'] or names != ['before_framework', 'after_framework', 'after_backend',
                                  'initialized', 'before_training', 'after_training', 'publish']:
        raise ValueError('missing/out-of-order/failed memory CPU36 evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args()
    receipt = capture_allocation()
    with args.capture.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2); stream.write('\n')
    value = receipt['receipt']
    print(value['node'], ','.join(map(str, value['allocated'])), ','.join(map(str, value['selected'])))
