"""Final queue/marker/source/review checks only; no dsub call."""
from pathlib import Path
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S07_STACK_R6_20261106T062352Z');sys.path.insert(0,str(root))
from prepare import verify_prepared
from review_gate import check_review
for pattern in ('S07_STACK_R6_*/submit_once.marker','S07_STACK_R6_*/job_id.txt'):
    found=list(root.parent.glob(pattern));print('EXISTING_R6_RECORDS',pattern,[str(p) for p in found],flush=True)
    if found:raise ValueError('existing R6 attempt; monitor same job, never submit again')
query=subprocess.run(['djob','-J'],check=True,stdout=subprocess.PIPE,timeout=10)
(root/'PRE_SUBMIT_QUEUE.raw').write_bytes(query.stdout);print(query.stdout.decode(),flush=True)
verify_prepared(root)
print('REVIEW_SHA',check_review(root,'b9082f2385df26e05ff6ccd9b11f421db38e2e597d643bff81b2d9859e09b250'),flush=True)
print('S07_R6_PRE_SUBMIT_CHECK_PASS',flush=True)
