"""Read-only closeout provenance/field audit. Standard library only; no experiments."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickletools
import re
import zipfile

OWN = Path(__file__).resolve().parent
WORK = OWN.parent.parent
SRC = WORK / 'S07/real_dual_ddp_evidence_closeout_r1_20261106'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def asset(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def select(value, selector):
    if selector == '$':
        return value
    assert selector.startswith('$.')
    for part in selector[2:].split('.'):
        match = re.fullmatch(r'([^\[]+)(?:\[([^\]]+)\])?', part)
        assert match, selector
        value = value[match[1]]
        if match[2] is not None:
            value = value[int(match[2])] if match[2].isdigit() else next(row for row in value if row['code'] == match[2])
    return value


def main():
    verified, field_checks = {}, []

    def verify(value):
        if isinstance(value, dict):
            if {'path', 'sha256'} <= value.keys() and value['sha256'] is not None:
                actual = asset(value['path'])
                assert actual['sha256'] == value['sha256'], value['path']
                if 'bytes' in value:
                    assert actual['bytes'] == value['bytes'], value['path']
                verified[actual['path']] = actual
                if {'field', 'original_value'} <= value.keys():
                    path, field = Path(value['path']), value['field']
                    # These original Windows subprocess logs use CP936; JSON/source use UTF-8.
                    encoding = 'cp936' if path.suffix == '.log' else 'utf-8-sig'
                    text = path.read_text(encoding=encoding, errors='replace')
                    if field.startswith('original source lines '):
                        expected = value['original_value']
                        actual_value = dict(start_line=expected['start_line'], end_line=expected['end_line'],
                            text='\n'.join(text.splitlines()[expected['start_line']-1:expected['end_line']]))
                    elif field in ('entire log', 'entire existing log'):
                        actual_value = text
                    elif field == 'top-level recorded field names':
                        actual_value = list(json.loads(text))
                    elif field.startswith('$.{'):
                        source = json.loads(text)
                        actual_value = {name.split('.')[-1]: select(source, '$.'+name) for name in field[3:-1].split(',')}
                    else:
                        actual_value = select(json.loads(text), field)
                    assert actual_value == value['original_value'], (str(path), field)
                    field_checks.append(dict(path=str(path), field=field, matches=True))
            for child in value.values():
                verify(child)
        elif isinstance(value, list):
            for child in value:
                verify(child)

    ready_path = SRC / 'EVIDENCE_CLOSEOUT_READY.json'
    ready = read(ready_path)
    verified[str(ready_path)] = asset(ready_path)
    verify(ready)
    closeout = read(SRC / 'EVIDENCE_CLOSEOUT.json')
    inputs = read(SRC / 'INPUT_MANIFEST.json')
    recheck = read(SRC / 'SOURCE_RECHECK.json')
    for item in (closeout, inputs, recheck):
        verify(item)
    assert len(inputs['files']) == recheck['original_files_rechecked'] == ready['original_files_verified'] == 56
    assert {row['path']: row['sha256'] for row in inputs['files']} == {row['path']: row['sha256'] for row in recheck['files']}
    assert all(row['unchanged'] is True for row in recheck['files'])
    cases = closeout['cases']
    assert len(cases) == 15
    counts = dict(Counter(row['classification'] for row in cases))
    assert counts == closeout['classification_counts'] == ready['classification_counts'] == dict(SUPPORTED=5, UNSUPPORTED=4, NOT_RECORDED=6)
    assert {row['review_gap'] for row in cases} == {row['code'] for row in read(WORK / 'S01/real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_REVIEW.json')['insufficient_evidence']}
    process_rows = closeout['process_binding_table']
    assert [(r['popen_pid'], r['compute_pid']) for r in process_rows] == [(111828,124816),(121848,117608),(123160,None),(116596,118980),(111740,123980)]
    assert all(r['os_parent_child_relationship'] == 'UNKNOWN' for r in process_rows)
    for row in closeout['per_stage_recorded_timing']:
        assert row['actual_compute_descendant_exit_within15s'] == 'UNKNOWN'
        assert row['derived_end_time_used_as_original_event'] is False
    assert ready['historical_gaps_recovered'] is False and ready['gaps_finalized'] is True
    assert ready['historical_compute_and_descendant_15s_cleanup'] == closeout['historical_compute_and_descendant_15s_cleanup'] == 'UNKNOWN_NOT_PROVEN'
    assert ready['execution_authorized'] is False and closeout['training_pass'] is False

    search = read(SRC / 'evidence/TARGETED_SEARCH.json')
    assert search['passes'] == 1 and search['text_files_searched'] == len(search['files']) == 40
    pattern = re.compile(search['pattern'], re.IGNORECASE)
    for row in search['files']:
        path = Path(row['path'])
        assert path.is_relative_to(Path(search['scope']))
        lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        assert len(lines) == row['line_count']
        expected = [dict(line=i, text=line) for i, line in enumerate(lines, 1) if pattern.search(line)]
        assert expected == row['matches'], str(path)

    raw = read(SRC / 'evidence/RAW_METADATA_INSPECTION.json')
    assert len(raw['files']) == 2 and raw['archive_tensor_payloads_read'] == 0
    for row in raw['files']:
        verify(row)
        with zipfile.ZipFile(row['path']) as archive:
            data = archive.read(row['metadata_member'])
        assert len(data) == row['metadata_bytes'] and hashlib.sha256(data).hexdigest() == row['metadata_sha256']
        literals = [(op.name, arg, pos) for op, arg, pos in pickletools.genops(data) if isinstance(arg, str)]
        for item in row['observed_literal_keys']:
            assert (item['opcode'], item['literal'], item['position']) in literals
        assert not set(row['absent_literal_keys']) & {arg for _, arg, _ in literals}
    sums_count = 0
    for line in (SRC / 'SHA256SUMS.txt').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert asset(SRC / name)['sha256'] == digest, name
        verified[str(SRC / name)] = asset(SRC / name)
        sums_count += 1
    scope = read(SRC / 'ARCHIVE_SCOPE.json')
    candidates = [Path(p) for p in scope['git_candidate_paths']]
    assert len(candidates) == len(set(candidates)) == 13
    for path in candidates:
        assert path.is_file()
        assert path.is_relative_to(SRC) or path in (SRC.parent / 'SESSION_STATUS.md', SRC.parent / 'ROUND_DELTA.md')
        assert path.suffix.lower() not in ('.pt', '.zip', '.npz', '.pth')
    result = dict(status='PASS_RECORD_CLOSEOUT_WITH_UNRECOVERED_LIMITS',
                  observed_utc=datetime.now(timezone.utc).isoformat(), ready=asset(ready_path),
                  original_source_files=56, verified_unique_files=len(verified),
                  original_field_checks=len(field_checks), field_checks=field_checks,
                  classification_counts=counts, case_results=[dict(code=c['code'], review_gap=c['review_gap'],
                      classification=c['classification'], conclusion=c['conclusion'], classification_accepted=True) for c in cases],
                  process_identity_table=process_rows,
                  targeted_search_files=40, targeted_search_lines_and_matches_verified=True,
                  original_log_decoding='CP936 (byte SHA also verified); JSON/source UTF-8',
                  raw_pickle_metadata_archives_verified=2, tensor_deserializations=0,
                  sha256sums_entries=sums_count, S07_new_archive_files=11, S07_mutable_status_paths=2,
                  historical_gap_recovery=False, limitations_finalized=True,
                  historical_cleanup_pass=False, numerical_pass=False, execution_authorized=False,
                  inputs=sorted(verified.values(), key=lambda row: row['path']))
    (OWN / 'CLOSEOUT_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','field_checks','process_identity_table','case_results')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
