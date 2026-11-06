"""Read-only old artifacts: bounded byte/SHA check, receipts only in this new root."""
import argparse
import json
from pathlib import Path
import signal
from prepare import sha,save
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['BEFORE','AFTER'],required=True);args=p.parse_args()
root=Path(__file__).resolve().parent
out=root/('OLD_INPUTS_'+args.phase+'.json')
if out.exists():raise FileExistsError('preserve original check receipt')
def timeout(*_):raise TimeoutError('old artifact SHA check50s exceeded')
signal.signal(signal.SIGALRM,timeout);signal.alarm(50)
records=[]
try:
    for asset in json.loads((root/'OLD_INPUT_IDENTITIES.json').read_text(encoding='utf-8')):
        path=Path(asset['path']);before=path.stat();digest=sha(path);after=path.stat()
        if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns or digest!=asset['sha256']:
            raise ValueError('OLD_SOURCE_CHANGED: '+str(path))
        records.append(dict(path=str(path),bytes=after.st_size,mtime_ns=after.st_mtime_ns,sha256=digest))
    save(out,dict(status='OLD_INPUT_IDENTITIES_PASS',phase=args.phase,checked=records))
except BaseException as exc:
    save(out,dict(status='OLD_INPUT_CHECK_FAILED',phase=args.phase,checked=records,error=repr(exc)));raise
print('OLD_INPUT_IDENTITIES_PASS',args.phase,len(records),flush=True)
