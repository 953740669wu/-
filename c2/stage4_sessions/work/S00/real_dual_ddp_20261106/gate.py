"""Native two-domain/DDR authority before framework import, within shared840s."""
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from prepare import check_root, verify_prepared, save, sha
from review_gate import check_review
from scheduler_handoff import live_context, create_request, await_handoff


def gate(root, deadline):
    check_root(root)
    pins = verify_prepared(root)
    check_review(root, os.environ['S00_REVIEW_SHA'])
    if socket.gethostname().startswith('login') or os.environ.get('HBM') != '0':
        raise ValueError('native compute/HBM0 required')
    context = live_context()
    request = create_request(root, context)
    remaining = deadline-time.monotonic()
    if remaining <= 0: raise TimeoutError('preflight budget exhausted')
    authority = await_handoff(root, request, context, 76, 24576, 900, timeout=remaining)
    if live_context() != context: raise ValueError('native job context changed')
    out = root/'job_evidence'
    save(out/'scheduler_handoff_receipt.json', authority)
    row = json.loads((root/'scheduler_allocation.json').read_bytes())['data']['successData'][0]
    if row['retryPolicy'] != dict(maxRetryCnt=0, currentRetryTimes=0): raise ValueError('retries forbidden')
    allocated = row['resGroups'][0]['resAlloc']
    if allocated['cpu'] != 76 or allocated['mem'] != 24576: raise ValueError('actual allocation differs')
    sys.path.insert(0, str(root/'payload/training/candidate'))
    import cpu36_contract as cpu36
    import runtime_guard
    contracts = cpu36.discover_contracts(context['allowed'], 2)
    if set(context['allowed']) != set().union(*(set(c['allocated']) for c in contracts.values())):
        raise ValueError('two complete authorized domains required')
    physical = {}
    total_ddr_kb = 0
    for node, contract in contracts.items():
        cpu36.validate_receipt(contract)
        if len(contract['allocated']) != 38: raise ValueError('38 allocated physical CPUs per domain required')
        for cpu in contract['allocated']:
            base = Path('/sys/devices/system/cpu/cpu'+str(cpu))
            if sorted(p.name for p in base.glob('node[0-9]*')) != ['node'+str(node)]:
                raise ValueError('CPU NUMA mismatch')
            physical[str(cpu)] = [(base/'topology'/name).read_text().strip()
                                 for name in ('physical_package_id', 'core_id')]
        mem = Path('/sys/devices/system/node/node'+str(node)+'/meminfo').read_text()
        (out/('ddr_node'+str(node)+'_meminfo.txt')).write_text(mem)
        total_ddr_kb += int(re.search(r'MemTotal:\s+(\d+)\s+kB', mem).group(1))
    if len({tuple(v) for v in physical.values()}) != 76: raise ValueError('76 distinct physical CPUs required')
    if total_ddr_kb < 24576*1024: raise ValueError('CPU-bearing DDR insufficient')
    allocation = root/'allocation.json'
    save(allocation, dict(job_id=context['job_id'], scheduler_evidence=authority['scheduler_evidence'],
         ranks={str(rank): dict(node=node, allocated=receipt['allocated'])
                for rank, (node, receipt) in enumerate(contracts.items())}))
    save(out/'verified_allocation.json', runtime_guard.load_allocation(allocation))
    libraries = []
    for path, digest in pins['runtime_sha256'].items():
        actual = sha(path)
        if actual != digest: raise ValueError('runtime library drift: '+path)
        p = Path(path)
        libraries.append(dict(path=path, realpath=str(p.resolve()), bytes=p.stat().st_size, sha256=actual))
    for exe in ['/usr/bin/numactl', '/usr/bin/timeout', pins['python']]:
        if not os.access(exe, os.X_OK): raise ValueError('missing existing executable: '+exe)
    save(out/'cpu_ddr_library_receipt.json', dict(**context, contracts=contracts, physical_ids=physical,
         libraries=libraries, memory_MB=24576, memory_limit_MB=24576, HBM=0))
    if time.monotonic() > deadline: raise TimeoutError('preflight budget exhausted')


if __name__ == '__main__': gate(Path(sys.argv[1]).resolve(), float(sys.argv[2]))
