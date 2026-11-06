"""Final queue/marker/source/review checks only; no dsub call."""
from pathlib import Path
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S07_ATOMIC_R7_20261106T073004Z_P1');sys.path.insert(0,str(root))
from prepare import verify_prepared
from review_gate import check_review
for pattern in ('S07_ATOMIC_R7_*/submit_once.marker','S07_ATOMIC_R7_*/job_id.txt'):
    found=list(root.parent.glob(pattern));print('EXISTING_R7_RECORDS',pattern,[str(p) for p in found],flush=True)
    if found:raise ValueError('existing R7 attempt; monitor same job, never submit again')
query=subprocess.run(['djob','-J'],check=True,stdout=subprocess.PIPE,timeout=10)
(root/'PRE_SUBMIT_QUEUE.raw').write_bytes(query.stdout);print(query.stdout.decode(),flush=True)
verify_prepared(root)
print('REVIEW_SHA',check_review(root,'8493beccf28ed9fe760ff2dd73a157147897aa551860c87aac476956e12b79bd'),flush=True)
print('S07_R7_PRE_SUBMIT_CHECK_PASS',flush=True)
