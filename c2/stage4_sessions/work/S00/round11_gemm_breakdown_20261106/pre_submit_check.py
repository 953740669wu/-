"""Login-only bounded checks before the original reviewed single submitter."""
from pathlib import Path
import json
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_20261106T041202Z')
sys.path.insert(0,str(root))
from prepare import verify_prepared,sha
from review_gate import check_review
for pattern in ('S02_GEMM5_*/submit_once.marker','S02_GEMM5_*/job_id.txt'):
    found=list(root.parent.glob(pattern));print('EXISTING_MARKERS',pattern,[str(p) for p in found],flush=True)
    assert not found,'already attempted R11; monitor original, do not submit'
q=subprocess.run(['djob','-J'],check=True,stdout=subprocess.PIPE,timeout=10)
print(q.stdout.decode(),flush=True)
verify_prepared(root)
print('REVIEW_SHA',check_review(root,'f75a7030f76613d1126960d2d27ace9b8e327d41788a7a3301cd7105ea5723f1'),flush=True)
subprocess.run(['timeout','--signal=TERM','--kill-after=5s','60s','env','-u','LD_PRELOAD','PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',
 '/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3','-B',str(root/'payload/inspect_engineering.py'),
 '--descriptor',str(root/'ENGINEERING_DESCRIPTOR.json'),'--descriptor-sha256','b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6',
 '--output',str(root/'PRE_SUBMIT_METADATA_CHECK.json')],check=True,stdout=subprocess.PIPE,timeout=67)
assert json.loads((root/'PRE_SUBMIT_METADATA_CHECK.json').read_text())['status']=='ENGINEERING_METADATA_HASH_GATE_PASS'
print('R11_PRE_SUBMIT_CHECK_PASS',flush=True)
