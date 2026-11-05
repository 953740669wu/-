"""Use new output paths to verify final source identities and entry rejection."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
case=ROOT.parent/'round3_20261104T134939Z/case/fixed_16_pre.pt'
old=ROOT.parents[1]/'S00/evidence/memory3_s07_r2_20261105/S02/received/strict_reference_result.json'
common=['--case-file',str(case),'--expected-cpus',','.join(map(str,range(36))),
        '--cpu-contract','not-read-on-Windows.json']
current=hashlib.sha256((ROOT/'SOURCE_SHA256.json').read_bytes()).hexdigest()
checks=[]
for name,extra,reason in [
    ('check_sequence5.py',[],'Linux'),
    ('train_sequence5.py',['--checkpoint','0','--strict-result',str(old)],'old one-step result refused')]:
    out=ROOT/'evidence'/('rejected_final_'+name.replace('.py','.json'))
    assert not out.exists(), 'use a new evidence path; never overwrite a previous result'
    run=subprocess.run([sys.executable,'-B',str(ROOT/name),*common,*extra,'--output',str(out)],
                       capture_output=True,text=True)
    out.with_suffix('.stdout.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
    assert out.exists() and 'refuse existing output' not in run.stdout+run.stderr
    data=json.loads(out.read_text())
    assert run.returncode==2 and reason in data['error'] and data['source_manifest_sha256']==current
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value
               for path,value in data['source_sha256'].items())
    checks.append(dict(entry=name,exit=2,error=data['error'],result=out.relative_to(ROOT).as_posix(),
                       source_manifest_sha256=current))
path=ROOT/'evidence/local_validation.json'
record=json.loads(path.read_text());record['final_entry_rejections']=checks
path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
(ROOT/'evidence/entry_receipt_version_note.json').write_text(json.dumps(dict(
    initial_finalization='Detected pre-final source SHA in earlier rejection receipts; final check stopped',
    cause='Harness reused output paths; entry correctly refused overwrite, then harness read old JSON',
    preserved_previous_results=True,
    first_refresh_attempt='Inline harness IndentationError; no statement or model executed',
    resolved='New output paths plus fresh result existence/current manifest/source SHA assertions',
    final_results=checks,production_code_or_archive_changed=False),indent=2)+'\n',encoding='utf-8')
print(json.dumps(checks,indent=2))
