"""Read-only S01 check of the frozen deployment and its release consumer."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile
from audit_code import asset, sha, OWN, WORK, SRC

DEP = WORK/'S00/round12_dw_ab_20261106'


def main():
    ready = json.loads((DEP/'S00_DEPLOYMENT_READY.json').read_text())
    inputs = {'deployment_ready': asset(DEP/'S00_DEPLOYMENT_READY.json')}
    for key, value in ready.items():
        if isinstance(value, dict) and {'path','bytes','sha256'} <= value.keys():
            assert asset(Path(value['path'])) == value, key
            inputs[key] = asset(Path(value['path']))
    index = json.loads((DEP/'ARTIFACT_SHA256.json').read_text())
    for name,digest in index.items():
        path=DEP/name
        assert sha(path)==digest, name
        inputs['deployment:'+name]=asset(path)
        if name.endswith(('.py','.sh')):
            assert b'\r' not in path.read_bytes(), name
        if name.endswith('.py'):
            ast.parse(path.read_text(),feature_version=(3,9))
    with zipfile.ZipFile(ready['deployment_package']['path']) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names)) and archive.testzip() is None
        files=[n for n in names if not n.endswith('/')]
        assert set(files)==set(index)|{'ARTIFACT_SHA256.json','ARTIFACT_SHA256.txt'}
        for name in files:
            p=PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
            raw=archive.read(name)
            assert raw==(DEP/name).read_bytes(), name
            target=OWN/'frozen_deployment'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==raw
            else:target.write_bytes(raw)
    assert (DEP/'S02_R12_READY.json').read_bytes()==(SRC/'R12_READY.json').read_bytes()
    assert (DEP/'S02_SOURCE_SHA256.json').read_bytes()==(SRC/'SOURCE_SHA256.json').read_bytes()
    for name in ('R12_CONTRACT.json','REFERENCE_FIRST5.json','REFERENCE_EPOCH25.json'):
        assert (DEP/name).read_bytes()==(SRC/name).read_bytes()
    task=WORK/'COORDINATION/R12_DW_AB_EXECUTION_NEXT_20261106.md'
    assert (DEP/'TASK_CARD.md').read_bytes()==task.read_bytes()
    inputs['task_card_original']=asset(task)
    helpers=json.loads((DEP/'UNCHANGED_HELPERS.json').read_text())
    for name,record in helpers.items():
        assert record['unchanged'] is True and sha(DEP/name)==record['sha256']==sha(Path(record['source'])), name
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(OWN/'frozen_deployment'))
    import review_gate
    bindings=review_gate.expected(DEP)
    assert bindings==ready['required_review_bindings']
    assert review_gate.RESOURCES==ready['resources']
    assert review_gate.WORKLOAD==ready['workload']==ready['required_review_workload']
    proposed=dict(decision='PASS_FOR_ENGINEERING_R12_AB',review_complete=True,bindings=bindings,
                  resources=ready['resources'],workload=ready['workload'])
    review_gate.validate(proposed,bindings)
    checks=json.loads(Path(ready['checks']['path']).read_text())
    assert all(checks[k] is True for k in ('LF','Linux_bash_n','Python39_AST','ZIP_CRC_and_source_manifest'))
    assert checks['fixed_source_files']==36 and checks['fixed_units']==16
    assert checks['local_fixture_tests']==checks['linux_login_fixture_tests']==9
    log=Path(ready['linux_login_log']['path']).read_text()
    assert all(x in log for x in ('R12_LOGIN_DEPLOYMENT_PASS','ENGINEERING_METADATA_HASH_GATE_PASS','OLD_INPUT_IDENTITIES_PASS BEFORE 9','Ran 9 tests','FIXED16_CURRENT_SOURCE_SHA_PASS'))
    result=dict(status='PASS_DEPLOYMENT_PRE_REVIEW',zip_members=len(names),zip_files=len(files),
        source_index_entries=len(index),unchanged_helpers=len(helpers),
        release_bindings=bindings,resources=ready['resources'],workload=ready['workload'],
        exact_review_consumer_accepts=True,nonoptimized_assertion_chain=True,
        shared_absolute_execution_seconds=840,cleanup_seconds=30,closing_seconds=30,
        local_fixture_checks=9,linux_login_fixture_checks=9,fixed_units=16,fixed_file_receipts=36,
        no_S01_remote_or_model_execution=True,signal_fault_cleanup='NOT_RUN',blockers=[],inputs=inputs)
    (OWN/'deployment_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
