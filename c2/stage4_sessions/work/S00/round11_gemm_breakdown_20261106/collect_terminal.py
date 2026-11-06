"""Collect the one terminal R11 job; old artifacts are read-only."""
import json
from pathlib import Path
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_20261106T041202Z')
sys.path.insert(0,str(root))
from prepare import sha,save
from collect_evidence import collect
job=(root/'job_id.txt').read_text().strip()
assert job=='2049454'
row=json.loads(subprocess.run(['djob','-J','-l',job],check=True,stdout=subprocess.PIPE,timeout=10).stdout)['data']['successData'][0]
assert row['state'] in ('SUCCEEDED','FAILED','CANCELLED') and str(row['jobId'])==job
base=root.parent
old=base/'ENGINEERING_PILOT_20261105T154333Z'
r9=base/'S02_PROFILE5_20261106T030149Z'
paths=[Path('/home/share/songzhenlong/eitfm/corpus_shape_20261102/manifest.csv'),old/'ENGINEERING_DESCRIPTOR.json',
 old/'payload/outputs/EXPOSURE_LEDGER.json',old/'payload/outputs/engineering_2043445/checkpoints/final.pt',
 r9/'payload/outputs/profile_2048959/EXPOSURE_LEDGER.json',r9/'payload/outputs/profile_2048959/checkpoints/final.pt',r9/'payload/baseline/kml_ops.py']
with (root/'OLD_INPUTS_AFTER.sha256').open('x') as stream:
    for path in paths:stream.write(sha(path)+'  '+str(path)+'\n')
q=subprocess.run(['timeout','--signal=TERM','--kill-after=5s','45s','env','-u','LD_PRELOAD','PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',
 '/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3','-B',str(root/'recheck_fixed_inputs.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=52)
(root/'FIXED_INPUTS_AFTER.json').write_bytes(q.stdout);(root/'FIXED_INPUTS_AFTER.stderr').write_bytes(q.stderr)
print('FIXED_INPUTS_AFTER',q.returncode,json.loads(q.stdout).get('status'),flush=True)
collect(root)
