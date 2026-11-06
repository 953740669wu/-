"""Small R7 job/CPU/readiness/atomic-report components, copied unchanged."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import cpu36_contract as cpu36


def write_rank_report(path, data):
    payload = json.dumps(data, indent=2, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False,
                                         dir=path.parent, prefix='.' + path.name + '.',
                                         suffix='.tmp') as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def publish_json(path, data):
    if path.exists():
        raise ValueError('refuse existing readiness file: ' + str(path))
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(data, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def await_peer_ready(directory, spec, rank, event_path):
    stop = int(os.environ['S07_CASE_DEADLINE_NS'])
    identity = dict(run_id=spec['run_id'], job_id=spec['job_id'], ready_token=spec['ready_token'])

    def check_deadline():
        if time.monotonic_ns() >= stop:
            raise TimeoutError('original case deadline reached while awaiting readiness')

    record_event(event_path, 'ready_context_wait', rank=rank)
    while True:
        check_deadline()
        try:
            context = json.loads((directory / 'participants.json').read_text(encoding='utf-8'))
            break
        except FileNotFoundError:
            time.sleep(0.05)
    pids = context.get('pids') if isinstance(context, dict) else None
    if (not isinstance(pids, list) or len(pids) != 2
            or any(type(pid) is not int or pid <= 0 for pid in pids)
            or len(set(pids)) != 2 or pids[rank] != os.getpid()
            or type(context.get('deadline_ns')) is not int
            or context != dict(identity, pids=pids, deadline_ns=stop)):
        raise ValueError('invalid current-run readiness participant identity/deadline')
    check_deadline()
    publish_json(directory / f'ready_rank{rank}.json', dict(identity, rank=rank, pid=pids[rank]))
    record_event(event_path, 'ready_published', rank=rank, job_id=spec['job_id'],
                 run_id=spec['run_id'], ready_token=spec['ready_token'])
    record_event(event_path, 'peer_ready_wait', rank=rank)
    while True:
        check_deadline()
        complete = True
        for peer in range(2):
            try:
                ready = json.loads((directory / f'ready_rank{peer}.json').read_text(encoding='utf-8'))
            except FileNotFoundError:
                complete = False
                continue
            if (not isinstance(ready, dict) or type(ready.get('rank')) is not int
                    or type(ready.get('pid')) is not int
                    or ready != dict(identity, rank=peer, pid=pids[peer])):
                raise ValueError(f'invalid current-run ready identity for rank{peer}')
        check_deadline()
        if complete:
            record_event(event_path, 'both_ready', rank=rank, pids=pids)
            return
        time.sleep(0.05)


def record_event(path, event, **fields):
    if path is None:
        return True
    row = dict(event=event, time_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(),
               pid=os.getpid(), **fields)
    try:
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        return True
    except OSError as exc:
        # Diagnostics must not interrupt the existing child/session cleanup.
        try:
            print(f'TRACE_WRITE_ERROR {path}: {exc}', file=sys.stderr, flush=True)
        except OSError:
            pass
        return False


def validate_pair(receipts):
    if (len(receipts) != 2 or receipts[0]['node'] == receipts[1]['node']
            or set(receipts[0]['allocated']) & set(receipts[1]['allocated'])):
        raise ValueError('require two distinct, disjoint authorized domains')


def validate_current_job(job_id):
    current = os.environ.get('CCS_JOB_ID')
    if not current or not current.strip():
        raise ValueError('missing current CCS_JOB_ID')
    if job_id != current:
        raise ValueError('configured job_id does not match current CCS_JOB_ID')


def load_allocation(path):
    if sys.platform != 'linux':
        raise ValueError('CPU36 live probe requires Linux sysfs and affinity APIs')
    data = json.loads(path.read_text(encoding='utf-8'))
    validate_current_job(data.get('job_id'))
    if set(data['ranks']) != {'0', '1'}:
        raise ValueError('exactly rank0/rank1 required')
    evidence = Path(data['scheduler_evidence'])
    if not evidence.is_absolute() or not evidence.is_file():
        raise ValueError('absolute raw scheduler allocation evidence required')
    allowed = set(os.sched_getaffinity(0))
    receipts = []
    for rank in range(2):
        entry = data['ranks'][str(rank)]
        node = entry['node']
        if type(node) is not int or node < 0:
            raise ValueError('invalid NUMA node')
        domain = cpu36.cpu_list(Path(f'/sys/devices/system/node/node{node}/cpulist').read_text())
        allocated = entry['allocated']
        if len(set(allocated)) != len(allocated) or not set(allocated) <= allowed:
            raise ValueError('duplicate CPU or allocation outside inherited authority')
        siblings = {str(cpu): cpu36.cpu_list(Path(
            f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list').read_text())
                    for cpu in domain}
        receipt = cpu36.select_cpus(allocated, domain, siblings)
        receipt['node'] = node
        receipts.append(receipt)
    validate_pair(receipts)
    return dict(job_id=str(data['job_id']), scheduler_evidence=str(evidence),
                scheduler_sha256=cpu36.sha(evidence), inherited_allowed=sorted(allowed),
                allocation_sha256=cpu36.sha(path), ranks=receipts)

