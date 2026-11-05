"""Run only the authorized short stdlib protocol checks in this account's unique directory."""
import base64
from datetime import datetime, timezone
import getpass
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile

run_id = 'R4_LINUX_20261104T123653399272Z'
assert sys.platform == 'linux' and getpass.getuser() == 'dengqingtian'
base = Path('/home/share/dengqingtian/opt/stage4_sessions/S01')
root = base / run_id
root.resolve().relative_to(base.resolve())
root.mkdir(parents=True, exist_ok=False)
context = dict(started_utc=datetime.now(timezone.utc).isoformat(), host=platform.node(),
               platform=platform.platform(), python=sys.executable, python_version=sys.version,
               account=getpass.getuser(), root=str(root), scope='SHORT_STDLIB_PROTOCOL_ONLY',
               torch_imported=False, model_started=False, hbm_started=False, jobs_submitted=0)
code = 1
try:
    raw = base64.b64decode(sys.stdin.buffer.read())
    assert hashlib.sha256(raw).hexdigest() == '162620a88c6edb9ee12c2d7d8bc4b07bd574c93be6d4d1b8f8018ad8586968b6'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            target.relative_to(root.resolve())
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(archive.read(member))
    payload = root / 'linux_payload'
    print('S01: payload verified; running Bash/Linux process protocol checks only.', file=sys.stderr, flush=True)
    command = ['bash', str(payload / 'run_linux_checks.sh')]
    result = subprocess.run(command, cwd=payload, capture_output=True, text=True, timeout=60)
    (root / 'protocol_stdout.txt').write_text(result.stdout, encoding='utf-8')
    (root / 'protocol_stderr.txt').write_text(result.stderr, encoding='utf-8')
    context.update(command=command, exit_code=result.returncode)
    code = result.returncode
except Exception as exc:
    context.update(exit_code=1, error=f'{type(exc).__name__}: {exc}')
finally:
    context['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (root / 'remote_context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    output = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                data = path.read_bytes()
                archive.writestr(relative, data)
                hashes[relative] = hashlib.sha256(data).hexdigest()
    blob = output.getvalue()
    transport = dict(remote_context=context, files=hashes, archive_sha256=hashlib.sha256(blob).hexdigest(),
                     archive_base64=base64.b64encode(blob).decode('ascii'))
    print('S01_TRANSPORT_JSON_BEGIN')
    print(json.dumps(transport))
    print('S01_TRANSPORT_JSON_END', flush=True)
    print('S01: protocol complete; own-task evidence returned. No training/job started.', file=sys.stderr, flush=True)
raise SystemExit(code)
