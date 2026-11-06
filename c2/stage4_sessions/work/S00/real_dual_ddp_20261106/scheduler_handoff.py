"""Login-only scheduler query; atomic, fresh, job-bound handoff before frameworks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import time
import uuid


def encode(data):
    return (json.dumps(data, sort_keys=True, indent=2) + '\n').encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    temporary = path.with_name('.' + path.name + '.partial.' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def live_context():
    job = os.environ.get('CCS_JOB_ID')
    if not job or not job.strip():
        raise ValueError('missing native CCS_JOB_ID')
    return dict(job_id=job, host=socket.gethostname(), allowed=sorted(os.sched_getaffinity(0)))


def create_request(root, context):
    if not context['job_id'] or not context['job_id'].strip():
        raise ValueError('missing current job identity')
    request = dict(context=context, nonce=uuid.uuid4().hex, created_at=time.time())
    atomic_write(root / 'scheduler_request.json', encode(request))
    return request


def cpus(text):
    result = []
    for item in text.split(','):
        first, sep, last = item.strip().partition('-')
        result.extend(range(int(first), int(last) + 1) if sep else [int(first)])
    return sorted(result)


def await_handoff(root, request, context, expected_cpu, expected_mem, expected_wall, timeout=30):
    if request['context'] != context:
        raise ValueError('live job/host/CPU context changed')
    deadline = time.monotonic() + timeout
    ready = root / 'scheduler_ready.json'
    while not ready.is_file():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('no complete scheduler handoff within the bounded wait')
        time.sleep(min(0.02, remaining))
    header = json.loads(ready.read_bytes())
    raw_path = root / 'scheduler_allocation.json'
    before = raw_path.stat()
    raw = raw_path.read_bytes()
    after = raw_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('scheduler original changed while reading')
    now = time.time()
    if not (request['created_at'] <= header['generated_at'] <= now and now - header['generated_at'] <= 30):
        raise ValueError('stale/future scheduler handoff')
    if (header['job_id'] != context['job_id'] or header['nonce'] != request['nonce']
            or header['request_sha256'] != digest(encode(request)) or header['raw_sha256'] != digest(raw)):
        raise ValueError('job/request/original SHA mismatch')
    rows = json.loads(raw)['data']['successData']
    if len(rows) != 1:
        raise ValueError('require one exact current job record')
    job = rows[0]
    if (str(job['jobId']) != context['job_id'] or job['state'] != 'RUNNING'
            or job['exclusive'] is not True or job['jobWallClockLimit'] != expected_wall
            or len(job['resGroups']) != 1):
        raise ValueError('wrong job/state/exclusivity/wall limit')
    group = job['resGroups'][0]
    if (group['resReq']['cpu'] != expected_cpu or group['resReq']['mem'] != expected_mem
            or group['resLimit']['mem'] != expected_mem or len(group['nodeResUsages']) != 1):
        raise ValueError('wrong resources or multiple nodes')
    node = group['nodeResUsages'][0]
    if node['execNode'] != context['host'] or cpus(node['hwThreads']) != context['allowed']:
        raise ValueError('scheduler host/CPU differs from native compute context')
    if len(context['allowed']) != expected_cpu:
        raise ValueError('unexpected inherited CPU count')
    return dict(**context, scheduler_evidence=str(raw_path.resolve()), scheduler_sha256=digest(raw),
                nonce=request['nonce'], verified_at=now, raw_mtime_ns=after.st_mtime_ns)


def publish(root, job_id):
    # This command is invoked on login only, after the actual job becomes RUNNING.
    deadline = time.monotonic() + 30
    request_path = root / 'scheduler_request.json'
    while not request_path.is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError('no compute request within 30 seconds')
        time.sleep(0.05)
    request = json.loads(request_path.read_bytes())
    if request['context']['job_id'] != job_id or not 0 <= time.time() - request['created_at'] <= 30:
        raise ValueError('request is not from the fresh submitted job')
    cli = shutil.which('djob')
    if not cli:
        raise RuntimeError('login scheduler CLI unavailable; source its existing login profile first')
    command = [cli, '-J', '-l', job_id]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    except subprocess.TimeoutExpired as exc:
        atomic_write(root / 'scheduler_query_stderr.txt', exc.stderr or b'')
        atomic_write(root / 'scheduler_query_receipt.json', encode(dict(
            command=command, exit_code=None, timed_out=True, timeout_seconds=5)))
        atomic_write(root / 'scheduler_allocation.json', exc.stdout or b'')
        raise
    atomic_write(root / 'scheduler_query_stderr.txt', result.stderr)
    atomic_write(root / 'scheduler_query_receipt.json', encode(dict(command=command, exit_code=result.returncode)))
    atomic_write(root / 'scheduler_allocation.json', result.stdout)
    if result.returncode:
        raise RuntimeError('login scheduler query failed')
    atomic_write(root / 'scheduler_ready.json', encode(dict(job_id=job_id, nonce=request['nonce'],
        generated_at=time.time(), request_sha256=digest(encode(request)), raw_sha256=digest(result.stdout))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['publish'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--job-id', required=True)
    args = parser.parse_args()
    if args.root.resolve().parent != Path('/home/share/dengqingtian/opt/stage4_sessions/S00'):
        parser.error('new S00-owned remote staging root required')
    publish(args.root.resolve(), args.job_id)
