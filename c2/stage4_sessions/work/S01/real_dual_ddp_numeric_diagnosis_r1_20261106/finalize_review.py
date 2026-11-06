"""Close the evidence-only R1 review; preserve original training refusal."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
S01 = OWN.parent
WORK = S01.parent
SRC = WORK / 'S07/real_dual_ddp_numeric_diagnosis_r1_20261106'


def asset(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    current = json.loads((OWN / 'DIAGNOSIS_REVIEW.json').read_text(encoding='utf-8'))
    assert current['status'] == 'WAITING_DIAGNOSIS_READY', 'do not overwrite a completed review'
    for source, target in [('DIAGNOSIS_REVIEW.json', 'WAITING_DIAGNOSIS_REVIEW.json'),
                           ('ARCHIVE_SCOPE.json', 'WAITING_ARCHIVE_SCOPE.json')]:
        with (OWN / target).open('xb') as stream:
            stream.write((OWN / source).read_bytes())
    for name in ('SESSION_STATUS.md', 'ROUND_DELTA.md'):
        with (OWN / ('RESUME_BEFORE_' + name)).open('xb') as stream:
            stream.write((S01 / name).read_bytes())
    evidence = json.loads((OWN / 'EVIDENCE_REVIEW.json').read_text(encoding='utf-8'))
    for row in evidence['inputs']:
        assert asset(Path(row['path'])) == row, row['path']
    old = Path(current['original_final_review']['path'])
    assert asset(old) == current['original_final_review']
    diagnosis = json.loads((SRC / 'DIAGNOSIS.json').read_text(encoding='utf-8'))
    supported = [
        'In the current controlled full/sequence sample, byte-identical linear inputs and adjoints yield different fp32 weight gradients; partition/grouping already reproduces the three failures without DDP.',
        'Existing identical-operand float64 contraction control strongly reduces the grouping difference, supporting precision/accumulation sensitivity; no specific native kernel or instruction identified.',
        'All thirteen original scalar gradient metrics are reproduced; scalar equality does not establish equality of historical DDP gradient vectors.']
    excluded = [
        'For current full versus sequence only: different sample/shard input or mask bytes, differing recorded initialization/RNG digests, or differing recorded environment/threads.',
        'For current full versus sequence only: differences in captured forward tensors or captured output adjoints as the origin of these failed weight gradients.',
        'For current full versus sequence only: local-mean averaging or duplicate parameter/input gradient division; code uses the same global denominators4/16384 and 1x objective.']
    gaps = [
        dict(code='E01_DDP_NOT_COMPLETED', detail='New DDP stopped before after_pg with10013/10049; no new rank gradient vectors/counts/reducer/input-scaling or sequence-DDP comparison. Additional DDP effects remain unknown.'),
        dict(code='E02_CLEANUP_PID_BINDING', detail='Popen supervised PIDs differ from compute PIDs. Direct handles were reaped, but actual compute PID/descendant exit timing and ownership were not retained. Current exact-PID check finds none; this does not prove all descendants reaped within15s.'),
        dict(code='E03_HISTORICAL_IDENTITY', detail='Original failure lacks actual thread counts, initial tensor digest and intermediate tensors; all13 scalar metrics matching cannot establish full historical vector/environment identity.'),
        dict(code='E04_EXACT_KERNEL', detail='No native kernel/instruction trace; shape/grouping-sensitive fp32 contraction precision is supported, exact implementation cause remains undetermined.'),
        dict(code='E05_FP64_THREAD_SNAPSHOT', detail='Float64 process used the same interpreter/controller environment and has no thread-changing code, but its own actual thread snapshot was not recorded.'),
        dict(code='E06_INITIAL_TENSOR_RETENTION', detail='New full/sequence/two rank initialization and RNG digests agree under identical seed/source; initial parameter tensors were not retained for a second direct tensor comparison. This limits direct reinspection, not the observed gradient reproduction.')]
    current.update(status='REVIEWED_PARTIAL_DIAGNOSIS_WITH_EVIDENCE_GAPS',
        decision='ACCEPT_PARTIAL_DIAGNOSIS_NOT_TRAINING_ACCEPTANCE', review_complete=True,
        reviewed_utc=datetime.now(timezone.utc).isoformat(), execution_authorized=False,
        training_pass_published=False, numerical_acceptance='FAIL_ORIGINAL_THRESHOLDS_PRESERVED',
        diagnosis_ready=dict(**evidence['ready'], exists=True),
        checks_status='60_SOURCE_AND_EVIDENCE_IDENTITIES_VERIFIED_34_SAVED_METRICS_RECOMPUTED',
        reviewed_diagnosis_artifacts=evidence['inputs'], evidence_review=asset(OWN / 'EVIDENCE_REVIEW.json'),
        report=asset(OWN / 'REPORT.md'), current_pid_check=asset(OWN / 'CURRENT_PID_CHECK.json'),
        supported_causes=supported, excluded_causes=excluded,
        excluded_scope='Only this fixed current full/sequence sample and recorded configuration; not a blanket DDP/C2 exclusion.',
        unknown_causes=['Additional new DDP effects and runtime scaling/count validation',
                        'Exact native kernel/instruction', 'Complete historical identity',
                        'Actual fp64 thread snapshot', 'Contemporaneous actual-worker/descendant cleanup timing'],
        insufficient_evidence=gaps,
        earliest_observed_nonzero=diagnosis['earliest_numeric_difference'],
        earliest_threshold_failure=diagnosis['earliest_original_threshold_failure'],
        earliest_scope='Observed graph-level locations, not instruction trace or proof loss rounding caused the weight gradient difference.',
        recomputed_metrics=34, original_gradient_metrics=13,
        failed_gradients=['val.weight', 'pos.weight', 'tf.weight'],
        initialization_and_threads=dict(initialization_sha256=evidence['initialization_digest'],
            post_init_rng_sha256=evidence['post_init_rng_digest'], threading=evidence['diagnosis_threading']),
        original_FAIL_preserved=True, new_model_or_diagnostic_paths_by_S01=0,
        minimum_next_action='If existing process ownership/compute-PID exit originals exist, S07 may supply them read-only; otherwise retain the timing gap without rerunning. Coordination decides any separately scoped minimal contraction candidate; no current frozen-source edit, DDP retry, fp64/reference replacement or job is authorized.',
        activity=dict(saved_tensor_metric_recomputations=1, forward_backward_runs=0, contraction_runs=0,
                      DDP_runs=0, optimizer_updates=0, full_model_runs=0, SSH=0, cluster_jobs=0,
                      read_only_recorded_compute_PID_check=1, author_source_edits=0, git_stage_commit_push=0),
        conclusion='Limited contraction/grouping precision diagnosis supported. Exact kernel and new DDP effects remain unknown; original numerical gate and final FAIL remain. No training release.')
    write(OWN / 'DIAGNOSIS_REVIEW.json', current)
    status = '''# S01简短状态

- 更新/轮次：2026-11-06；REAL_DUAL_DDP_NUMERIC_DIAG_R1_REVIEWED_WITH_GAPS。
- 本轮增量：续接WAITING，07 READY已到；11直接绑定、17来源、39证据共60唯一文件bytes/SHA核验，未重复旧完整审核。
- 独立验证：仅载入已保存full/sequence tiny张量，用原compare复算34指标；原13梯度标量全部复现，val/pos/tf.weight仍3项FAIL，18份前向/adjoint字节相同。
- 有限结论：支持相同操作数下fp32权重收缩分组累计精度差异；最早观测非零为coarse loss2.98e-8（门槛内），首个依赖顺序越门槛tf.weight；顺序分片/float64不代替原B64。
- 未知/不足：新DDP权限10013/10049在PG完成前停止，额外影响未知；具体native内核未知，旧环境/初值完整可比性与fp64实际线程快照不足。
- 清理边界：Popen与worker自报PID不同，缺实际worker/后代15秒内终态原件；10:42:27Z只读查4个已知计算PID均不存在，仅证明当时状态。
- 固定交付：DIAGNOSIS_REVIEW.json为ACCEPT_PARTIAL_DIAGNOSIS_NOT_TRAINING_ACCEPTANCE、review_complete=true、execution_authorized=false，报告/证据/不足和最小动作已绑定。
- 保留原件：旧S01_REVIEW最终FAIL SHA=f933a3af02a9362b9bce854935cbb18eecebfb38dd761805da163b48ff110f74未变；原阈值/冻结包不改，无训练PASS。
- 本轮未运行：S01 0新forward/backward/收缩/DDP/优化器/完整模型/SSH/集群作业；仅保存指标复算与只读PID核对，无等待监视/信号/提权/重试。
- 停点与下一步：若07已有PID归属及退出原件仅补既有证据，无则保留缺口；协调另定是否制作最小候选，本轮不修复/重跑/放行。仅写自身R1目录及短状态，精确归档见ARCHIVE_SCOPE，无共享Git操作。
'''
    delta = '''任务/轮次：S01 / 本地数值诊断R1独立复核完成（2026-11-06）。
状态变化：WAITING转有限诊断接受，review_complete=true；原数值验收及最终FAIL不变，无训练许可。
验证增量：60唯一文件SHA、34保存指标复算及原13梯度误差全复现；同输入/初值摘要/8线程、分母与缩放已核。
有限归因：支持fp32权重收缩分组累计精度差异；首个观测非零coarse loss，首个依赖越阈值tf.weight；新DDP/具体内核仍未知。
证据不足：实际worker PID与Popen不同，缺15秒内后代终态；当前4计算PID均不存在，历史身份和fp64线程快照仍有限。
停点与交付：DIAGNOSIS_REVIEW.json列不足和最小下一动作；S01无新增模型/收缩/DDP/集群路径，仅既有指标复算，不改作者源码或共享Git。
'''
    assert len(delta.splitlines()) == 6 and len(status.splitlines()) <= 40
    (S01 / 'SESSION_STATUS.md').write_text(status, encoding='utf-8')
    (S01 / 'ROUND_DELTA.md').write_text(delta, encoding='utf-8')
    selected = sorted(p for p in OWN.iterdir() if p.is_file() and p.name not in ('ARCHIVE_SCOPE.json', 'ARTIFACT_SHA256.json'))
    selected += [S01 / 'SESSION_STATUS.md', S01 / 'ROUND_DELTA.md']
    scope = dict(files=[asset(p) for p in selected],
                 excluded=['author raw tensors/ZIP/source duplicates', 'data/weights/environments', '__pycache__'],
                 git_operations_performed=False, conclusion='Evidence review only; original training FAIL preserved')
    write(OWN / 'ARCHIVE_SCOPE.json', scope)
    write(OWN / 'ARTIFACT_SHA256.json', [asset(p) for p in selected + [OWN / 'ARCHIVE_SCOPE.json']])
    assert asset(old) == current['original_final_review']
    print(json.dumps(dict(review=asset(OWN / 'DIAGNOSIS_REVIEW.json'), decision=current['decision'],
                         reviewed_unique_files=60, metrics_recomputed=34, original_FAIL_unchanged=True,
                         archive_files=len(selected), six_line_delta=True), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
