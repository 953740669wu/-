"""S01 read-only R6 package/AST/receipt checks; no Torch, Gloo or test rerun."""
import ast
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

OWN=Path(__file__).resolve().parent
WORK=OWN.parent.parent
SRC=WORK/'S07/round6_aligned_stack_20261105'
OLD=WORK/'S07/round4_readiness_20261105'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset(path):
    path=Path(path)
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))


def main():
    inputs={}
    def record(path):
        entry=asset(path);inputs[entry['path']]=entry
    manifest=json.loads((SRC/'SOURCE_MANIFEST.json').read_text())
    package=SRC/'package/S07_ALIGNED_STACK_R6.zip'
    assert package.stat().st_size==43727 and sha(package)=='32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1'
    record(package);record(SRC/'SOURCE_MANIFEST.json')
    entries=manifest['delivery_files']
    assert len(entries)==14
    for entry in entries:
        path=SRC/entry['path'];actual=asset(path)
        assert all(actual[k]==entry[k] for k in ('bytes','sha256')),entry['path']
        record(path)
        if path.suffix=='.py':
            assert b'\r' not in path.read_bytes()
            ast.parse(path.read_text(),feature_version=(3,9))
    with zipfile.ZipFile(package) as archive:
        names=archive.namelist();files=[n for n in names if not n.endswith('/')]
        assert len(names)==len(set(names))==16 and len(files)==15
        assert set(files)=={e['path'] for e in entries}|{'SOURCE_MANIFEST.json'}
        assert archive.testzip() is None
        for name in files:
            p=PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
            raw=archive.read(name);assert raw==(SRC/name).read_bytes(),name
            target=OWN/'frozen_code'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==raw
            else:target.write_bytes(raw)
    (OWN/'frozen_code/evidence').mkdir(exist_ok=True)
    # Acceptance and all four original test groups remain exactly the same.
    unchanged=['candidate/cpu36_contract.py','candidate/run_checks.py',
        'tests/test_probe.py','tests/test_diagnostics.py','tests/test_readiness.py','tests/test_job_identity.py','allocation.template.json']
    for name in unchanged:
        assert (SRC/name).read_bytes()==(OLD/name).read_bytes(),name
        record(OLD/name)
    baseline=OLD/'candidate/comm_probe.py';record(baseline)
    assert sha(baseline)==manifest['baseline_probe_sha256']
    original=ast.parse(baseline.read_text());current=ast.parse((SRC/'candidate/comm_probe.py').read_text())
    old_functions={n.name:ast.dump(n) for n in original.body if isinstance(n,ast.FunctionDef)}
    new_functions={n.name:ast.dump(n) for n in current.body if isinstance(n,ast.FunctionDef)}
    changed=[name for name in old_functions if old_functions[name]!=new_functions[name]]
    assert set(changed)=={'supervise','worker','run'}
    actual=''.join(difflib.unified_diff(baseline.read_text().splitlines(True),
        (SRC/'candidate/comm_probe.py').read_text().splitlines(True),fromfile='a/candidate/comm_probe.py',tofile='b/candidate/comm_probe.py'))
    assert actual==(SRC/'minimal.diff').read_text()
    counts={}
    for name,expected in [('stack_observer',27),('readiness',16),('diagnostics',6),('job_identity',6),('probe',16)]:
        tree=ast.parse((SRC/f'tests/test_{name}.py').read_text())
        count=sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
        assert count==expected,(name,count);counts[name]=count
    evidence=json.loads((SRC/'EVIDENCE_MANIFEST.json').read_text());record(SRC/'EVIDENCE_MANIFEST.json')
    for entry in evidence['files']:
        path=SRC/entry['path'];assert sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes'],str(path)
        if entry['path'].startswith('evidence/') and not entry['path'].startswith('evidence/before/'):
            record(path)
    checks=json.loads((SRC/'evidence/local_checks.json').read_text())
    assert (checks['total'],checks['passed'],checks['skipped'])==(71,70,1)
    for check in checks['checks']:
        assert check['exit_code']==0
        text=(SRC/check['log']).read_text()
        assert 'Ran '+str(check['methods'])+' tests' in text and '\nOK' in text
    task=WORK/'COORDINATION/AFTER_R12_NO_GAIN_S07_RESUME_20261106.md';record(task)
    result=dict(status='PASS_CODE_PRE_REVIEW_PENDING_DEPLOYMENT',blockers=[],package_members=16,
        actual_payload_files=15,delivery_files=14,unchanged_files=len(unchanged),
        changed_original_functions=changed,minimal_diff_exact=True,Python39_AST=True,LF=True,
        test_groups=counts,total_tests=71,author_local_passed=70,author_local_skipped=1,
        Linux_current_job_requirement='71 passed, zero skipped; included in consumer shared budget',
        observer_scope='watchdog only; original deadline minus5s; two ranks share target+2s; no parent helper wait',
        original_case_order=manifest['case_order'],pg_timeout_seconds=5,case_seconds=30,
        diagnostic_completion_is_separate_from_communication=True,
        S01_execution=dict(new_jobs=0,remote_connections=0,Torch_or_Gloo_runs=0,repeated_author_suites=0),
        inputs=sorted(inputs.values(),key=lambda e:e['path']))
    (OWN/'code_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
