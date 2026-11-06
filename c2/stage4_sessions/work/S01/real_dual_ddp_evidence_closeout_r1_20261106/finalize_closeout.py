"""Publish archive-only closeout opinion, preserving both earlier S01 conclusions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
S01 = OWN.parent
WORK = S01.parent
SRC = WORK / 'S07/real_dual_ddp_evidence_closeout_r1_20261106'


def asset(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    path = OWN / 'EVIDENCE_CLOSEOUT_REVIEW.json'
    prior = json.loads(path.read_text(encoding='utf-8'))
    assert prior['status'] == 'WAITING_EVIDENCE_CLOSEOUT_READY', 'do not overwrite a final review'
    for name in ('EVIDENCE_CLOSEOUT_REVIEW.json', 'ARCHIVE_SCOPE.json'):
        with (OWN / ('WAITING_' + name)).open('xb') as stream:
            stream.write((OWN / name).read_bytes())
    for name in ('SESSION_STATUS.md', 'ROUND_DELTA.md'):
        with (OWN / ('RESUME_BEFORE_' + name)).open('xb') as stream:
            stream.write((S01 / name).read_bytes())
    audit = json.loads((OWN / 'CLOSEOUT_AUDIT.json').read_text(encoding='utf-8'))
    for row in audit['inputs']:
        assert asset(Path(row['path'])) == row, row['path']
    for key in ('prior_diagnosis_review', 'original_final_FAIL'):
        assert asset(Path(prior[key]['path'])) == prior[key]
    limitation_items = []
    for row in prior['items_to_review']:
        cases = [case for case in audit['case_results'] if case['review_gap'] == row['code']]
        assert cases and all(c['classification_accepted'] for c in cases)
        limitation_items.append(dict(code=row['code'], prior_limitation=row['prior_limitation'],
            historical_evidence_recovered=False, closeout_status='LIMITATION_ACCURATELY_FINALIZED',
            related_cases=cases, remains_unknown=True))
    ready = json.loads((SRC / 'EVIDENCE_CLOSEOUT_READY.json').read_text(encoding='utf-8'))
    result = dict(prior)
    result.update(status='COMPLETE_ACCEPT_FOR_LIMITED_DIAGNOSIS_ARCHIVE',
        decision='ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS', review_complete=True,
        reviewed_utc=datetime.now(timezone.utc).isoformat(), execution_authorized=False,
        training_pass_published=False, delivery_ready=dict(**audit['ready'], exists=True),
        reviewed_supplement_assets=audit['inputs'], audit=asset(OWN / 'CLOSEOUT_AUDIT.json'),
        report=asset(OWN / 'REPORT.md'), reviewed_unique_files=68,
        referenced_original_files=56, original_field_checks=86, targeted_search_files=40,
        metadata_archives_checked=2, classifications=audit['classification_counts'],
        classification_opinions=audit['case_results'],
        historical_evidence_completed=[], limitations_finalized=limitation_items,
        items_to_review=[], current_archive_blockers=[],
        evidence_clarified=[
            'Five direct Popen handles have completion receipts, without proving actual compute/descendant ownership or historical15s cleanup.',
            'Four role-associated compute PIDs differ; the fp64 compute PID is absent. A Windows launcher explanation remains unsupported as a specific historical cause.',
            'Existing later PID absence has its original observation-time scope only; no synthetic creation/termination/exit events were introduced.',
            'Original broad cleanup wording is explicitly restricted in the supplement; original READY/report bytes remain intact.'],
        archival_opinion=dict(status='ACCEPT_AS_LIMITED_DIAGNOSIS_WITH_RETAINED_GAPS',
            can_archive_as_reviewed_closeout=True, basis='Accurate source-bound limitation closure; no historical gap recovered.',
            scope='Reviewed limited diagnosis with its closeout caveats retained together. S07 new scope has11 closeout files and2 own mutable status paths; S01 own exact scope is separate. Coordination/Git must freeze the combined exact batch, not append accepted268 batch.',
            S07_scope=asset(SRC / 'ARCHIVE_SCOPE.json'),
            followup_experiment_required_for_archive=False,
            source_count_56_is_not_old_archive_batch_55=True,
            not_numerical_acceptance=True, not_historical_cleanup_runtime_pass=True,
            not_training_authorization=True),
        historical_compute_and_descendant_15s_cleanup='UNKNOWN_NOT_PROVEN',
        retained_gap_scope='Not recoverable in the enumerated existing records; no global disk/environment/system-log irrecoverability claim.',
        prior_reviews_unchanged=True, prior_numerical_acceptance='FAIL_PRESERVED',
        current_insufficient_evidence_for_archive=[],
        insufficient_evidence=[row['prior_limitation'] for row in limitation_items],
        minimum_next_action='Coordination may freeze the limited-diagnosis/retained-gap archive; sole Git window uses a new exact scope. No additional evidence-recovery experiment is required. Any numerical candidate or new lifecycle protocol needs a separately scoped task; no run/job is authorized here.',
        waiting_policy=dict(wait_loop_started=False, background_monitor_started=False, completed_without_waiting=True),
        activity=dict(models=0, contractions=0, DDP=0, cluster_jobs=0, SSH=0,
            new_process_checks=0, torch_imports=0, tensor_deserializations=0,
            numerical_recomputations=0, archive_metadata_inspections=2,
            author_original_edits=0, git_stage_commit_push=0),
        conclusion='Archive record closeout accepted with all E01-E06 limits retained. No historical-cleanup or numerical PASS; original diagnosis and final training FAIL preserved.')
    assert ready['historical_gaps_recovered'] is False
    write(path, result)
    status = '''# S01简短状态

- 更新/轮次：2026-11-06；REAL_DUAL_DDP_EVIDENCE_CLOSEOUT_R1_COMPLETE_ARCHIVE_WITH_LIMITS。
- 本轮增量：续接WAITING，07收尾READY已到；10直接绑定、56来源共68唯一文件bytes/SHA核验，86处原字段/源码行/日志相符，40份定向检索及2份raw元数据核对。
- 归档结论：EVIDENCE_CLOSEOUT_REVIEW为ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS、review_complete=true、execution_authorized=false；可按有限诊断/缺口保留归档，无需新增实验补历史。
- 分类核验：15项分类5 SUPPORTED、4 UNSUPPORTED、6 NOT_RECORDED均接受其范围；支持项限PID逻辑关联/5个直接Popen句柄记录等，不代表15项运行通过。
- 历史补齐：0；E01–E06限制如实定稿。实际父子/后代身份、15秒compute清理、fp64 PID/线程、旧初态/向量、初始权重原张量、具体内核及DDP额外影响仍未知。
- 表述收窄：07明确将旧全部子进程回收收窄为5个直接句柄回执；后来PID不存在/相对耗时/mtime/hook时间均未被当历史退出事件。UNKNOWN不冒称清理实测失败。
- 保留原件：原DIAGNOSIS_REVIEW SHA=a18ab449e1d99fd830fb6360d3abd85add53dbdf175081472417634516a47314、原最终FAIL SHA=f933a3af02a9362b9bce854935cbb18eecebfb38dd761805da163b48ff110f74未变；原阈值与冻结包不改，无数值/清理实测PASS或训练许可。
- 本轮运行：仅只读SHA/字段/元数据核对；0模型/收缩/DDP/数值复算/Torch导入/张量反序列化/新进程查询/SSH/集群；无监视、提权、作者原件编辑或共享Git操作。
- 精确归档：07新清单11收尾文件+2自身短状态；01自身清单见ARCHIVE_SCOPE。56来源数不等于旧55待归档清单，不追加已验收268批次。
- 下一步：协调按保留限制的诊断档案冻结新精确批次，唯一Git窗口据清单归档；后续候选或生命周期记录协议另立任务，本轮不授权执行。
'''
    delta = '''任务/轮次：S01 / 诊断R1只读证据收尾复核完成（2026-11-06）。
状态变化：WAITING转ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS，review_complete=true，无执行许可。
验证增量：68唯一文件SHA、86原字段、40份定向文本和2份raw元数据；15分类5支持/4不支持/6未记录均核。
结论边界：历史缺口补齐0，E01–E06已如实定稿；父子/后代15秒清理等仍未知，可归档不等于数值或清理实测通过。
保留与未运行：原DIAGNOSIS_REVIEW/最终FAIL及阈值不变；无新模型/收缩/DDP/数值复算/进程查询/集群/共享Git操作。
交付与下一步：EVIDENCE_CLOSEOUT_REVIEW.json及ARCHIVE_SCOPE；协调按新精确清单归档有限诊断，不追加268批次，不由归档意见授权训练。
'''
    assert len(delta.splitlines()) == 6 and len(status.splitlines()) <= 40
    (S01 / 'SESSION_STATUS.md').write_text(status, encoding='utf-8')
    (S01 / 'ROUND_DELTA.md').write_text(delta, encoding='utf-8')
    selected = sorted(p for p in OWN.iterdir() if p.is_file() and p.name not in ('ARCHIVE_SCOPE.json', 'ARTIFACT_SHA256.json'))
    selected += [S01 / 'SESSION_STATUS.md', S01 / 'ROUND_DELTA.md']
    write(OWN / 'ARCHIVE_SCOPE.json', dict(files=[asset(p) for p in selected],
        excluded=['author raw/ZIP/source duplicates','environment/data/weights','old accepted268 batch'],
        git_operations_performed=False, scope='S01 new closeout evidence and own two short states only'))
    write(OWN / 'ARTIFACT_SHA256.json', [asset(p) for p in selected + [OWN / 'ARCHIVE_SCOPE.json']])
    for key in ('prior_diagnosis_review', 'original_final_FAIL'):
        assert asset(Path(result[key]['path'])) == result[key]
    print(json.dumps(dict(review=asset(path), decision=result['decision'],
        historical_gaps_recovered=False, prior_reviews_unchanged=True,
        own_archive_files=len(selected), six_line_delta=True), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
