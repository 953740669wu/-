"""Actual frozen outer package preflight on login; no framework/model run."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

root = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z')
archive = root/'S00_REAL_DUAL_DDP_DEPLOYMENT.zip'
expected = '8d4fb023b99109850919b904561b0b228cdce50c607b9c26408adf90ce711434'
if archive.stat().st_size != 232024 or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise ValueError('wrong frozen deployment bytes/SHA')
with zipfile.ZipFile(archive) as z:
    if len(z.namelist()) != 37 or len(set(z.namelist())) != 37: raise ValueError('outer count/duplicate mismatch')
    z.extractall(root)
receipt = dict(status='FAIL', observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               outer_sha256=expected, commands=[], framework_model_requested=False, new_jobs=0)
for label, command in [('prepare',['/usr/bin/python3','-B',str(root/'prepare.py')]),
                        ('wrapper_tests',['/usr/bin/python3','-B',str(root/'tests/test_deployment.py')])]:
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)
    (root/'evidence'/('FINAL_'+label+'.log')).write_bytes(done.stdout)
    receipt['commands'].append(dict(label=label,command=command,returncode=done.returncode))
    if done.returncode: raise RuntimeError(label+' failed, raw log preserved')
    if label == 'wrapper_tests':
        text = done.stdout.decode()
        if not re.search(r'Ran 10 tests?\b',text) or not re.search(r'^OK\s*$',text,re.MULTILINE):
            raise ValueError('require all10 wrapper fixtures')
sys.path.insert(0,str(root))
from prepare import verify_prepared, save, sha
from run_job import application_command
pins = verify_prepared(root)
# Actual caller-to-entry flags and paths, with argparse --help before run().
command = application_command(root,pins)+['--help']
done = subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
(root/'evidence/FINAL_CLI_HELP.log').write_bytes(done.stdout)
receipt['commands'].append(dict(label='actual_caller_cli_help',command=command,returncode=done.returncode))
if done.returncode: raise RuntimeError('actual frozen CLI does not parse caller')
receipt.update(status='PASS_FROZEN_SHA_MANIFEST_LF_AST39_BASH_N_10_WRAPPER_FIXTURES_CLI_ONLY',
               source_manifest_sha256=sha(root/'ARTIFACT_SHA256.json'),
               pre_submit_checks=json.loads((root/'pre_submit_checks.json').read_text()),
               upstream_local_numerical_gate=pins['upstream_local_numerical_gate'],
               numeric_acceptance=False, standard_library_only=True)
save(root/'FINAL_PREPARATION_RECEIPT.json',receipt)
print(json.dumps(receipt,indent=2),flush=True)
