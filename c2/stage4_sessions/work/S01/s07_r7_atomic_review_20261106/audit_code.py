"""Verify the frozen R7 bytes, minimal AST change and existing fault evidence."""
import ast
import copy
import difflib
import json
from pathlib import Path,PurePosixPath
import zipfile
from audit_baseline import OWN,WORK,asset,sha

SRC=WORK/'S07/round7_atomic_reports_20261106'
OLD=WORK/'S07/round6_aligned_stack_20261105'


def main():
    inputs={}
    def record(path):
        item=asset(path);inputs[item['path']]=item
    def check_assets(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys():
                item=asset(Path(value['path']))
                assert all(item[k]==value[k] for k in ('bytes','sha256')),value['path']
                record(Path(value['path']))
            for child in value.values():check_assets(child)
        elif isinstance(value,list):
            for child in value:check_assets(child)
    ready_path=SRC/'ATOMIC_READY.json';record(ready_path)
    ready=json.loads(ready_path.read_text(encoding='utf-8'));assert ready['code_frozen'] is True
    check_assets(ready)
    manifest=json.loads((SRC/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    delivery=manifest['delivery_files'];assert len(delivery)==15
    for entry in delivery:
        path=SRC/entry['path'];value=asset(path)
        assert all(value[k]==entry[k] for k in ('bytes','sha256')),entry['path'];record(path)
        if path.suffix=='.py':
            assert b'\r' not in path.read_bytes();ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,9))
    with zipfile.ZipFile(ready['package']['path']) as archive:
        names=archive.namelist();files=[n for n in names if not n.endswith('/')]
        assert len(names)==len(set(names))==17 and len(files)==16 and archive.testzip() is None
        assert set(files)=={e['path'] for e in delivery}|{'SOURCE_MANIFEST.json'}
        for name in files:
            p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
            raw=archive.read(name);assert raw==(SRC/name).read_bytes()
            target=OWN/'frozen_code'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==raw
            else:target.write_bytes(raw)
    for entry in ready['unchanged_from_R6']:
        name=entry['relative_path'];assert (SRC/name).read_bytes()==(OLD/name).read_bytes(),name;record(OLD/name)
    baseline=OLD/'candidate/comm_probe.py';record(baseline)
    current=SRC/'candidate/comm_probe.py'
    diff=''.join(difflib.unified_diff(baseline.read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='R6/candidate/comm_probe.py',tofile='R7/candidate/comm_probe.py'))
    assert diff==(SRC/'minimal.diff').read_text(encoding='utf-8')
    tree=ast.parse(current.read_text(encoding='utf-8'));old_tree=ast.parse(baseline.read_text(encoding='utf-8'))
    added=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='write_rank_report'];assert len(added)==1
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='write_rank_report'];assert len(calls)==3
    reduced=copy.deepcopy(tree)
    reduced.body=[n for n in reduced.body if not (isinstance(n,ast.FunctionDef) and n.name=='write_rank_report') and not (isinstance(n,ast.Import) and [a.name for a in n.names]==['tempfile'])]
    class Restore(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id=='write_rank_report':node.func.id='write_json'
            return node
    assert ast.dump(Restore().visit(reduced))==ast.dump(old_tree),'change outside writer/import/three calls'
    # Check original receipts; do not rerun these standard-library suites.
    checks=json.loads((SRC/'evidence/local_checks.json').read_text(encoding='utf-8'))
    assert (checks['test_methods'],checks['passed'],checks['skipped'])==(88,87,1)
    counts={}
    for row in checks['groups']:
        path=SRC/'tests'/row['file'];tree=ast.parse(path.read_text(encoding='utf-8'))
        actual=sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
        assert actual==row['methods'] and row['returncode']==0
        counts[row['file']]=actual
        log=SRC/'evidence'/(path.stem+'.log');record(log)
        text=log.read_text(encoding='utf-8');assert 'Ran '+str(actual)+' tests' in text and '\nOK' in text
    assert sum(counts.values())==88 and counts['test_atomic_reports.py']==17
    evidence=json.loads((SRC/'EVIDENCE_MANIFEST.json').read_text(encoding='utf-8'));check_assets(evidence)
    reproduction=json.loads((SRC/'evidence/controlled_reproduction.json').read_text(encoding='utf-8'));assert len(reproduction['runs'])==6
    prior_sha=set()
    for row in reproduction['runs']:
        directory=SRC/row['evidence_directory'];target=directory/'rank0.json'
        assert row['owned_child_terminated_and_reaped'] is True
        for file in row['files']:
            path=directory/file['path'];value=asset(path)
            assert all(value[k]==file[k] for k in ('bytes','sha256'));record(path)
        if row['mode']=='old':
            assert row['target_preserved'] is False
            if row['phase']=='zero':assert target.read_bytes()==b''
            else:
                try:json.loads(target.read_text(encoding='utf-8'))
                except json.JSONDecodeError:pass
                else:raise AssertionError('old partial evidence unexpectedly valid')
        elif row['previous_report']:
            assert row['target_preserved'] is True and target.stat().st_size==133
            assert 'error' not in json.loads(target.read_text(encoding='utf-8'));prior_sha.add(sha(target))
            assert (directory/row['temporary_remnant']).is_file()
        else:assert not target.exists() and (directory/row['temporary_remnant']).is_file()
    assert len(prior_sha)==1
    result=dict(status='PASS_CODE_PRE_REVIEW_PENDING_DEPLOYMENT',blockers=[],package_members=17,
        actual_payload_files=16,delivery_files=15,unchanged_R6_assets=len(ready['unchanged_from_R6']),
        minimal_diff_exact=True,AST_only_writer_import_and_three_rank_calls=True,rank_updates=3,
        test_counts=counts,total_tests=88,author_local_passed=87,author_local_skipped=1,
        controlled_reproductions=6,old_empty_partial_reproduced=True,new_prior_checkpoint_preserved=True,
        no_prior_publication_remains_missing=True,reader_ready_case_deadline_cleanup_AST_unchanged=True,
        S01_execution=dict(new_jobs=0,remote_connections=0,Torch_Gloo_or_model_runs=0,repeated_author_suites=0),
        inputs=sorted(inputs.values(),key=lambda e:e['path']))
    (OWN/'code_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
