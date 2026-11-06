"""Focused actual-KML gate on a NEW reviewed allocation; no submission here."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback
import unittest
import cpu36_guard
from diagnostic_common import configure_backend,finish_backend

ROOT=Path(__file__).resolve().parent


def source_identity():
    manifest=ROOT/'SOURCE_SHA256.json';source=json.loads(manifest.read_text())
    for name,digest in source.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('source drift: '+name)
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected-cpus',required=True)
    p.add_argument('--cpu-contract',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();a.output_dir.mkdir(exist_ok=False,parents=True);result=dict(status='STARTED',cpu36={},new_jobs=0)
    try:
        result['source_manifest_sha256']=source_identity()
        cpu36_guard.prepare([int(x) for x in a.expected_cpus.split(',')],a.cpu_contract,result['cpu36'])
        import torch
        cpu36_guard.checkpoint(result['cpu36'],'after_framework',torch)
        runtime,expected=configure_backend(torch,'kml',[int(x) for x in a.expected_cpus.split(',')]);result['runtime']=runtime
        sys.path.insert(0,str(ROOT/'tests'));import test_linear_reuse as tests
        tests.OUTPUT=a.output_dir;tests.BACKEND='kml';tests.RUNTIME=runtime
        cpu36_guard.checkpoint(result['cpu36'],'before_linear_screen',torch)
        run=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.LinearTests))
        if not run.wasSuccessful():raise ValueError('strict linear screen failed; stop, preserve evidence, no retry')
        cpu36_guard.checkpoint(result['cpu36'],'after_linear_screen',torch);finish_backend(runtime,expected)
        if result['cpu36']['errors']:raise ValueError('CPU36 check failed')
        result.update(status='PASS_KML_LINEAR_ONLY_FULL_ENCODER_GATE_STILL_REQUIRED',tests=run.testsRun);code=0
    except Exception as exc:result.update(status='FAIL_STOP',error=repr(exc),traceback=traceback.format_exc());code=2
    (a.output_dir/'screen_result.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(code)
