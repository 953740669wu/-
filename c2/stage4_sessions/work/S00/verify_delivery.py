"""Check S00 delivery, source integrity, and hash every artifact; no execution of model code."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[3]
before = json.loads((WORK / 'evidence/source_before.json').read_text(encoding='utf-8'))
changed = []
for row in before['files']:
    path = ROOT / row['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
        changed.append(row['path'])
known = {row['path'] for row in before['files']}
added = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
         if p.is_file() and not p.is_relative_to(ROOT / 'c2/stage4_sessions/work')
         and not p.is_relative_to(ROOT / '.git')
         and p.relative_to(ROOT).as_posix() not in known]
external_review = json.loads((WORK / 'evidence/workspace_git_additions_20261105.json').read_text(encoding='utf-8'))
handoff_review = json.loads((WORK / 'evidence/workspace_handoff_additions_20261105.json').read_text(encoding='utf-8'))
external_review['reviewed_project_additions'].update(handoff_review['reviewed_project_additions'])
reviewed_additions = [name for name in added
    if name in external_review['reviewed_project_additions']
    and hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        == external_review['reviewed_project_additions'][name]['sha256']]
unexpected_additions = [name for name in added if name not in reviewed_additions]
documentation_review = json.loads((WORK / 'evidence/readme_handoff_review_20261105.json').read_text(encoding='utf-8'))
reviewed_changes = [name for name in changed
    if name in documentation_review['reviewed_original_changes']
    and hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        == documentation_review['reviewed_original_changes'][name]]
unreviewed_changes = [name for name in changed if name not in reviewed_changes]
integrity = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    original_file_count=len(before['files']), changed_or_missing=changed,
    original_files_byte_matched=len(before['files']) - len(changed),
    reviewed_documentation_changes=reviewed_changes, unreviewed_changes=unreviewed_changes,
    documentation_change_review='evidence/readme_handoff_review_20261105.json',
    added_outside_session_work=added, externally_reviewed_additions=reviewed_additions,
    unexpected_additions=unexpected_additions, git_metadata_excluded=True,
    external_additions_review='evidence/workspace_git_additions_20261105.json',
    status='PASS' if not unreviewed_changes and not unexpected_additions else 'FAIL',
    data_note='Remote manifest metadata and selected production source SHA verified; corpus payload integrity NOT_ESTABLISHED')
(WORK / 'evidence/source_integrity.json').write_text(json.dumps(integrity, indent=2) + '\n', encoding='utf-8')
assert integrity['status'] == 'PASS', integrity
python_paths = sorted(p for p in WORK.rglob('*.py') if not p.is_relative_to(WORK / 'tmp'))
for path in python_paths:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
embedded = []
for path in (WORK / 'candidate').glob('*.sh'):
    text = path.read_text(encoding='utf-8')
    assert b'\r' not in path.read_bytes(), path
    for index, source in enumerate(re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", text, re.S)):
        ast.parse(source, filename=str(path) + ':heredoc')
        embedded.append(str(path.relative_to(WORK)) + ':' + str(index))
for path in (WORK / 'execution_packages').iterdir():
    if path.suffix in ('.sh', '.env'):
        assert b'\r' not in path.read_bytes(), path
report = (WORK / 'REPORT.md').read_text(encoding='utf-8')
for section in range(1, 8):
    assert '## ' + str(section) + '. ' in report
assert 'REMOTE_VERIFIED / HISTORICAL_RECOMPUTED / NEW_CLUSTER_BENCHMARK_NOT_RUN' in report
for target in re.findall(r"(E:\\[^|\r\n`']+)", report):
    target = target.strip()
    # The all-artifact index is created at the end of this check.
    if target.endswith(('ARTIFACT_SHA256.txt', 'delivery_validation.json')):
        continue
    assert Path(target).exists(), target
validation = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='PASS_EVIDENCE_DELIVERY_PERFORMANCE_NOT_ACCEPTED', python_syntax_files=len(python_paths),
    embedded_python_syntax=embedded, original_source_integrity=integrity['status'],
    report_sections=7, remote_audit='VERIFIED_AS_SCOPED', remote_training_tests='NOT_RUN',
    detailed_evidence='USER_AUTHORIZED_AND_SAVED_WITH_LIMITED_SCOPE',
    bash_syntax='PASS_REMOTE_STDIN_BUILD_AND_ISOLATED_RUNNER',
    numerical_and_performance_acceptance='NOT_ESTABLISHED')
environment = json.loads((WORK / 'evidence/compute_environment_verified.json').read_text(encoding='utf-8'))
validation.update(compute_environment=environment['status'],
    compute_validation_job=environment['validation_job_id'],
    model_pilots='S01_JOB_2026356_FAILED_BEFORE_MODEL_STOPPED_NO_RETRY',
    s02_model_pilot='NOT_SUBMITTED_S01_GATE_NOT_PASSED',
    s02_affinity_fix='EXPLICIT_CPUS_AND_SAME_PROCESS_GUARD_LINUX_FIXTURE_PASS',
    pilot_package_validation='evidence/execution_package_validation.json',
    s02_training_memory='NOT_READY')
restart = json.loads((WORK / 'evidence/s01_lf_restart_2026450/review.json').read_text(encoding='utf-8'))
assert restart['status'] == 'PASS_COMPLETE_EVIDENCE_DELIVERY_S01_RUN_FAILED'
validation.update(remote_training_tests='ONE_REAL_MODEL_ROUND_EXECUTED_REJECTED_CPU_AFFINITY',
    model_pilots='S01_JOB_2026450_CHILD_EXIT0_JOB_EXIT1_STOPPED',
    latest_model_job=restart['job_id'],
    latest_model_review='evidence/s01_lf_restart_2026450/review.json',
    full_model_evidence_files=restart['full_evidence_file_count'],
    old_2026356_evidence_unchanged=restart['old_2026356_evidence_unchanged'],
    s02_model_pilot='NOT_SUBMITTED_EXPLICIT_USER_HOLD',
    s02_training_memory='NOT_RUN_NUMERICAL_GATE_AND_USER_HOLD')
cpu36 = json.loads((WORK / 'execution_packages/NEXT_CPU36_EXECUTION.json').read_text(encoding='utf-8'))
assert cpu36['selected_physical_cores_per_domain'] == cpu36['s02_checker_threads'] == 36
for relative, digest in cpu36['historical_files_sha256'].items():
    assert hashlib.sha256((WORK / relative).read_bytes()).hexdigest() == digest, relative
packages = json.loads((WORK / 'execution_packages/PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
assert all(packages[task]['execution_allowed'] is False for task in ('S01', 'S02'))
validation.update(future_compute_cores_per_domain=36,
    cpu36_package=cpu36['cpu36_package_status'], old_packages_execution_allowed=False,
    cpu36_registration='RECORDED_WAITING_S01_ACCEPTED_REVISION_NO_NEW_JOB')
diagnostic = json.loads((WORK / 'evidence/cpu36_r6_2026725/review.json').read_text(encoding='utf-8'))
assert diagnostic['status'] == 'PASS_FULL_DIAGNOSTIC_EVIDENCE_DELIVERY_ANALYSIS_PENDING'
assert diagnostic['job_exit_code'] == 0 and len(diagnostic['cases']) == 5
validation.update(cpu36_registration='R6_DIAGNOSTIC_COMPLETE_MODEL_REVISION_PENDING',
    cpu36_diagnostic_job=diagnostic['job_id'],
    cpu36_diagnostic_evidence_files=diagnostic['full_evidence_files'],
    cpu36_diagnostic_samples=diagnostic['total_samples'],
    original_mtime_ns_metadata='PRESERVED_AND_VERIFIED',
    latest_turn_scope='FIVE_SMALL_OPERATOR_CASES_ONLY_NO_MODEL_S02_OR_TRAINING_MEMORY',
    production_model_config='NOT_ACCEPTED')
r7 = json.loads((WORK / 'evidence/r7_cpu36_2034247/review.json').read_text(encoding='utf-8'))
assert r7['status'] == 'PASS_R7_BOUNDED_STARTUP_EVIDENCE_REVIEW_PENDING'
assert r7['job_exit_code'] == 0 and len(r7['rounds']) == 3 and r7['offline_summary'] == 'PASS'
validation.update(cpu36_registration='R7_BOUNDED_STARTUP_PASS_REVIEW_PENDING',
    latest_model_job=r7['job_id'], latest_model_review='evidence/r7_cpu36_2034247/review.json',
    model_pilots='R7_THREE_ROUNDS_CHILD_EXIT0_JOB_EXIT0_REMOTE_AND_OFFLINE_PASS',
    remote_training_tests='R7_REAL_PRE_DEC_THREE_REPS1_ROUNDS_PASS',
    full_model_evidence_files=r7['full_evidence_files'], offline_summary='PASS',
    offline_max_mtime_rounding_ns=r7['offline_max_mtime_rounding_ns'],
    latest_turn_scope='R7_SINGLE_DOMAIN_STARTUP_ONLY_NO_S02_OR_TRAINING_MEMORY',
    numerical_and_performance_acceptance='NOT_ESTABLISHED', production_model_config='NOT_DEPLOYED')
pair = json.loads((WORK / 'evidence/s02_r5_s03_c_20261105/review.json').read_text(encoding='utf-8'))
assert pair['status'] == 'COMPLETE_EVIDENCE_DELIVERY_S02_NUMERICAL_FAIL_S03_C_PASS'
assert pair['new_jobs'] == 2 and pair['retries'] == 0
validation.update(latest_model_job=pair['records']['S02']['job_id'],
    latest_model_review='evidence/s02_r5_s03_c_20261105/S02/review.json',
    latest_c_job=pair['records']['S03']['job_id'],
    latest_c_review='evidence/s02_r5_s03_c_20261105/S03/review.json',
    latest_turn_scope='ONE_S02_R5_KML_STRICT_THEN_ONE_S03_C_SAFETY_JOB',
    s02_model_pilot='EXECUTED_FAIL_ORIGINAL_CRITERIA_95_OF_1063',
    s02_affinity_fix='R5_ACTUAL_SAME_PID_SEVEN_CPU36_CHECKPOINTS_PASS',
    s02_training_memory='NOT_RUN_NUMERICAL_GATE_NOT_PASSED',
    full_model_evidence_files=pair['records']['S02']['full_evidence_files'],
    s03_c_safety='FROZEN_EXPECTED_FAILURE_CANDIDATE_25_PASS_ISOLATED_SO_PASS',
    s03_evidence_files=pair['records']['S03']['full_evidence_files'],
    s03_real_HBM='NOT_RUN', r7_offline_summary='PASS',
    offline_summary='R7_HISTORICAL_PASS_CURRENT_PAIR_METRIC_AND_C_EVIDENCE_AUDIT_COMPLETE',
    numerical_and_performance_acceptance='S02_NUMERICAL_FAIL_NO_FORMAL_PERFORMANCE_ACCEPTANCE')
current = json.loads((WORK / 'evidence/s02_r6_s03_r2_20261105/review.json').read_text(encoding='utf-8'))
assert current['status'] == 'COMPLETE_S02_R6_STRICT_PASS_S03_R2_UBSAN_LINK_BLOCKED'
assert current['new_jobs'] == 2 and current['retries'] == 0
validation.update(latest_model_job=current['records']['S02']['job_id'],
    latest_c_job=current['records']['S03']['job_id'],
    latest_turn_scope='ONE_R6_CKPT64_STRICT_AND_ONE_R2_UBSAN_JOB_NO_MEMORY_OR_HBM',
    current_round_evidence='evidence/s02_r6_s03_r2_20261105/review.json',
    s02_model_pilot='R6_B64_CKPT0_VS_CKPT1_1063_STRICT_METRICS_PASS_THIS_CASE_ONLY',
    s02_training_memory='NOT_RUN_THIS_ROUND',
    s03_c_safety='R2_DEFAULT_TOOLCHAIN_CANNOT_LINK_LIBUBSAN_CASES_NOT_RUN',
    full_model_evidence_files=current['records']['S02']['full_evidence_files'],
    s03_evidence_files=current['records']['S03']['full_evidence_files'],
    numerical_and_performance_acceptance='R6_THIS_CASE_STRICT_PASS_NO_MEMORY_OR_PERFORMANCE_ACCEPTANCE')
(WORK / 'evidence/delivery_validation.json').write_text(json.dumps(validation, indent=2) + '\n', encoding='utf-8')
index = WORK / 'ARTIFACT_SHA256.txt'
paths = [p for p in sorted(WORK.rglob('*')) if p.is_file() and p != index
         and not p.is_relative_to(WORK / 'tmp')]
index.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  '
                        + p.relative_to(WORK).as_posix() + '\n' for p in paths), encoding='utf-8')
print(json.dumps(dict(status=validation['status'], original_files_checked=len(before['files']),
    changed_originals=len(changed), hash_index_files=len(paths)), indent=2))
