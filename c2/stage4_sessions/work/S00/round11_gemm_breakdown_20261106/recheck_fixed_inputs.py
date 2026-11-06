"""Bounded read-only identities of the original fixed inputs; no array imports."""
import datetime
import hashlib
import json
from pathlib import Path
import signal

result=dict(status='STARTED',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checked=[],arrays_read=False,model_run=False)


def check(path,digest,expected_bytes=None):
    p=Path(path);before=p.stat();h=hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or h.hexdigest()!=digest or (expected_bytes is not None and after.st_size!=expected_bytes):
        raise ValueError('SOURCE_CHANGED: '+str(p))
    result['checked'].append(dict(path=str(p),bytes=after.st_size,mtime_ns=after.st_mtime_ns,sha256=h.hexdigest()))


def timeout(*_):raise TimeoutError('fixed input metadata40s budget exhausted')


if __name__=='__main__':
    signal.signal(signal.SIGALRM,timeout);signal.alarm(40)
    try:
        p=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json')
        check(p,'b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6')
        d=json.loads(p.read_text())
        for a in (d['corpus']['manifest'],d['selection']['cases_txt'],d['exposure_ledger']):check(a['path'],a['sha256'],a.get('bytes'))
        for u in d['train']:
            for key,prefix in [('path','npz'),('sidecar_path','sidecar')]:check(u[key],u[prefix+'_sha256'],u[prefix+'_bytes'])
        result.update(status='FIXED16_CURRENT_SOURCE_SHA_PASS',units=len(d['train']),files=len(result['checked']))
    except Exception as exc:result.update(status='SOURCE_CHANGED' if 'SOURCE_CHANGED' in str(exc) else 'METADATA_CHECK_FAILED',error=repr(exc))
    finally:print(json.dumps(result,indent=2),flush=True)
