"""Record exact local closeout scope without any Git or cluster action."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
OWN = Path(__file__).resolve().parent
S01 = OWN.parent
S00 = S01.parent / 'S00/real_dual_ddp_20261106'


def asset(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    review_path = OWN / 'S01_REVIEW.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    assert review['decision'] == 'FAIL' and review['review_complete'] is True
    assert asset(Path(review['report']['path'])) == review['report']
    sys.path.insert(0, str(S00))
    import review_gate
    try:
        review_gate.validate(review, review_gate.expected(S00))
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise AssertionError('actual final FAIL accepted by S00 consumer')
    (OWN / 'FINAL_CONSUMER_CHECK.json').write_text(json.dumps(dict(
        final_review=asset(review_path), consumer=asset(S00 / 'review_gate.py'),
        actual_FAIL_rejected=True, reason=rejection, jobs_submitted=0), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    status = '''# S01简短状态

- 更新/轮次：2026-11-06；REAL_DUAL_DDP_FINAL_FAIL_NO_RELEASE。
- 本轮完成：独立核新DDP数学、完整B64参考、全部参数/AdamW覆盖、mask RNG、清理/截止静态链及具体SHA；固定S01_REVIEW.json已发布FAIL、review_complete=true、execution_authorized=false，不得用于提交。
- 具体阻断：07冻结严格small B64/双rank对照13项中val.weight/pos.weight/tf.weight 3项超原阈值；最终19方法17过1失败1平台skip。重新核算失败指标并保留，不豁免/重试/代改源码；不推断C2结果。
- 证据增量：02包18成员/17源/12复用与1600帧25批无重缺；07包21成员/19交付/79证据/18参考绑定/7个R7函数；00当前外包37成员36清单文件已核。完整SHA/资源/更新上限见S01_REVIEW.json和186项FROZEN_INPUTS.json。
- 部署边界：09:37:47Z快照未有最终S00_DEPLOYMENT_READY，旧login receipt与当前prepare.py/run_job.py不同，未冒称最终Linux部署通过；后到READY不改变本次FAIL。00消费者3项负检查及最终实际FAIL拒绝已核。
- 保留预算：rank32×2/global64；两域各38分配36实际留2、DDR总24576MB同limit/exclusive/HBM0；共同840+30+30=900秒、PG120；上限25全局/50rank/5参考=55，原阈值不变。
- 实际完成/未运行：S01 0提交/0SSH/0完整模型更新；此前隔离tiny FileStore一次超时已停、无本路径worker残留。未获放行/未收RUN_COMPLETE，C2前5/25步/同步/保存恢复/清理实际审核NOT_RUN；正式split/subject UNKNOWN、无val/test/提速结论。
- 活动job：本窗口未提交；S00实时队列未由本窗口核实，不由本地空记录推断集群状态。
- 停点与下一步：明确数值失败后结束有界等待，不耗尽90分钟或占节点。供协调决定针对性诊断/新修订，当前审核不授权追加job或重试；REPORT.md/ARCHIVE_SCOPE.json供唯一Git窗口归档，未操作共享Git。
'''
    delta = '''任务/轮次：S01 / REAL_DUAL_DDP_FINAL_FAIL_NO_RELEASE（2026-11-06）。
状态变化：最终固定审核FAIL、review_complete=true；07严格小B64对照3/13梯度超原阈值，不能放行唯一job。
本轮改动：仅自身real_dual_ddp_review_20261106及短状态；不改作者源码/旧包/阈值，不暂存提交推送。
验证增量：02的18成员17源12复用；07的21成员19交付79证据；00外包快照37成员；186输入SHA，消费者拒绝实际FAIL。
证据：REPORT.md、S01_REVIEW.json、FROZEN_INPUTS.json、training_review.json、deployment_snapshot_review.json、FINAL_CONSUMER_CHECK.json及ARCHIVE_SCOPE.json。
停点与下一步：C2训练/恢复/实际结果NOT_RUN，S01 0提交，S00实时job未直接核实；协调决定新诊断/修订，本次FAIL不授权追加作业。
'''
    assert len(delta.splitlines()) == 6 and len(status.splitlines()) <= 40
    (S01 / 'SESSION_STATUS.md').write_text(status, encoding='utf-8')
    (S01 / 'ROUND_DELTA.md').write_text(delta, encoding='utf-8')
    selected = [p for p in OWN.iterdir() if p.is_file() and p.name not in ('ARCHIVE_SCOPE.json', 'ARTIFACT_SHA256.json')]
    selected += [S01 / 'SESSION_STATUS.md', S01 / 'ROUND_DELTA.md']
    scope = dict(files=[asset(p) for p in sorted(selected)],
                 excluded=['frozen_reference/** duplicated author package', 'local_small_ddp/** duplicated probe inputs',
                           '**/__pycache__/**', '**/*.zip', 'raw data/weights/environments'],
                 git_operations_performed=False, conclusion='FAIL evidence archive, not accepted training code')
    (OWN / 'ARCHIVE_SCOPE.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    artifacts = [asset(p) for p in sorted(selected + [OWN / 'ARCHIVE_SCOPE.json'])]
    (OWN / 'ARTIFACT_SHA256.json').write_text(json.dumps(artifacts, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(decision='FAIL', final_review=asset(review_path), archive_files=len(artifacts),
                         six_line_delta=True, final_consumer_rejected=True), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
