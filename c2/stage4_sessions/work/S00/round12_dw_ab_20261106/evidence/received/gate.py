"""Live native job/resource gate; bounded30s, consumed inside whole-entry840."""
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from prepare import check_root,verify_prepared,save
from review_gate import check_review
from scheduler_handoff import live_context,create_request,await_handoff
from cpu36_contract import discover_contracts,validate_receipt


def gate(root,deadline):
    check_root(root);verify_prepared(root)
    check_review(root,os.environ['S00_REVIEW_SHA'])
    if socket.gethostname().startswith('login') or os.environ.get('HBM')!='0':raise ValueError('compute/HBM0 required')
    context=live_context();request=create_request(root,context)
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TimeoutError('preflight budget exhausted')
    authority=await_handoff(root,request,context,38,24576,900,timeout=remaining)
    if live_context()!=context:raise ValueError('native context changed')
    out=root/'job_evidence';save(out/'scheduler_handoff_receipt.json',authority)
    raw=json.loads((root/'scheduler_allocation.json').read_bytes())['data']['successData'][0]
    if raw['retryPolicy']!=dict(maxRetryCnt=0,currentRetryTimes=0):raise ValueError('scheduler retries forbidden')
    alloc=raw['resGroups'][0]['resAlloc']
    if alloc['cpu']!=38 or alloc['mem']!=24576:raise ValueError('actual allocation differs')
    contracts=discover_contracts(context['allowed'],1);node,contract=next(iter(contracts.items()));validate_receipt(contract)
    if contract['allocated']!=context['allowed'] or len(contract['allocated'])!=38:raise ValueError('complete authorized38 domain required')
    physical={}
    for cpu in contract['allocated']:
        base=Path('/sys/devices/system/cpu/cpu'+str(cpu))
        if sorted(p.name for p in base.glob('node[0-9]*'))!=['node'+str(node)]:raise ValueError('per-core NUMA mismatch')
        physical[str(cpu)]=[(base/'topology'/f).read_text().strip() for f in ('physical_package_id','core_id')]
    if len({tuple(v) for v in physical.values()})!=38:raise ValueError('38 physical cores required')
    mem=Path('/sys/devices/system/node/node'+str(node)+'/meminfo').read_text();(out/'selected_ddr_node_meminfo.txt').write_text(mem)
    if int(re.search(r'MemTotal:\s+(\d+)\s+kB',mem).group(1))<24576*1024:raise ValueError('CPU-bearing DDR insufficient')
    for exe in ['/usr/bin/numactl','/usr/bin/timeout','/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3']:
        if not os.access(exe,os.X_OK):raise ValueError('missing existing executable: '+exe)
    save(out/'cpu_ddr_receipt.json',dict(**context,contract=contract,DDR_node=node,physical_ids=physical,
        allocation_mem_MB=24576,limit_mem_MB=24576,HBM=0,
        note='launcher inherits38; original S02 same-PID guard binds first36 before framework import; no setter or login profile here'))
    if time.monotonic()>deadline:raise TimeoutError('preflight budget exhausted')


if __name__=='__main__':gate(Path(sys.argv[1]).resolve(),float(sys.argv[2]))
