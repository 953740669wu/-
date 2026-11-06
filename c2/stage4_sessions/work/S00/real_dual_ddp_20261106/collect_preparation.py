"""Snapshot only this task's login preflight originals; no job or weights."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z')
archive = root/'PRE_SUBMISSION_EVIDENCE.zip'
files = ['FINAL_PREPARATION_RECEIPT.json','pre_submit_checks.json','evidence/FINAL_prepare.log',
         'evidence/FINAL_wrapper_tests.log','evidence/FINAL_CLI_HELP.log',
         'preparation_checks/RECEIPT.json','preparation_checks/tests.log','preparation_checks/CHECK_SOURCE_SHA256.json']
metadata = {}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for name in files:
        path = root/name
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
            raise ValueError('preflight original changed during snapshot')
        metadata[name] = dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),mtime_ns=after.st_mtime_ns)
        z.writestr(name,data)
    z.writestr('PRE_SUBMISSION_INDEX.json',json.dumps(metadata,indent=2)+'\n')
receipt = dict(path=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files)+1)
print(json.dumps(receipt,indent=2))
