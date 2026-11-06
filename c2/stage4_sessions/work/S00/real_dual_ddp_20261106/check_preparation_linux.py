"""Login-only original wrapper snapshot checks; no framework or submission."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

root = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z')
archive = root/'PREPARATION_CHECK.zip'
if hashlib.sha256(archive.read_bytes()).hexdigest() != 'af43258313fddc5d48e35dadba62739e85c017900a6f61ebd447f122b9746000':
    raise ValueError('wrapper snapshot ZIP changed')
folder = root/'preparation_checks'
folder.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z: z.extractall(folder)
index = json.loads((folder/'CHECK_SOURCE_SHA256.json').read_text(encoding='utf-8'))
for name, digest in index.items():
    raw = (folder/name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest or b'\r' in raw:
        raise ValueError('SHA/LF failure: '+name)
    if name.endswith('.py'): ast.parse(raw.decode(), feature_version=(3,9))
    if name.endswith('.sh'): subprocess.run(['bash','-n',str(folder/name)], check=True, timeout=5)
command = ['/usr/bin/python3','-B',str(folder/'tests/test_deployment.py')]
done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
(folder/'tests.log').write_bytes(done.stdout)
text = done.stdout.decode()
passed = done.returncode == 0 and re.search(r'Ran 10 tests?\b',text) and re.search(r'^OK\s*$',text,re.MULTILINE)
receipt = dict(status='PASS_LOGIN_WRAPPER_SNAPSHOT_ONLY' if passed else 'FAIL', python=sys.version,
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), source_sha256=index, methods=10,
    returncode=done.returncode, command=command, checks=['SHA','LF','AST39','bash-n','10 wrapper fixtures'],
    framework_imports=False, new_jobs=0)
(folder/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2),flush=True)
if not passed: raise SystemExit(1)
