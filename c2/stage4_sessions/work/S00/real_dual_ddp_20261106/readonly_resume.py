"""Read-only scheduler, fixed-input and installed-library evidence; no job."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import socket


def query(argv, timeout=10):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return dict(command=argv, returncode=p.returncode, stdout=p.stdout.decode(), stderr=p.stderr.decode())


base = Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
result = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), host=socket.gethostname(),
              queue=query(['djob', '-J']), previous_job=query(['djob', '-J', '-l', '2051116']),
              series_records=[], installed_files=[], new_jobs=0)
for directory in sorted(base.glob('REAL_DUAL_DDP_*')):
    result['series_records'].append(dict(directory=str(directory), records={p.name: p.read_text()
        for p in directory.iterdir() if p.is_file() and p.name in ('submit_once.marker', 'job_id.txt', 'submission.result.json')}))
env = base / 'ENV_20261104T130730Z_R4'
for path in [env/'venv/bin/python3', env/'S01_payload/lib/libkml_sgemm_shim.so',
             Path('/opt/HPCKit/bisheng-lib/aarch64-unknown-linux-gnu/libomp.so'),
             Path('/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so')]:
    try:
        resolved = path.resolve(strict=True)
        before = resolved.stat()
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        after = resolved.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('installed file changed: ' + str(path))
        result['installed_files'].append(dict(path=str(path), realpath=str(resolved), bytes=after.st_size,
                                             mtime_ns=after.st_mtime_ns, sha256=digest))
    except OSError as exc:
        result['installed_files'].append(dict(path=str(path), status='UNAVAILABLE_ON_LOGIN_VERIFY_IN_JOB', error=repr(exc)))
# Fixed-input checker source is supplied as a literal by the local caller. It
# hashes the descriptor's original paths, without importing NumPy or Torch.
result['fixed_input_check'] = query(['/usr/bin/timeout', '-k', '5', '45', '/usr/bin/python3', '-B', '-c',
                                   FIXED_INPUT_SOURCE], timeout=52)
print(json.dumps(result, indent=2), flush=True)
