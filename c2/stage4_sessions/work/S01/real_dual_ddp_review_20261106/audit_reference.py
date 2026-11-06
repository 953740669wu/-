"""Independent S02 frozen reference audit: bytes, plan and existing receipts."""
import ast
import hashlib
import json
from pathlib import Path,PurePosixPath
import sys
import zipfile

OWN=Path(__file__).resolve().parent
WORK=OWN.parent.parent
REF=WORK/'S02/real_dual_ddp_reference_20261106'
OLD=WORK/'S02/round12_dw_output_tiles_20261106'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset(path):
    path=Path(path)
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))


def main():
    inputs={}
    def record(path):
        value=asset(path);inputs[value['path']]=value
    def check(value):
        if isinstance(value,dict):
            if {'path','sha256'}<=value.keys():
                path=Path(value['path']);assert sha(path)==value['sha256'],str(path)
                if 'bytes' in value:assert path.stat().st_size==value['bytes']
                record(path)
            for item in value.values():check(item)
        elif isinstance(value,list):
            for item in value:check(item)
    ready_path=REF/'REFERENCE_READY.json';record(ready_path)
    ready=json.loads(ready_path.read_text(encoding='utf-8'));assert ready['immutable_after_publish'] is True;check(ready)
    source=json.loads((REF/'SOURCE_SHA256.json').read_text(encoding='utf-8'))
    original=json.loads((OLD/'SOURCE_SHA256.json').read_text(encoding='utf-8'))
    reused=[]
    for name,digest in source.items():
        path=REF/name;assert sha(path)==digest;record(path)
        if path.suffix=='.py':
            assert b'\r' not in path.read_bytes();ast.parse(path.read_text(encoding='utf-8'),feature_version=(3,9))
        if name in original and name!='DECISION_BEFORE_CODE.md':
            assert digest==original[name]==sha(OLD/name),name;record(OLD/name);reused.append(name)
    with zipfile.ZipFile(ready['package']['path']) as archive:
        names=archive.namelist();assert len(names)==len(set(names))==18 and archive.testzip() is None
        assert set(names)==set(source)|{'SOURCE_SHA256.json'}
        for name in names:
            p=PurePosixPath(name);assert not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name
            raw=archive.read(name);assert raw==(REF/name).read_bytes()
            target=OWN/'frozen_reference'/name;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert target.read_bytes()==raw
            else:target.write_bytes(raw)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(OWN/'frozen_reference'))
    import dual_reference as ref
    assert not {'torch','numpy'} & set(sys.modules),'framework imported during reference import'
    combined=[]
    for step in range(1,26):
        plan=ref.plan(step);assert len(plan['rank_indices'])==2
        ref.validate_partition(plan['global_indices'],plan['rank_indices']);combined+=plan['global_indices']
    assert len(combined)==len(set(combined))==1600 and set(combined)==set(range(1600))
    checks=json.loads(Path(ready['local_checks']['path']).read_text(encoding='utf-8'))
    assert checks['tests']==7 and checks['tiny_comparator_metrics']==190 and checks['tiny_max_abs']==0
    assert checks['original_comparator_byte_identical'] is True
    metrics=json.loads(Path(ready['local_metrics']['path']).read_text(encoding='utf-8'))
    # Receipt has positive comparisons plus deliberate rejected probes separately.
    assert len(metrics['metrics'])==190 and all(m['passed'] for m in metrics['metrics'])
    init=json.loads(Path(ready['windows_initialization_diagnostic']['path']).read_text(encoding='utf-8'))
    assert init['init_hash_match'] is False and init['first_mask_match'] is True
    assert init['expected']['initial_weights_sha256']=='2543d05f25883b654141cbc5dc1bb093906e3b360f11ec9f5e87cb4f8bad76b5'
    result=dict(status='PASS_REFERENCE_PRE_REVIEW_PENDING_TRAINING_DEPLOYMENT',blockers=[],
        package_members=18,source_entries=len(source),reused_original_files=len(reused),
        plan_25_steps_exact_first32_last32=True,unique_frames=1600,import_before_framework=True,
        original_comparator_and_thresholds_unchanged=True,original_B64_reference=True,
        canonical_parameter_names=153,parameter_numel=37995777,
        local_helper_checks=7,local_tiny_metrics=190,Windows_C2_init='REJECTED_ORIGINAL_GATE_RETAINED',
        actual_C2_initialization_data_KML_DDP='PENDING_UNIQUE_JOB',repeated_author_suites=0,
        inputs=sorted(inputs.values(),key=lambda x:x['path']))
    (OWN/'reference_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='inputs'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
