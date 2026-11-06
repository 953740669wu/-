"""NEW allocation only: one real-KML target shape screen before full strict5."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import traceback
import cpu36_guard
from diagnostic_common import configure_backend,finish_backend
from runtime_counts import source_identity,attach_native

ROOT=Path(__file__).resolve().parent


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expected-cpus',required=True)
    p.add_argument('--cpu-contract',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    a.output_dir.mkdir(exist_ok=False,parents=True);result=dict(status='STARTED',pid=os.getpid(),argv=list(sys.argv),protocol='ENGINEERING_DW_TILES_R12_V1',phase='target_screen')
    try:
        result.update(source_manifest_sha256=source_identity(),host=platform.node(),job_id=os.environ.get('CCS_JOB_ID'))
        if ROOT.name!='payload' or not ROOT.parent.name.startswith('S02_DW_R12_') or ROOT.parent.parent!=Path('/home/share/dengqingtian/opt/stage4_sessions/S00') or result['job_id'] in (None,'2043445','2048959','2049454'):
            raise ValueError('new reviewed R12 deployment/job required')
        result['cpu36']={};cpus=[int(x) for x in a.expected_cpus.split(',')]
        cpu36_guard.prepare(cpus,a.cpu_contract,result['cpu36'])
        import torch
        cpu36_guard.checkpoint(result['cpu36'],'after_framework',torch)
        spec=importlib.util.spec_from_file_location('r12_candidate_kml',ROOT/'candidate/kml_ops.py')
        candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
        runtime,expected=configure_backend(torch,'kml',cpus);result['runtime']=runtime;baseline=sys.modules['kml_ops']
        states={role:attach_native(module,True) for role,module in [('baseline',baseline),('candidate',candidate)]}
        result['native']=states
        sys.path.insert(0,str(ROOT/'tests'));from check_equivalence import compare
        torch.manual_seed(2026);aa=torch.randn(13312,512)*.01;bb=torch.randn(13312,2048)*.01
        aa_before=aa.clone();bb_before=bb.clone();values={};result['metrics']=[]
        original_empty=torch.empty
        for role,module in [('baseline',baseline),('candidate',candidate)]:
            backing=torch.full((512*2048+512,),-123456.,dtype=torch.float32);out=backing[256:-256].view(512,2048)
            from unittest.mock import patch
            def allocate(*shape,**kwargs):
                if shape!=(512,2048) or kwargs:raise ValueError('only original final C allocation expected')
                return out
            cpu36_guard.checkpoint(result['cpu36'],'before_'+role,torch)
            with patch.object(module.torch,'empty',side_effect=allocate):values[role]=module.gemm(aa,bb,ta=True)
            if not (backing[:256]==-123456.).all() or not (backing[-256:]==-123456.).all():raise ValueError('target output bounds violation')
            if not torch.equal(aa,aa_before) or not torch.equal(bb,bb_before):raise ValueError('target operands changed')
            rows=states[role]['captured_target']
            if len(rows)!=(1 if role=='baseline' else 2):raise ValueError('native target dispatch count')
            for column,row in zip(([0] if role=='baseline' else [0,1024]),rows):
                width=2048 if role=='baseline' else 1024
                if tuple(row)!=(101,112,111,512,width,13312,1.,aa.data_ptr(),512,bb.data_ptr()+column*4,2048,0.,out.data_ptr()+column*4,2048):raise ValueError('actual target pointer/ld mismatch')
            cpu36_guard.checkpoint(result['cpu36'],'after_'+role,torch)
        compare(torch,'actual_KML_target.output',values['baseline'],values['candidate'],'tensor',result['metrics'])
        result['imports']={role:dict(path=module.__file__,sha256=__import__('hashlib').sha256(Path(module.__file__).read_bytes()).hexdigest()) for role,module in [('baseline',baseline),('candidate',candidate)]}
        # configure_backend counts baseline logical call; actual native counter checks both paths.
        finish_backend(runtime,expected);cpu36_guard.checkpoint(result['cpu36'],'publish',torch)
        if result['cpu36']['errors']:raise ValueError('CPU36 failed')
        if source_identity()!=result['source_manifest_sha256']:raise ValueError('source changed during target screen')
        result['status']='PASS_ACTUAL_KML_TARGET_ONLY';code=0
    except Exception as exc:result.update(status='FAIL_CLOSE_FIXED_CANDIDATE',error=repr(exc),traceback=traceback.format_exc());code=2
    (a.output_dir/'screen_result.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(code)
