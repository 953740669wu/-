"""Final source/receipt checks and an index of this new S02 directory only."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


manifest=json.loads((ROOT/'package/PACKAGE_MANIFEST.json').read_text())
archive=ROOT/'package'/manifest['archive']
assert sha(archive)==manifest['archive_sha256'] and archive.stat().st_size==manifest['archive_bytes']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))==24
    for name,item in manifest['entries'].items():
        assert sha(ROOT/name)==item['sha256']==hashlib.sha256(z.read(name)).hexdigest()
        assert (ROOT/name).stat().st_size==item['bytes']
sources=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert len(sources)==23
assert all(sha(ROOT/name)==value for name,value in sources.items())
for path in ROOT.rglob('*.py'):ast.parse(path.read_text('utf-8'),feature_version=(3,9))
before=json.loads((ROOT/'evidence/inputs_before.json').read_text());protected=0
for name,item in before.items():
    if Path(name).name in ('SESSION_STATUS.md','ROUND_DELTA.md'):continue
    path=Path(name)
    assert dict(bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns,sha256=sha(path))==item,name
    protected+=1
for name,count in [('native_tests_after.txt',3),('protocol_tests.txt',11)]:
    text=(ROOT/'evidence'/name).read_text('utf-8')
    assert f'Ran {count} tests' in text and text.rstrip().endswith('OK')
assessment=json.loads((ROOT/'evidence/memory3_assessment.json').read_text())
assert all([x['kml_calls'] for x in p['measurements']]==[149,197] for p in assessment['pairs'])
assert all(str(x['job'])=='2039061' for p in assessment['pairs'] for x in p['measurements'])
assert assessment['strict_metrics']==1063 and assessment['old_different_host']['include_in_new_stats'] is False
identity=json.loads((ROOT/'evidence/saved_result_identity_review.json').read_text())
assert len(identity['files'])==7 and sum(x['checkpoints'] for x in identity['files'])==49
local=json.loads((ROOT/'evidence/local_validation.json').read_text())
assert len(local['shell_checks'])==5
assert all(item['git_bash_n_exit']==0 and item['cr_bytes']==0 for item in local['shell_checks'])
assert len(local['final_entry_rejections'])==2
for item in local['final_entry_rejections']:
    data=json.loads((ROOT/item['result']).read_text())
    assert item['exit']==2 and data['status']=='ERROR_RUNTIME_OR_STATE'
    assert data['source_manifest_sha256']==sha(ROOT/'SOURCE_SHA256.json')
    assert all(sha(ROOT/name)==value for name,value in data['source_sha256'].items())
for name in ('SESSION_STATUS.md','ROUND_DELTA.md'):
    assert 'R7' in (ROOT.parent/name).read_text('utf-8')
    assert sha(ROOT/'evidence'/('before_'+name))==before[str((ROOT.parent/name).resolve())]['sha256']
assert len((ROOT.parent/'ROUND_DELTA.md').read_text('utf-8').splitlines())==6
assert len((ROOT.parent/'SESSION_STATUS.md').read_text('utf-8').splitlines())<=40
assert manifest['archive_sha256'] in (ROOT/'REPORT.md').read_text('utf-8')
record=dict(status='LOCAL_READY_FOR_COORDINATION_REVIEW_NO_NEW_C2',archive_sha256=sha(archive),
    archive_bytes=archive.stat().st_size,archive_files=24,source_entries=23,frozen_r6_files=13,
    protected_prior_files_unchanged=protected,small_native_torch_tests=3,stdlib_protocol_tests=11,
    actual_old_one_step_pass_rejected=True,saved_result_files_reviewed=7,saved_cpu_checkpoints_reviewed=49,
    final_entry_receipts_match_current_source=True,full_model_runs=0,new_cluster_jobs=0,
    new_sequence_numerical='NOT_RUN_ON_C2',new_training_memory_runs=0,hbm_runs=0,steady_state_claim=False,
    recommendation='RETAIN_EXPERIMENTAL_CANDIDATE_DO_NOT_INTEGRATE_YET',
    session_status_sha256=sha(ROOT.parent/'SESSION_STATUS.md'),round_delta_sha256=sha(ROOT.parent/'ROUND_DELTA.md'),
    substantive_local_code_blockers=[],next=['coordination package review','S00 separately arranged five-step C2 strict gate',
    'only after new five-step PASS, independent five-step memory arrangement'])
(ROOT/'evidence/final_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name!='ARTIFACT_SHA256.txt')
(ROOT/'ARTIFACT_SHA256.txt').write_text(''.join(sha(p)+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files),
                                       encoding='utf-8',newline='\n')
print(json.dumps(dict(record,indexed_artifacts=len(files)),indent=2))
