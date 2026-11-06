"""Hash shared R4 module files and preserve installed DDP source without imports."""
import base64
import datetime
import hashlib
import json
from pathlib import Path

venv = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv')
torch = Path('/home/share/songzhenlong/eitfm/sw/torch_kml/torch')
records = []
for path in [torch/'__init__.py', torch/'nn/parallel/distributed.py',
             venv/'lib64/python3.9/site-packages/numpy/__init__.py']:
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('module file changed while hashing')
    record = dict(path=str(path), realpath=str(path.resolve()), bytes=len(raw), mtime_ns=after.st_mtime_ns,
                  sha256=hashlib.sha256(raw).hexdigest())
    if path == torch/'nn/parallel/distributed.py': record['source_base64'] = base64.b64encode(raw).decode()
    records.append(record)
print(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      status='READ_FILES_ONLY_NO_FRAMEWORK_IMPORT', files=records), indent=2))
