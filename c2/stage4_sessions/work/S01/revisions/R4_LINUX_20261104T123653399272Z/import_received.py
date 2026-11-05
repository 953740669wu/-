"""Verify and import only the returned S01-owned artifacts; never import credentials."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import zipfile

source, destination = Path(sys.argv[1]), Path(sys.argv[2])
text = source.read_text(encoding='utf-8-sig')
payload = text.split('S01_TRANSPORT_JSON_BEGIN\n', 1)[1].split('\nS01_TRANSPORT_JSON_END', 1)[0]
record = json.loads(payload)
blob = base64.b64decode(record.pop('archive_base64'))
assert hashlib.sha256(blob).hexdigest() == record['archive_sha256']
if os.name == 'nt' and any(len(str((destination / name).resolve())) >= 240 for name in record['files']):
    raise ValueError('Choose a shorter S01-owned destination before extraction; Windows ordinary path limit would be exceeded')
destination.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(io.BytesIO(blob)) as archive:
    assert set(archive.namelist()) == set(record['files'])
    for name, digest in record['files'].items():
        target = (destination / name).resolve()
        target.relative_to(destination.resolve())
        data = archive.read(name)
        assert hashlib.sha256(data).hexdigest() == digest, name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
record['local_directory'] = str(destination)
(source.parent / 'IMPORT.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print('Imported verified S01 artifacts:', len(record['files']), 'remote exit:', record['remote_context']['exit_code'])
