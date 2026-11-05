"""S00 login-side preparation and one-shot sequential submissions of reviewed payloads."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

BASE = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
CASE = BASE / 'S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt'
TERMINAL = ('SUCCEEDED', 'FAILED', 'CANCELLED')


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def execute(command, root, label, timeout=10):
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    (root / (label + '.stdout')).write_bytes(p.stdout)
    (root / (label + '.stderr')).write_bytes(p.stderr)
    save(root / (label + '.command.json'), dict(command=command, exit_code=p.returncode))
    if p.returncode: raise RuntimeError(label + ': exit ' + str(p.returncode))
    return p.stdout


def prepare(task, root):
    assert root.parent == BASE
    assert not (root / 'pre_submit_checks.json').exists()
    if task == 'S02':
        archive = root / 'S02_SEQUENCE5_R7_CODE.zip'
        assert archive.stat().st_size == 55378 and sha(archive) == 'bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092'
        payload = root / 'payload'; payload.mkdir()
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist()) == 24
            z.extractall(payload)
        manifest = json.loads((root / 'PACKAGE_MANIFEST.json').read_text())
        for name, entry in manifest['entries'].items():
            p = payload / name
            assert p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256'], name
        frozen = json.loads((payload / 'CASE_MANIFEST.json').read_text())
        assert CASE.stat().st_size == frozen['bytes'] and sha(CASE) == frozen['sha256']
        for p in payload.rglob('*'):
            if p.suffix in ('.sh', '.env', '.py'):
                assert b'\r' not in p.read_bytes(), str(p)
                if p.suffix == '.py': ast.parse(p.read_text(), feature_version=(3, 9))
                else: subprocess.run(['bash', '-n', str(p)], check=True)
        save(root / 'pre_submit_checks.json', dict(status='SHA_LF_SYNTAX_ONLY',
            payload_files={str(p.relative_to(root)): sha(p) for p in payload.rglob('*') if p.is_file()},
            package_sha256=sha(archive), case_path=str(CASE), case_bytes=CASE.stat().st_size,
            case_sha256=sha(CASE), case_mtime_ns=CASE.stat().st_mtime_ns))
        wrapper = '#!/bin/bash\nset -euo pipefail\nHERE=$(cd -- "$(dirname -- "$0")" && pwd -P)\n: "${CCS_JOB_ID:?native scheduler identity required}"\ntimeout --signal=TERM --kill-after=2s 45s /usr/bin/python3 -B "$HERE/cpp_readonly_identity.py" "$HERE" > "$HERE/cpp_probe.log" 2>&1 || echo "$?" > "$HERE/cpp_probe_nonzero.txt"\nexec env S02_CASE_FILE="' + str(CASE) + '" bash "$HERE/payload/run_s00_seq5_job.sh" strict\n'
        (root / 'run_s02_strict_once.sh').write_text(wrapper)
        subprocess.run(['bash', '-n', str(root / 'run_s02_strict_once.sh')], check=True)
    else:
        archive = root / 'S07_S00_WRAPPER_R3.zip'
        assert archive.stat().st_size == 71154 and sha(archive) == '08e0c921e33631c9e98ac1465cf854a74c1a353a08ecbc13f480b42f296da821'
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist()) == 11
            z.extractall(root)
        for line in (root / 'ARTIFACT_SHA256.txt').read_text().splitlines():
            digest, name = line.split('  ', 1); assert sha(root / name) == digest
        execute(['/usr/bin/python3', '-B', str(root / 'prepare.py')], root, 'prepare', 30)
        execute(['/usr/bin/python3', '-B', str(root / 'tests/test_scheduler_handoff.py')], root, 'handoff_mock_tests', 15)
    save(root / 'execution_layer_identity.json', {p.name: dict(sha256=sha(p), bytes=p.stat().st_size)
        for p in root.iterdir() if p.is_file() and p.suffix in ('.py', '.sh', '.zip')})


def observe(root, job):
    raw = execute(['djob', '-J', '-l', job], root, 'scheduler_latest')
    row = json.loads(raw)['data']['successData'][0]
    assert str(row['jobId']) == job
    if row['state'] == 'RUNNING' and not (root / 'scheduler_running.json').exists():
        (root / 'scheduler_running.json').write_bytes(raw)
    if row['state'] in TERMINAL:
        assert all(n['pids'] == '-' for g in row['resGroups'] for n in g['nodeResUsages'])
        (root / 'djob_final.json').write_bytes(raw)
    return row


def submit(task, root, dependency):
    if task == 'S07':
        old = json.loads((dependency / 'djob_final.json').read_text())['data']['successData'][0]
        assert old['state'] in TERMINAL and all(n['pids'] == '-' for g in old['resGroups'] for n in g['nodeResUsages'])
        save(root / 'S02_dependency_terminal.json', old)
    assert not list(root.glob('*submission*')) and not (root / 'submit_once.marker').exists()
    execute(['djob', '-J'], root, 'queue_before_submit')
    (root / 'submit_once.marker').open('x').write(task + ': exactly one reviewed job; no retries\n')
    command = ['dsub', '-J', '-q', 'q_hpcai']
    if task == 'S07': command += ['-x', 'job']
    command += ['-R', 'cpu=' + ('38' if task == 'S02' else '76') + ',mem=24576MB',
        '-RL', 'mem=24576MB', '-a', 'numa[count=' + ('1' if task == 'S02' else '2') + ',distribution=pack]',
        '-T', '900' if task == 'S02' else '300', '--env', 'none', '--cwd', str(root),
        '-oo', str(root / 'job.log'), 'bash', str(root / ('run_s02_strict_once.sh' if task == 'S02' else 'run_s07_r2_job.sh'))]
    raw = execute(command, root, 'submission')
    job = str(json.loads(raw)['data']['jobId'])
    (root / 'job_id.txt').write_text(job + '\n')
    print('SUBMITTED', task, job, flush=True)
    published, last = False, None
    while True:
        row = observe(root, job)
        if row['state'] != last:
            print('STATE', task, job, row['state'], flush=True); last = row['state']
        if task == 'S07' and row['state'] == 'RUNNING' and not published:
            published = True
            command = ['/usr/bin/python3', '-B', str(root / 'scheduler_handoff.py'), 'publish', '--root', str(root), '--job-id', job]
            with (root / 'login_publish.log').open('wb') as stream:
                p = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=40)
            save(root / 'login_publish_receipt.json', dict(command=command, exit_code=p.returncode))
            print('PUBLISH_ONCE', job, p.returncode, flush=True)
        if row['state'] in TERMINAL:
            print('TERMINAL', task, job, row['state'], row.get('jobExitCode'), flush=True)
            return
        time.sleep(1)


if __name__ == '__main__':
    action, task, root = sys.argv[1], sys.argv[2], Path(sys.argv[3]).resolve()
    assert root.parent == BASE and task in ('S02', 'S07')
    if action == 'prepare': prepare(task, root)
    elif action == 'submit': submit(task, root, Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else None)
    else: raise ValueError(action)
