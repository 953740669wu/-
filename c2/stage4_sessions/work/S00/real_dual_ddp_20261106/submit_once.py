"""Login-only current review + live deduplication + one durable submission."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from prepare import BASE, PREFIX, check_root, verify_prepared, save
from review_gate import check_review
from scheduler_handoff import publish


def documents(text):
    decoder = json.JSONDecoder()
    while text.strip():
        value, end = decoder.raw_decode(text.lstrip())
        yield value
        text = text.lstrip()[end:]


def query(argv):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    record = dict(command=argv, returncode=result.returncode, stdout=result.stdout.decode(), stderr=result.stderr.decode())
    if result.returncode: raise RuntimeError('live query failed: '+repr(record))
    return record


def deduplicate(root):
    series = []
    for directory in sorted(BASE.glob(PREFIX+'*')):
        for name in ('submit_once.marker', 'job_id.txt', 'submission.result.json'):
            path = directory/name
            if path.exists(): series.append(dict(path=str(path), raw=path.read_text()))
    listing = query(['djob', '-J'])
    details = []
    matched = []
    for document in documents(listing['stdout']):
        if document.get('code') != 'success': raise ValueError('invalid live queue result')
        rows = document.get('data', [])
        if not isinstance(rows, list): raise ValueError('unexpected queue schema')
        if document.get('totalElements') != len(rows): raise ValueError('queue pagination incomplete')
        for row in rows:
            if row['state'] not in ('RUNNING', 'PENDING'): raise ValueError('unexpected active queue state')
            raw = query(['djob', '-J', '-l', str(row['jobId'])])
            details.append(raw)
            jobs = json.loads(raw['stdout'])['data']['successData']
            if len(jobs) != 1 or str(jobs[0]['jobId']) != str(row['jobId']): raise ValueError('ambiguous job identity')
            job = jobs[0]
            execution = Path(job['execPath'])
            if execution.parent == BASE and execution.name.startswith(PREFIX): matched.append(job)
    evidence = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), series=series,
                    queue=listing, details=details, matched=matched)
    save(root/'pre_submit_deduplication.json', evidence)
    if series or matched: raise RuntimeError('existing series attempt/job: monitor or collect it, never resubmit')


def command(root, review_sha):
    return ['dsub', '-J', '-q', 'q_hpcai', '-x', 'job', '-R', 'cpu=76,mem=24576MB',
            '-RL', 'mem=24576MB', '-a', 'numa[count=2,distribution=pack]', '-T', '900',
            '--env', 'none', '--cwd', str(root), '-oo', str(root/'job.log'),
            'bash', str(root/'run_job.sh'), review_sha]


def submit(root):
    check_root(root)
    verify_prepared(root)
    review_sha = check_review(root)
    deduplicate(root)
    # Created before dsub, including failed/ambiguous submissions. Never remove.
    with (root/'submit_once.marker').open('x') as stream:
        stream.write('one real dual DDP attempt; no automatic retry, including ambiguous submission\n')
    argv = command(root, review_sha)
    save(root/'submission.command.json', dict(command=argv, review_sha256=review_sha, attempts=1))
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    except subprocess.TimeoutExpired as exc:
        (root/'submission.stdout').write_bytes(exc.stdout or b'')
        (root/'submission.stderr').write_bytes(exc.stderr or b'')
        save(root/'submission.result.json', dict(timed_out=True, ambiguous_job_id=True, retry=False))
        raise
    (root/'submission.stdout').write_bytes(result.stdout)
    (root/'submission.stderr').write_bytes(result.stderr)
    save(root/'submission.result.json', dict(returncode=result.returncode, timed_out=False, retry=False))
    if result.returncode: raise RuntimeError('submission failed; never retry')
    job = str(json.loads(result.stdout)['data']['jobId'])
    (root/'job_id.txt').write_text(job+'\n')
    print('SUBMITTED_ONCE', job, flush=True)
    began = time.monotonic()
    while True:
        record = query(['djob', '-J', '-l', job])
        save(root/'scheduler_observed_raw.json', record)
        rows = json.loads(record['stdout'])['data']['successData']
        if len(rows) != 1 or str(rows[0]['jobId']) != job: raise ValueError('wrong observed job')
        row = rows[0]
        if row['state'] == 'RUNNING':
            publish(root, job)
            print('PUBLISHED_ONCE', job, flush=True)
            return
        if row['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            raise RuntimeError('terminal before authority publication; collect same job')
        if time.monotonic()-began >= 3600:
            raise TimeoutError('queued60min; recheck this job before any cancellation; never resubmit')
        time.sleep(0.5)


if __name__ == '__main__': submit(Path(sys.argv[1]).resolve())
