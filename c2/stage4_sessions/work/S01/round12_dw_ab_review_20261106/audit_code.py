"""S01 independent bytes/AST/reference audit; no framework import or execution."""
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

OWN = Path(__file__).resolve().parent
WORK = OWN.parent.parent
SRC = WORK / 'S02/round12_dw_output_tiles_20261106'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset(path):
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def main():
    ready = json.loads((SRC / 'R12_READY.json').read_text())
    inputs = {'ready': asset(SRC / 'R12_READY.json')}
    for key, value in ready.items():
        if isinstance(value, dict) and 'sha256' in value and 'path' in value:
            path = Path(value['path'])
            assert asset(path) == value, (key, 'readiness asset differs')
            inputs[key] = asset(path)
    source = json.loads((SRC / 'SOURCE_SHA256.json').read_text())
    for name, digest in source.items():
        assert sha(SRC / name) == digest, name
        inputs['source:' + name] = asset(SRC / name)
        if name.endswith(('.py', '.sh', '.env')):
            assert b'\r' not in (SRC / name).read_bytes(), ('not LF', name)
        if name.endswith('.py'):
            ast.parse((SRC / name).read_text(), feature_version=(3, 9))
    with zipfile.ZipFile(Path(ready['package']['path'])) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 27
        assert set(names) == set(source) | {'SOURCE_SHA256.json'}
        assert archive.testzip() is None
        for name in names:
            p = PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
            assert archive.read(name) == (SRC / name).read_bytes(), name
            target = OWN / 'frozen_code' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == archive.read(name)
            else:
                target.write_bytes(archive.read(name))
    # Only one new if statement in gemm; every pre-existing AST node is unchanged.
    base = ast.parse((SRC / 'baseline/kml_ops.py').read_text())
    cand = ast.parse((SRC / 'candidate/kml_ops.py').read_text())
    bg = next(n for n in base.body if isinstance(n, ast.FunctionDef) and n.name == 'gemm')
    cg = next(n for n in cand.body if isinstance(n, ast.FunctionDef) and n.name == 'gemm')
    assert len(cg.body) == len(bg.body) + 1
    indexes = []
    for index, node in enumerate(cg.body):
        reduced = copy.deepcopy(cand)
        function = next(n for n in reduced.body if isinstance(n, ast.FunctionDef) and n.name == 'gemm')
        del function.body[index]
        if ast.dump(base) == ast.dump(reduced):
            indexes.append(index)
    assert len(indexes) == 1 and isinstance(cg.body[indexes[0]], ast.If)
    actual_diff = ''.join(difflib.unified_diff(
        (SRC/'baseline/kml_ops.py').read_text().splitlines(True),
        (SRC/'candidate/kml_ops.py').read_text().splitlines(True),
        fromfile='frozen/baseline/kml_ops.py', tofile='candidate/kml_ops.py'))
    assert actual_diff == (SRC/'diff/CANDIDATE_ONLY.patch').read_text()
    protected = json.loads((SRC/'evidence/PROTECTED_INPUTS.json').read_text())
    for name in protected['copied_files']:
        assert source[name] == protected['r11_files'][name] == sha(Path(protected['r11_root'])/name), name
    for name in ('evidence/PROTECTED_INPUTS.json', 'evidence/runtime_contract_final.log'):
        inputs[name] = asset(SRC / name)
    epoch = json.loads((SRC/'REFERENCE_EPOCH25.json').read_text())
    original = Path(epoch['steps_asset']['path'])
    assert asset(original) == epoch['steps_asset']
    rows = [json.loads(line) for line in original.read_text().splitlines()]
    assert len(rows) == len(epoch['steps']) == 25
    seen = []
    first = json.loads((SRC/'REFERENCE_FIRST5.json').read_text())
    for index, (row, ref) in enumerate(zip(rows, epoch['steps']), 1):
        assert ref['step'] == row['step'] == index
        ids_sha = hashlib.sha256(json.dumps(row['frame_ids'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert ref['frame_ids_sha256'] == ids_sha and ref['frame_indices'] == row['frame_indices'] and ref['mask_sha256'] == row['mask_sha256']
        if index <= 5:
            assert all(ref[k] == first['steps'][index-1][k] for k in ('step', 'frame_indices', 'frame_ids_sha256', 'mask_sha256'))
        seen.extend(ref['frame_indices'])
    assert len(seen) == len(set(seen)) == 1600 and set(seen) == set(range(1600))
    inputs['original_epoch_steps'] = asset(original)
    numeric = json.loads((SRC/'evidence/native_screen.json').read_text())
    assert len(numeric['metrics']) == 30 and all(m['passed'] for m in numeric['metrics'])
    assert all(m['max_abs'] == m['l2_relative'] == 0 for m in numeric['metrics'])
    report = dict(status='PASS_CODE_PRE_REVIEW_PENDING_DEPLOYMENT', package_members=27,
        source_entries=len(source), reused_sources=len(protected['copied_files']), unique_added_gemm_if=True,
        all_other_AST_unchanged=True, sole_diff_exact=True, Python39_AST=True, LF=True,
        epoch_reference_exact_original25=True, unique_epoch_frames=1600,
        author_local_checks=9, author_local_metrics=30, repeated_model_or_fake_math_tests=0,
        actual_KML='NOT_RUN_BY_S01', full_model='NOT_RUN_BY_S01', new_jobs=0,
        ABI=dict(m=512,n=2048,k=13312,width=1024,columns=[0,1024],
            B_offsets_bytes=[0,4096],C_offsets_bytes=[0,4096],lda=512,ldb=2048,ldc=2048,
            A_last_float=13312*512-1,B_last_float=13312*2048-1,C_last_float=512*2048-1),
        stage_order=['target','strict','perf_baseline','perf_candidate'],
        counts=dict(baseline=[149,12,149,12,0],candidate=[149,12,161,0,24],
                    fields=['logical','target_logical','native','target_full','target_tiles']),
        blockers=[], inputs=inputs)
    (OWN/'code_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('inputs',)},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
