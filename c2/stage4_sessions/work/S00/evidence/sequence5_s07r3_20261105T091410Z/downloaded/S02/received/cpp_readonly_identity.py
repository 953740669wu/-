"""Finite read-only compiler lookup inside an existing allocation; no compilation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

out = Path(sys.argv[1]) / 'cpp_readonly'
out.mkdir()
records = []


def query(label, command):
    try:
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        code, stdout, stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b'', exc.stderr or b''
    (out / (label + '.stdout')).write_bytes(stdout)
    (out / (label + '.stderr')).write_bytes(stderr)
    records.append(dict(label=label, command=command, exit_code=code, timeout_seconds=5))
    return stdout.decode(errors='replace').strip() if code == 0 else ''


paths = {name: shutil.which(name) for name in ('g++', 'c++', 'clang++', 'gcc')}
candidates = {Path(p).resolve() for name, p in paths.items() if p and name != 'gcc'}
if paths['gcc']:
    for name in ('g++', 'cc1plus'):
        reported = query('gcc_reports_' + name.replace('+', 'p'), [paths['gcc'], '-print-prog-name=' + name])
        p = Path(reported)
        if p.is_absolute() and p.is_file():
            candidates.add(p.resolve())
identities = []
for index, p in enumerate(sorted(candidates)):
    stat = p.stat()
    identities.append(dict(path=str(p), executable=os.access(p, os.X_OK), bytes=stat.st_size,
                           mtime_ns=stat.st_mtime_ns, sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for kind, command in [('version', [str(p), '--version']), ('elf', ['/usr/bin/file', '-L', str(p)]),
                          ('dependencies', ['/usr/bin/ldd', str(p)])]:
        query(str(index) + '_' + kind, command)
(out / 'identity.json').write_text(json.dumps(dict(job_id=os.environ.get('CCS_JOB_ID'), host=socket.gethostname(),
    original_PATH=os.environ.get('PATH'), lookup=paths, identities=identities, queries=records,
    compiled=False, installed=False, environment_changed=False), indent=2) + '\n')
