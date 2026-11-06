"""Publish the one immutable S01 R12 decision after exact input revalidation."""
import datetime
import json
import os
from pathlib import Path
import sys
from audit_code import OWN, WORK, asset, sha

sys.dont_write_bytecode=True
sys.path.insert(0,str(OWN/'frozen_deployment'))
import review_gate


def save(name,value):
    (OWN/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    final=OWN/'S01_REVIEW.json'
    if final.exists():raise FileExistsError('published review is immutable')
    code=json.loads((OWN/'code_review.json').read_text(encoding='utf-8'))
    dep=json.loads((OWN/'deployment_review.json').read_text(encoding='utf-8'))
    assert code['blockers']==dep['blockers']==[]
    frozen=json.loads((OWN/'FROZEN_INPUTS.json').read_text(encoding='utf-8'))
    for entry in frozen['files']:assert asset(Path(entry['path']))==entry,entry['path']
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    review=dict(task='S01',round='R12_DW_AB',decision='PASS_FOR_ENGINEERING_R12_AB',
        review_complete=True,published_utc=now,immutable_after_publish=True,blockers=[],
        bindings=dep['release_bindings'],resources=dep['resources'],workload=dep['workload'],
        remote_staging_root='/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z',
        baseline_sha256='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26',
        code_review=asset(OWN/'code_review.json'),deployment_review=asset(OWN/'deployment_review.json'),
        frozen_inputs=asset(OWN/'FROZEN_INPUTS.json'),
        authorization_scope='Only the task-card unique same-node target -> strict5 each -> perf25 each chain. S00 rechecks same SHAs/live queue/new exclusive marker before submitting once; no user relay needed.',
        numerical_gate='Original comparator retained: tensor max_abs<=2e-5, state<=2e-6, l2_relative<=2e-6 unless reference norm<=1e-8; finite/shape/dtype/exact step checks unchanged.',
        expected_counts_per_update=dict(baseline=dict(logical=149,native=149,target_logical=12,target_full=12,target_tiles=0,dispatch=0),candidate=dict(logical=149,native=161,target_logical=12,target_full=0,target_tiles=24,dispatch=12)),
        S01_execution=dict(new_jobs=0,full_model_runs=0,actual_KML_runs=0,remote_connections=0),
        actual_KML_target='NOT_YET_VERIFIED_BY_THIS_REVIEW',full_encoder_strict='NOT_YET_VERIFIED_BY_THIS_REVIEW',
        same_node_AB='NOT_YET_VERIFIED_BY_THIS_REVIEW',signal_fault_cleanup='NOT_RUN_THIS_ROUND',
        engineering_only=True,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',
        stop_conditions='Any numerical/ABI/source/library/CPU/dispatch failure stops later phases; timeout or insufficient budget INCOMPLETE; no retry, shorter25, changed tile/precision/backend/resources.',
        conclusion='专项前置审核通过；00可按具体SHA执行本卡唯一有限R12工程作业。不是实际KML数值通过、加速或生产接受。')
    report='''# S01 R12 专项复核报告

结论：**PASS_FOR_ENGINEERING_R12_AB，review_complete=true，无前置阻断项。** S00可核对本轮固定审核原件和同SHA后直接执行唯一作业，无需用户中转。审核对象仅本轮冻结候选、实际target→strict5→两独立perf25门槛链和新部署；未重复R11完整审核或旧矩阵。

## 列块ABI、边界和实际导入

候选仅在fp32 CPU/实际KML、ta=True/tb=False、beta0/out=None/acc32False且(m,n,k)=(512,2048,13312)时命中。原连续性/同dtype断言保持；新增stride/element_size/4字节对齐/输出storage不alias输入断言。两个N=1024块均完整K=13312，A地址不变，B/C偏移分别0和4096bytes，lda512/ldb2048/ldc2048，alpha1/beta0。A/B/C最大float索引6815743/27262975/1048575在原buffer内；两块C列区间互斥、覆盖最终C，无K分块或部分梯度累加，无大输入复制。

独立AST删除唯一新增if后与原baseline完全一致；唯一diff逐字一致，其它函数/forward/dX/bias/gb与fallback保持原路径。实际target一次baseline/一次candidate，使用canary、输入前后相等、完整14参数指针/leading dimension与原比较器；拒绝Python替身_sgemm。candidate由明确路径importlib加载，baseline来源有精确路径检查；SOURCE_SHA256前后核验和输出import SHA绑定这两个实际模块，未加载R10候选。

run_job.sh使用env-i清除PYTHONOPTIMIZE，冻结环境不重新设置；外层拒绝sys.flags.optimize/PYTHONOPTIMIZE，子解释器仅-B，没有-O/-OO，因此已交断言在此启动链中启用。

## 实际数值门槛链和计数

冻结shell set-euo pipefail串行执行target→strict→perf_baseline→perf_candidate。target收据SHA/source/host/job/selected36进入strict；strict收据SHA/source/descriptor/host/job/CPU进入两个新性能进程。各阶段还比较实际KML/OpenMP/shim映射及SHA、Torch/NumPy文件版本和环境；原固定descriptor与SOURCE绑定的初始化/25步参照补齐数据身份。原descriptor/归一化、37995777参数初始权重SHA、seed0、每步frame/order/mask均拒绝漂移。target不读取语料，数据身份在strict/perf入口强制验证。

严格阶段两侧各连续5更新，比较h/voltage/coarse、三个loss、两个输入梯度、全部参数梯度/更新参数/相对初始delta、AdamW step/exp_avg/exp_avg_sq及buffers。冻结tests/check_equivalence.py字节未改：tensor max_abs<=2e-5，state<=2e-6；同时要求L2 relative<=2e-6（原reference norm<=1e-8例外保留），shape/dtype/finite与exact step检查保持；不是loss-only。每步并保留原job首5 loss门槛。strict的双模型/hook时间不作性能对照。

每次更新都强制核以下计数，candidate不能误用旧native149或删门禁。它们仅表示此KML路径的直接调用，不表示Torch全部BLAS。

| 侧别 | logical | target logical | native SGEMM | target full | target tiles | dispatch |
|---|---:|---:|---:|---:|---:|---:|
| baseline |149|12|149|12|0|0|
| candidate |149|12|161|0|24|12|

性能两侧各独立新进程25更新，前5预热、后20观察，无profiler/输出hook；两侧相同诊断、finite/状态/暴露检查，保留训练调用、诊断、加载、壁钟分项以及process-lifetime RSS/HWM。各侧必须保存checkpoint并完成0额外更新恢复；任一侧不足25或恢复失败均无完整A/B。最多60个完整模型更新、仅一对，不能缩步、换tile或追加试验。

## 新部署、预算、退出与收集

新目录 /home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z/payload；旧2043445/2048959/2049454及旧marker被拒绝。review_gate强制本轮PASS、review_complete、10项SHA、resources和workload；submit_once独占x创建新marker，一次dsub，模糊提交不重试。S00提交前须按COMMANDS重查实际队列/现有记录和同SHA，S01没有代做远端查询。

单节点单NUMA、38分配/实际36留末2、24576MB DDR且limit同值、exclusive/HBM0/retry0。原生调度身份/物理core/DDR门禁及CPU36合同保持；框架前绑定36，逐检查点采集全部TID边界和实际Torch intra-op=36，缺证据/越界/错线程数拒绝。OMP/MKL=36、OPENBLAS=1，调用线程较窄合法子集不误拒绝。

START从外层import开始，原生gate与整个应用共用绝对START+840；外层计时器和run_phase绝对截止优先于内层840/入口720后备，不能先前置再额外840或逐阶段重置。统一TERM15/KILL15，总清理<=30且最晚START+870，调度900留30收尾；PR_SET_CHILD_SUBREAPER及PID/start_ticks跟踪所属跨session后代并reap，不杀不相关进程。非零/数值失败立即停后续；超时/不足预算记INCOMPLETE，不续跑或缩短25。

r12_outcome核四阶段原协议/成功状态、60更新、两侧frame/mask/init、import/CPU/library/native计数、原metrics及恢复；inspect再核原步骤日志/账本/收据SHA。缺阶段、后续越过失败、错计数或任一不完整不判成功。收集保留原错误、target/strict/两侧perf/dw_ab、runner/调度/退出/清理和部分账本；含糊暴露不声称未使用。权重留远端，仅回传路径/bytes/SHA，收尾须确认所属PID清空。

## 本轮证据及限制

独立核02代码ZIP 27成员/26源、14复用、Python3.9 AST/LF/CRC、唯一diff；新25步参照与原job2043445步骤日志逐项一致，1600索引无重复。核作者5项数学/ABI加4项运行契约原件、30项差0比较及导入证明；它们仅本地假CBLAS/native Torch证据，没有重跑这套数学检查。

核00部署33 ZIP成员（32文件+1目录）/30索引、7原封复用helper、10项执行绑定；源码/包/索引逐字与冻结原件一致。核00本地9项、Linux登录9项fixture及元数据/旧9项身份/固定16单元36文件SHA收据。S01只对冻结副本导入stdlib review_gate并验证实际拟发布记录，未提交作业或运行矩阵/模型；77份冻结输入最终复核均无漂移。

本轮未现场触发Linux信号/超时故障清理，不能用fixture冒充已实测。实际KML局部门槛、完整Encoder严格对照、CPU/TID现场表现和两侧性能结果均待唯一作业。预算内可能INCOMPLETE，必须照原规则停止。正式split/subject UNKNOWN，无val/test；本审核不建立正式划分，不作效果、稳态收益或生产接受。

## 精确绑定与交接

'''
    report+='| 执行绑定 | SHA256 |\n|---|---|\n'
    report+=''.join('| '+k+' | '+v+' |\n' for k,v in review['bindings'].items())
    report+='\n基线SHA='+review['baseline_sha256']+'。全部输入路径/bytes/SHA见FROZEN_INPUTS.json，逐项复核见code_review.json和deployment_review.json；固定S01_REVIEW.json发布后不热改。\n\n只写本任务目录及自身SESSION_STATUS.md、六行ROUND_DELTA.md；原源/门槛/数据/历史审核不改，未操作共享Git暂存/提交/推送。精确可归档清单见ARCHIVE_FILES.json，排除ZIP、frozen副本、语料/权重/环境；S00直接读取固定审核执行并跟踪原job，失败停止无自动重试。S01本轮前置复核结束，不后台监控。\n'
    (OWN/'REPORT.md').write_text(report,encoding='utf-8')
    review['report']=asset(OWN/'REPORT.md')
    review_gate.validate(review,dep['release_bindings'])
    temporary=OWN/'.S01_REVIEW.json.partial'
    with temporary.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(review,ensure_ascii=False,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    if final.exists():raise FileExistsError('refuse replacing published review')
    temporary.rename(final)
    print(json.dumps(dict(decision=review['decision'],review_complete=True,review=asset(final),report=review['report']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
