"""LOCAL_FIXTURE only: new protocol verdicts, captures and exact review bindings."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import profile_outcome as p
import review_gate as g
from prepare import RESOURCES
import collect_evidence as c


class ProfileDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'evidence');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'payload/outputs/profile_42';self.run.mkdir(parents=True)

    def fixture(self):
        steps=[]
        for i in range(1,6):
            profile=dict(step=i,sampled=i>=3,status='CAPTURED' if i>=3 else 'WARMUP_NO_CPU_CAPTURE',kml_markers=149 if i>=3 else 0)
            if i>=3:
                events=[dict(name='S02/'+n) for n in p.PHASES]+[dict(name='S02/KML_python_gemm_envelope')]*149
                for kind,value in [('trace',dict(traceEvents=events)),('summary',dict(events=len(events),top_self_cpu=[]))]:
                    path=self.run/('trace_step_'+str(i)+'.json' if kind=='trace' else 'events_step_'+str(i)+'.json')
                    path.write_text(json.dumps(value));profile[kind]=dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                profile['events']=len(events)
            steps.append(dict(step=i,adamw_step=i,batch_size=64,cursor=64*i,frame_indices=list(range((i-1)*64,i*64)),
               baseline_loss_metrics=[dict(name=n,passed=True) for n in ('total','voltage','coarse')],kml_calls=149,profile=profile))
        (self.run/'steps.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in steps))
        app=dict(protocol=p.PROTOCOL,status=p.SUCCESS,completed_updates=5,planned_updates=5,consumed_frames=320,
                 engineering_only=True,source_and_data_after='PASS_SAME_FROZEN_IDENTITIES',cpu36=dict(errors=[],checkpoints=[{}]*19),runtime=dict(kml_gemm_calls=745),checkpoint=dict(sha256='a'*64),
                 recovery=dict(status='PASS_NO_EXTRA_UPDATE',extra_updates=0,parameters_exact=True,optimizer_exact=True,rng_exact=True,cursor_exact=True,identity_exact=True))
        (self.run/'result.json').write_text(json.dumps(app));(self.run/'EXPOSURE_LEDGER.json').write_text('{}');return app

    def test_new_profile_success_and_2plus3(self):
        self.fixture();result=p.inspect(self.root,'42');self.assertEqual(result['errors'],[]);self.assertTrue(result['profile5_complete'])

    def test_missing_trace_never_passes(self):
        self.fixture();(self.run/'trace_step_4.json').unlink();self.assertFalse(p.inspect(self.root,'42')['profile5_complete'])

    def test_missing_phase_events_never_passes(self):
        self.fixture();path=self.run/'trace_step_3.json';value=json.loads(path.read_text());value['traceEvents']=[];path.write_text(json.dumps(value))
        self.assertFalse(p.inspect(self.root,'42')['profile5_complete'])

    def test_oversized_raw_trace_not_truncated_or_accepted(self):
        self.fixture();path=self.run/'trace_step_5.json';path.write_bytes(b'x'*(8*1024*1024+1))
        self.assertFalse(p.inspect(self.root,'42')['profile5_complete']);self.assertEqual(path.stat().st_size,8*1024*1024+1)

    def test_unsupported_limit_incomplete_keep_original_status(self):
        for status in ['UNSUPPORTED_PROFILER','PROFILE_LIMIT_EXCEEDED','INCOMPLETE','SOURCE_CHANGED']:
            (self.run/'result.json').write_text(json.dumps(dict(protocol=p.PROTOCOL,status=status,error='original')))
            result=p.inspect(self.root,'42');self.assertEqual(result['application_status'],status);self.assertFalse(result['profile5_complete'])

    def test_old_success_and_failed_numeric_metrics_rejected(self):
        app=self.fixture();app['status']='ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE';(self.run/'result.json').write_text(json.dumps(app))
        self.assertFalse(p.inspect(self.root,'42')['profile5_complete'])
        self.fixture();steps=[json.loads(s) for s in (self.run/'steps.jsonl').read_text().splitlines()];steps[4]['baseline_loss_metrics'][0]['passed']=False
        (self.run/'steps.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in steps));self.assertFalse(p.inspect(self.root,'42')['profile5_complete'])

    def test_only_new_specific_decision_and_all_bindings(self):
        bindings={k:'a'*64 for k in g.BINDING_KEYS};review=dict(decision='PASS_FOR_ENGINEERING_PROFILE5',review_complete=True,bindings=bindings,resources=RESOURCES)
        g.validate(review,bindings)
        for key in g.BINDING_KEYS:
            bad=dict(bindings);bad[key]='b'*64
            with self.assertRaises(ValueError):g.validate(review,bad)
        review['decision']='PASS_FOR_ENGINEERING_PILOT'
        with self.assertRaises(ValueError):g.validate(review,bindings)

    def test_new_profile_ledger_selected_without_touching_old_location(self):
        (self.root/'job_id.txt').write_text('42')
        old=self.root/'payload/outputs/EXPOSURE_LEDGER.json';old.write_text('{"sentinel":"old_not_output"}')
        new=self.run/'EXPOSURE_LEDGER.json';new.write_text('{"in_flight":{"step":3},"confirmed_updates":[]}')
        result=c.exposure(self.root)
        self.assertEqual(result['raw']['in_flight']['step'],3)
        self.assertEqual(old.read_text(),'{"sentinel":"old_not_output"}')


if __name__=='__main__':unittest.main(verbosity=2)
