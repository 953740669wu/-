"""S00 execution/collection only for one unchanged R7 five-update memory job."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

BASE = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
OLD = BASE / 'S02_SEQUENCE5_R7_20261105T091410Z'
STRICT = OLD / 'payload/evidence/sequence5_2040203_strict/checker/result.json'
CASE = BASE / 'S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt'
TERMINAL = ('SUCCEEDED', 'FAILED', 'CANCELLED')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(root, label, command, timeout=15):
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    (root / (label + '.stdout')).write_bytes(p.stdout)
    (root / (label + '.stderr')).write_bytes(p.stderr)
    save(root / (label + '.command.json'), dict(command=command, exit_code=p.returncode))
    if p.returncode: raise RuntimeError(label + ': ' + str(p.returncode))
    return p.stdout


def prepare(root):
    existing = [str(p) for p in BASE.glob('S02_SEQUENCE5*') if p != root and 'MEMORY' in p.name]
    old_memory = list((OLD / 'payload/evidence').glob('*_memory'))
    assert not existing and not old_memory, (existing, old_memory)
    assert not (OLD / 'memory_submit_once.marker').exists()
    save(root / 'dedup_before.json', dict(existing_memory_roots=existing, old_memory_outputs=[], prior_memory_marker=False))
    run(root, 'queue_before', ['djob', '-J'])
    raw = run(root, 'strict_dependency', ['djob', '-J', '-l', '2040203'])
    job = json.loads(raw)['data']['successData'][0]
    assert job['state'] == 'SUCCEEDED' and job['jobExitCode'] == 0
    assert all(n['pids'] == '-' for g in job['resGroups'] for n in g['nodeResUsages'])
    archive = root / 'S02_SEQUENCE5_R7_CODE.zip'
    shutil.copyfile(OLD / archive.name, archive)
    assert archive.stat().st_size == 55378 and sha(archive) == 'bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092'
    payload = root / 'payload'; payload.mkdir()
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == 24
        z.extractall(payload)
    source = json.loads((payload / 'SOURCE_SHA256.json').read_text())
    for name, digest in source.items(): assert sha(payload / name) == digest, name
    for p in payload.rglob('*'):
        if p.suffix in ('.py', '.sh', '.env'):
            assert b'\r' not in p.read_bytes(), str(p)
            if p.suffix == '.py': ast.parse(p.read_text(), feature_version=(3, 9))
            else: subprocess.run(['bash', '-n', str(p)], check=True)
    assert sha(STRICT) == '905866e1149ba796652315083d0f79c3a705700c82296c172b962cbd009d4c93'
    frozen = json.loads((payload / 'CASE_MANIFEST.json').read_text())
    assert CASE.stat().st_size == frozen['bytes'] and sha(CASE) == frozen['sha256']
    run(root, 'sequence_gate_before_submit', ['/usr/bin/python3', '-B', str(payload / 'sequence_gate.py'), str(STRICT)], 30)
    save(root / 'pre_submit_checks.json', dict(status='ORIGINAL_SHA_LF_SYNTAX_CASE_AND_FIVE_STEP_GATE_PASS',
        payload_files={str(p.relative_to(root)): sha(p) for p in payload.rglob('*') if p.is_file()},
        execution_file_sha256=sha(Path(__file__)), package_sha256=sha(archive),
        case=dict(path=str(CASE), sha256=sha(CASE), bytes=CASE.stat().st_size, mtime_ns=CASE.stat().st_mtime_ns),
        strict=dict(path=str(STRICT), sha256=sha(STRICT), bytes=STRICT.stat().st_size, mtime_ns=STRICT.stat().st_mtime_ns)))
    print('PREPARED_ORIGINAL_GATE_PASS_NO_STRICT_RERUN', flush=True)


def submit(root):
    assert (root / 'pre_submit_checks.json').is_file()
    (root / 'memory_submit_once.marker').open('x').write('one R7 independent five-update memory job; no retry\n')
    command = ['dsub', '-J', '-q', 'q_hpcai', '-R', 'cpu=38,mem=24576MB', '-RL', 'mem=24576MB',
        '-a', 'numa[count=1,distribution=pack]', '-T', '900', '--env', 'none', '--cwd', str(root / 'payload'),
        '-oo', str(root / 'job.log'), 'env', 'S02_CASE_FILE=' + str(CASE),
        'S02_SEQUENCE5_RESULT=' + str(STRICT), 'bash', str(root / 'payload/run_s00_seq5_job.sh'), 'memory']
    job_id = str(json.loads(run(root, 'memory_submission', command))['data']['jobId'])
    (root / 'job_id.txt').write_text(job_id + '\n')
    print('SUBMITTED_MEMORY_ONCE', job_id, flush=True)
    previous = None
    while True:
        raw = run(root, 'scheduler_latest', ['djob', '-J', '-l', job_id])
        job = json.loads(raw)['data']['successData'][0]
        assert str(job['jobId']) == job_id
        if job['state'] != previous:
            print('STATE', job_id, job['state'], flush=True); previous = job['state']
        if job['state'] == 'RUNNING' and not (root / 'scheduler_running.json').exists():
            (root / 'scheduler_running.json').write_bytes(raw)
        if job['state'] in TERMINAL:
            assert all(n['pids'] == '-' for g in job['resGroups'] for n in g['nodeResUsages'])
            (root / 'djob_final.json').write_bytes(raw)
            print('TERMINAL', job_id, job['state'], job.get('jobExitCode'), flush=True)
            return
        time.sleep(1)


def collect(root):
    pre = json.loads((root / 'pre_submit_checks.json').read_text())
    job = json.loads((root / 'djob_final.json').read_text())['data']['successData'][0]
    assert job['state'] in TERMINAL and all(n['pids'] == '-' for g in job['resGroups'] for n in g['nodeResUsages'])
    assert sha(Path(__file__)) == pre['execution_file_sha256']
    for name, digest in pre['payload_files'].items(): assert sha(root / name) == digest, name
    for label in ('case', 'strict'):
        p = Path(pre[label]['path']); assert sha(p) == pre[label]['sha256'] and p.stat().st_size == pre[label]['bytes']
        save(root / (label + '_identity_after.json'), dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns))
    shutil.copyfile(STRICT, root / 'strict_reference_result.json')
    assert not list((root / 'payload/evidence').glob('*_strict'))
    paths = sorted(p for p in root.rglob('*') if p.is_file())
    metadata = {}
    for p in paths:
        before = p.stat(); digest = sha(p); after = p.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        metadata[p.relative_to(root).as_posix()] = dict(bytes=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest)
    start, end = [datetime.datetime.fromisoformat(job[k].replace('Z', '+00:00')) for k in ('startTime', 'endTime')]
    index = root / 'COLLECTION_S00.json'
    save(index, dict(job_id=str(job['jobId']), scheduler_state=job['state'], job_exit_code=job.get('jobExitCode'),
        captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), files=metadata, source_unchanged=True,
        strict_rerun=False, S07_run=False, S06_run=False, retries=0, real_HBM=False, formal_training=False,
        node_seconds=(end-start).total_seconds(), scheduler_usage_seconds=job['resGroups'][0]['nodeResUsages'][0]['wallclockDuration']))
    paths.append(index); bundle = root / ('JOB_' + str(job['jobId']) + '_full_evidence.zip')
    with zipfile.ZipFile(bundle, 'x', zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p, p.relative_to(root).as_posix())
    receipt = dict(bundle=str(bundle), bytes=bundle.stat().st_size, sha256=sha(bundle), file_count=len(paths),
        job_id=str(job['jobId']), state=job['state'], job_exit_code=job.get('jobExitCode'), node_seconds=(end-start).total_seconds())
    save(root / ('JOB_' + str(job['jobId']) + '_receipt.json'), receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    root = Path(sys.argv[2]).resolve()
    assert root.parent == BASE and root.name.startswith('S02_SEQUENCE5_R7_MEMORY_')
    {'prepare': prepare, 'submit': submit, 'collect': collect}[sys.argv[1]](root)
