"""Bounded login-only source/review/data/queue checks; no dsub here."""
import json
import os
from pathlib import Path
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z');sys.path.insert(0,str(root))
from prepare import verify_prepared
from review_gate import check_review
if sys.flags.optimize or os.environ.get('PYTHONOPTIMIZE'):raise ValueError('non-optimized Python required')
for pattern in ('S02_DW_R12_*/submit_once.marker','S02_DW_R12_*/job_id.txt'):
    found=list(root.parent.glob(pattern));print('EXISTING_MARKERS',pattern,[str(p) for p in found],flush=True)
    if found:raise ValueError('R12 already attempted; monitor original, never submit again')
query=subprocess.run(['djob','-J'],check=True,stdout=subprocess.PIPE,timeout=10);print(query.stdout.decode(),flush=True)
verify_prepared(root)
print('REVIEW_SHA',check_review(root,'ccdf321ea9982f582d17c4663a017efa197ff78aa177ae9843616bb2d8a73d0c'),flush=True)
subprocess.run(['timeout','--signal=TERM','--kill-after=5s','60s','env','-u','LD_PRELOAD','PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',
 '/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3','-B',str(root/'inspect_metadata.py'),'--output',str(root/'PRE_SUBMIT_METADATA_CHECK.json')],check=True,timeout=67)
assert json.loads((root/'PRE_SUBMIT_METADATA_CHECK.json').read_text())['status']=='ENGINEERING_METADATA_HASH_GATE_PASS'
print('R12_PRE_SUBMIT_CHECK_PASS',flush=True)
