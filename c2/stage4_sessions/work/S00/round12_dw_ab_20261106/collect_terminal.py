"""Preserve all terminal phase outputs, including gate failures and partial ledgers."""
import json
from pathlib import Path
import subprocess
import sys
root=Path('/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z');sys.path.insert(0,str(root))
from collect_evidence import collect
job=(root/'job_id.txt').read_text().strip()
row=json.loads(subprocess.run(['djob','-J','-l',job],check=True,stdout=subprocess.PIPE,timeout=10).stdout)['data']['successData'][0]
assert str(row['jobId'])==job and row['state'] in ('SUCCEEDED','FAILED','CANCELLED')
query=subprocess.run(['timeout','--signal=TERM','--kill-after=5s','55s','/usr/bin/python3','-B',str(root/'check_old_inputs.py'),'--phase','AFTER'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=62)
(root/'old_inputs_after.log').write_bytes(query.stdout);print('OLD_INPUT_AFTER_EXIT',query.returncode,flush=True)
query=subprocess.run(['timeout','--signal=TERM','--kill-after=5s','45s','/usr/bin/python3','-B',str(root/'recheck_fixed_inputs.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=52)
(root/'FIXED_INPUTS_AFTER.json').write_bytes(query.stdout);(root/'FIXED_INPUTS_AFTER.stderr').write_bytes(query.stderr)
print('FIXED_INPUT_AFTER_EXIT',query.returncode,flush=True)
collect(root)
