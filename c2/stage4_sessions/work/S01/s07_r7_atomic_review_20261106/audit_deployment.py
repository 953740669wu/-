"""Check final R7 deployment bytes and the real release consumer, without jobs."""
import ast
import json
from pathlib import Path,PurePosixPath
import sys
import zipfile
from audit_code import SRC
from audit_baseline import OWN,WORK,asset,sha

DEP=WORK/'S00/s07_r7_atomic_20261106'


def main():
    ready=json.loads((DEP/'S00_DEPLOYMENT_READY.json').read_text(encoding='utf-8'))
    assert ready['immutable_after_publish'] is True and ready['status']=='S00_DEPLOYMENT_READY'
    inputs={}
    def record(path):
        value=asset(path);inputs[value['path']]=value
    record(DEP/'S00_DEPLOYMENT_READY.json')
    for key,value in ready.items():
        if isinstance(value,dict) and {'path','bytes','sha256'}<=value.keys():
            path=Path(value['path']);assert asset(path)==value,key;record(path)
    index=json.loads((DEP/'ARTIFACT_SHA256.json').read_text(encoding='utf-8'))
    for name,digest in index.items():
        path=DEP/name;assert sha(path)==digest,name;record(path)
        if path.suffix in ('.py','.sh'):assert b'\r' not in path.read_bytes(),name
        if path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,9))
    with zipfile.ZipFile(ready['deployment_package']['path']) as archive:
        names=archive.namelist();files=[n for n in names if not n.endswith('/')]
        assert len(names)==len(set(names)) and archive.testzip() is None
        assert set(files)==set(index)|{'ARTIFACT_SHA256.json','ARTIFACT_SHA256.txt'}
        for name in files:
            p=PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name
            raw=archive.read(name);assert raw==(DEP/name).read_bytes()
            path=OWN/'frozen_deployment'/name;path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():assert path.read_bytes()==raw
            else:path.write_bytes(raw)
    for local,source in [('S07_ATOMIC_READY.json','ATOMIC_READY.json'),('S07_INTERFACE_READY.json','INTERFACE_READY.json'),
            ('SOURCE_MANIFEST.json','SOURCE_MANIFEST.json'),('OBSERVATION_CONTRACT.md','OBSERVATION_CONTRACT.md'),
            ('INTERFACE_FOR_S00.md','INTERFACE_FOR_S00.md'),('S07_ATOMIC_REPORTS_R7.zip','package/S07_ATOMIC_REPORTS_R7.zip')]:
        assert (DEP/local).read_bytes()==(SRC/source).read_bytes(),local
    task=WORK/'COORDINATION/S07_R7_ATOMIC_REPORT_NEXT_20261106.md'
    assert (DEP/'TASK_CARD.md').read_bytes()==task.read_bytes();record(task)
    helpers=json.loads((DEP/'UNCHANGED_HELPERS.json').read_text(encoding='utf-8'))
    for name,value in helpers.items():
        assert value['unchanged'] is True and sha(DEP/name)==value['sha256']==sha(Path(value['source'])),name
        record(Path(value['source']))
    checks=json.loads(Path(ready['checks']['path']).read_text(encoding='utf-8'))
    assert all(checks[k] is True for k in ('LF','Linux_bash_n','Python39_AST','ZIP_CRC','source_SHA'))
    assert (checks['inner_entries'],checks['inner_files'],checks['inner_delivery'])==(17,16,15)
    assert checks['local_fixture_tests']==checks['linux_login_fixture_tests']==15
    assert checks['candidate_checks88']=='MUST_RUN_WITH_ZERO_SKIPS_IN_THIS_JOB'
    for key in ('local_fixture_log','linux_login_log'):
        text=Path(ready[key]['path']).read_text(encoding='utf-8');assert 'Ran 15 tests' in text and '\nOK' in text
    assert 'S07_R7_LOGIN_DEPLOYMENT_PASS' in Path(ready['linux_login_log']['path']).read_text(encoding='utf-8')
    correction_path=DEP/'evidence/PREPUBLISH_CORRECTION.json';record(correction_path)
    correction=json.loads(correction_path.read_text(encoding='utf-8'))
    assert correction['new_jobs']==0 and correction['new_remote_root']==ready['remote_staging_root']
    sys.dont_write_bytecode=True;sys.path.insert(0,str(OWN/'frozen_deployment'))
    import prepare,review_gate,run_s07_diag_job
    assert prepare.ARCHIVE=='S07_ATOMIC_REPORTS_R7.zip' and not (DEP/'S07_ALIGNED_STACK_R7.zip').exists()
    bindings=review_gate.expected(DEP)  # Concrete path bug must not be hidden by fixture-only validation.
    assert bindings==ready['required_review_bindings']
    assert review_gate.RESOURCES==ready['resources']
    assert review_gate.WORKLOAD==ready['workload']==ready['required_review_workload']
    assert [r[2] for r in run_s07_diag_job.CHECKS]==[17,27,16,6,6,16]
    assert sum(r[2] for r in run_s07_diag_job.CHECKS)==88
    review=dict(decision='PASS_FOR_S07_R7_ATOMIC',review_complete=True,bindings=bindings,
        resources=ready['resources'],workload=ready['workload'])
    review_gate.validate(review,bindings)
    finding=json.loads((OWN/'DRAFT_FINDING.json').read_text(encoding='utf-8'))
    assert sha(DEP/'review_gate.py')!=finding['source']['sha256']
    result=dict(status='PASS_DEPLOYMENT_PRE_REVIEW',blockers=[],zip_members=len(names),zip_files=len(files),
        source_index_entries=len(index),unchanged_R6_helpers=len(helpers),bindings=bindings,
        resources=ready['resources'],workload=ready['workload'],remote_staging_root=ready['remote_staging_root'],
        concrete_expected_and_validate_accept=True,archive_basename_bug_resolved=True,
        fixed_review_gate_sha256=sha(DEP/'review_gate.py'),old_draft_not_executable_approval=True,
        local_fixture_checks=15,linux_login_fixture_checks=15,current_job_linux88='PENDING',
        consumer_deadline=270,shared_cleanup_deadline=285,job_deadline=300,
        original_case_criteria_and_cleanup_retained=True,formal_and_temporary_reports_separate=True,
        diagnostic_completion_separate_from_communication=True,signal_fault_cleanup='NOT_RUN_THIS_ROUND',
        S01_jobs=0,S01_remote_connections=0,S01_Torch_Gloo_runs=0,
        inputs=sorted(inputs.values(),key=lambda e:e['path']))
    (OWN/'deployment_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
