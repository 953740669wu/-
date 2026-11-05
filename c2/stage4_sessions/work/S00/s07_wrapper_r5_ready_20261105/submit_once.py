"""Future login-only one-shot submission, after separate review and scheduling."""
import json
from pathlib import Path
import subprocess
import sys
import time

from prepare import BASE, PREFIX, ARCHIVE, INNER_SHA, sha
from scheduler_handoff import publish


def submit(root):
    if root.parent != BASE or not root.name.startswith(PREFIX): raise ValueError('new S00 readiness R5 directory required')
    if sha(root / ARCHIVE) != INNER_SHA: raise ValueError('diagnostic inner changed')
    if not (root / 'pre_submit_checks.json').is_file(): raise ValueError('prepare must pass first')
    if (root / 'submission.json').exists(): raise FileExistsError('submission already exists')
    with (root / 'submit_once.marker').open('x') as f: f.write('one separately arranged R4 diagnostic job; no retries\n')
    command = ['dsub', '-J', '-q', 'q_hpcai', '-x', 'job', '-R', 'cpu=76,mem=24576MB',
        '-RL', 'mem=24576MB', '-a', 'numa[count=2,distribution=pack]', '-T', '300', '--env', 'none',
        '--cwd', str(root), '-oo', str(root / 'job.log'), 'bash', str(root / 'run_s07_diag_job.sh')]
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    (root / 'submission.json').write_bytes(p.stdout)
    (root / 'submission.stderr').write_bytes(p.stderr)
    (root / 'submission.command.json').write_text(json.dumps(dict(command=command, exit_code=p.returncode), indent=2) + '\n')
    if p.returncode: raise RuntimeError('submission failed; do not retry')
    job = str(json.loads(p.stdout)['data']['jobId']); (root / 'job_id.txt').write_text(job + '\n')
    while True:
        p = subprocess.run(['djob', '-J', '-l', job], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        (root / 'scheduler_observed.json').write_bytes(p.stdout)
        (root / 'scheduler_observed.stderr').write_bytes(p.stderr)
        if p.returncode: raise RuntimeError('queue observation failed; no second submission')
        observed = json.loads(p.stdout)['data']['successData'][0]
        if str(observed['jobId']) != job: raise ValueError('wrong job in scheduler observation')
        state = observed['state']
        if state == 'RUNNING':
            publish(root, job)  # Original helper: one query, atomic raw/ready, no publication retry.
            print('PUBLISHED_ONCE', job, flush=True); return
        if state in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            raise RuntimeError('job became terminal before publication; collect without retry')
        time.sleep(1)


if __name__ == '__main__': submit(Path(sys.argv[1]).resolve())
