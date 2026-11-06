"""Independent frozen deployment bytes and exact S00 release-consumer audit."""
import ast
import difflib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile
from audit_code import OWN,WORK,SRC,sha,asset

DEP=WORK/'S00/s07_r6_resume_20261106'


def main():
    ready=json.loads((DEP/'S00_DEPLOYMENT_READY.json').read_text())
    assert ready['immutable_after_publish'] is True and ready['status']=='S00_DEPLOYMENT_READY'
    inputs={}
    def record(path):
        value=asset(path);inputs[value['path']]=value
    record(DEP/'S00_DEPLOYMENT_READY.json')
    for key,value in ready.items():
        if isinstance(value,dict) and {'path','bytes','sha256'}<=value.keys():
            path=Path(value['path']);assert asset(path)==value,key;record(path)
    index=json.loads((DEP/'ARTIFACT_SHA256.json').read_text())
    for name,digest in index.items():
        path=DEP/name;assert sha(path)==digest,name;record(path)
        if path.suffix in ('.py','.sh'):
            assert b'\r' not in path.read_bytes(),name
        if path.suffix=='.py':ast.parse(path.read_text(),feature_version=(3,9))
    with zipfile.ZipFile(ready['deployment_package']['path']) as archive:
        names=archive.namelist();files=[n for n in names if not n.endswith('/')]
        assert len(names)==len(set(names)) and archive.testzip() is None
        assert set(files)==set(index)|{'ARTIFACT_SHA256.json','ARTIFACT_SHA256.txt'}
        for name in files:
            p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
            raw=archive.read(name);assert raw==(DEP/name).read_bytes(),name
            path=OWN/'frozen_deployment'/name;path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():assert path.read_bytes()==raw
            else:path.write_bytes(raw)
    for name in ('SOURCE_MANIFEST.json','OBSERVATION_CONTRACT.md','INTERFACE_FOR_S00.md'):
        assert (DEP/name).read_bytes()==(SRC/name).read_bytes(),name
    assert (DEP/'S07_ALIGNED_STACK_R6.zip').read_bytes()==(SRC/'package/S07_ALIGNED_STACK_R6.zip').read_bytes()
    task=WORK/'COORDINATION/AFTER_R12_NO_GAIN_S07_RESUME_20261106.md'
    assert (DEP/'TASK_CARD.md').read_bytes()==task.read_bytes();record(task)
    helpers=json.loads((DEP/'UNCHANGED_HELPERS.json').read_text())
    for name,value in helpers.items():
        assert value['unchanged'] is True and sha(DEP/name)==value['sha256']==sha(Path(value['source'])),name
        record(Path(value['source']))
    provenance=json.loads((DEP/'OWNERSHIP_PROVENANCE.json').read_text())
    original=Path(provenance['source']);record(original)
    assert sha(original)==provenance['source_sha256'] and sha(DEP/'owned_processes.py')==provenance['current_sha256']
    diff=''.join(difflib.unified_diff(original.read_text().splitlines(True),(DEP/'owned_processes.py').read_text().splitlines(True),fromfile='R12/owned_processes.py',tofile='R6/owned_processes.py'))
    assert diff==(DEP/'OWNERSHIP_FROM_R12.diff').read_text()
    checks=json.loads(Path(ready['checks']['path']).read_text())
    assert all(checks[k] is True for k in ('LF','Linux_bash_n','Python39_AST','ZIP_CRC','source_SHA'))
    assert (checks['inner_entries'],checks['inner_files'],checks['inner_delivery'])==(16,15,14)
    assert checks['local_fixture_tests']==checks['linux_login_fixture_tests']==11
    assert checks['candidate_checks71']=='MUST_RUN_WITH_ZERO_SKIPS_IN_THIS_JOB'
    for key in ('local_fixture_log','linux_login_log'):
        log=Path(ready[key]['path']).read_text()
        assert 'Ran 11 tests' in log and '\nOK' in log
    assert 'S07_R6_LOGIN_DEPLOYMENT_PASS' in Path(ready['linux_login_log']['path']).read_text()
    sys.dont_write_bytecode=True;sys.path.insert(0,str(OWN/'frozen_deployment'))
    import review_gate
    bindings=review_gate.expected(DEP)
    assert bindings==ready['required_review_bindings']
    assert review_gate.RESOURCES==ready['resources']
    assert review_gate.WORKLOAD==ready['workload']==ready['required_review_workload']
    review=dict(decision='PASS_FOR_S07_R6_DIAGNOSTIC',review_complete=True,
        bindings=bindings,resources=ready['resources'],workload=ready['workload'])
    review_gate.validate(review,bindings)
    result=dict(status='PASS_DEPLOYMENT_PRE_REVIEW',blockers=[],zip_members=len(names),zip_files=len(files),
        source_index_entries=len(index),unchanged_helpers=len(helpers),ownership_diff_exact=True,
        bindings=bindings,resources=ready['resources'],workload=ready['workload'],
        exact_review_consumer_accepts=True,remote_staging_root=ready['remote_staging_root'],
        local_fixture_checks=11,linux_login_fixture_checks=11,actual_current_job_checks71='PENDING',
        absolute_consumer_deadline=270,shared_cleanup_deadline=285,job_deadline=300,
        diagnostic_completion_separate_from_communication=True,raw_empty_partial_residuals_preserved=True,
        actual_Torch_Gloo='NOT_RUN_BY_S01',signal_fault_cleanup='NOT_RUN_THIS_ROUND',
        inputs=sorted(inputs.values(),key=lambda e:e['path']))
    (OWN/'deployment_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
