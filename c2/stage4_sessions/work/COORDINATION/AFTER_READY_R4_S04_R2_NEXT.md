# 本轮短交接：00就绪同步部署适配与04有限fp32对齐

2026-11-05；原会话继续。先读短状态/增量，再按需读本轮必要材料；改动前核最新源/包身份。此轮只本地准备，无新集群job安排。

## S00

**本轮目标**：把已核S07双方就绪同步R4内包适配成新的部署包装层，固定具体身份和44项检查，交协调核包；不复用旧包重跑。

**参考文件**：自己的短状态；COORDINATION/S07_READY_R4_S04_R2_REVIEW.md/.json；S07/round4_readiness_20261105/{INTERFACE_FOR_S00.md,SOURCE_MANIFEST.json,SHA256SUMS.txt,package/S07_READY_SYNC_R4.zip}；S00/s07_wrapper_r4_diag_20261105原包装器。

**完成标准**：

1. 仅S00新版本目录，固定内包名S07_READY_SYNC_R4.zip、34295bytes、SHA=d39ae26f2b29d53f733bdef937832edeeec4bf4a468adf2d0eff0dbe5fb39c45、14成员/13文件/12项delivery。更新prepare/consumer的包身份、精确成员及payload_files计数；原已核07代码不修改，不覆盖旧R4部署包或失败。
2. 新增16 readiness检查，合计16+6诊断+6身份+16原检查=44；明确Windows43过/1 Linux跳过与未来同job44全过门槛。保持270秒统一consumer/300秒job提案，新检查消耗原剩余预算，不叠加时间。
3. 原调度nonce/raw/ready交接、现场CCS_JOB_ID、76核两域每域36实际、总DDR24GiB/exclusive及原四case/5秒/30秒总监督/清理均不改。S00不得预制参与者/worker ready来绕过候选真实PID和准备检查。
4. 终态收集新增participants.json、两个ready_rank*.json及.tmp残件、manifest.ready_token、父真实PID和双方/父events；核run/job/token/PID/绝对deadline关系，原件不完整仍完整保留。时序区分原子ready文件发布与稍后的ready_published日志，不能拿两rank日志先后错误否决合法就绪。
5. 做新包身份/44检查安排/就绪文件及错误残件收集等必要本地检查，给最小diff、新部署包/SHA、实际成员/测试数、精确命令和停止条件。日志/清单不能扩大成实际Linux通过。根因与通信接受仍待新job。
6. 更新自己的短状态和六行变化摘要，交协调复核具体包后才另行安排一次有界诊断。本轮不SSH/提交02/06/07，不临时安装或扩预算，不操作共享暂存区。

## S04

**本轮目标**：执行一次有限的无量化fp32计算路径对齐验证，并交一个敏感精度边界提案。当前不实现新bf16性能候选、不上集群。

**参考文件**：自己的R2短状态；COORDINATION/S07_READY_R4_S04_R2_REVIEW.md；S04/round2_local_attribution_20261105/{REPORT.md,candidate/,tests/,evidence/fp32_control.json,evidence/linear1_fp32_epilogue.json,evidence/key_bias_rounding.json,evidence/adamw_replay.json}及原冻结协议/夹具。

**完成标准**：

1. S04新独立R3目录，R1/R2完整保留；只一次明确的fp32计算路径对齐尝试。保持夹具/初权重/loss/AdamW/2线程、原83项检查及既定门槛，不改分母、eps或豁免参数/增量。
2. 诊断目标为候选同一重写结构与原参考采用一致的fp32算子/求值及反向归约路径：优先明确F.linear/addmm与mm+add的bias epilogue、原生autograd与自定义backward的差异。对齐是建立可比控制，不把合法舍入称编码错误；也不能直接换回整个原block来跳过候选结构验证。
3. 先有针对性对照，再做最小诊断路径改动；逐项报告原7个失败是否变化、是否出现新失败，并完整给83项结果。R1实际bf16模式保持原字节或明确验证行为未改；不得用反事实参考gate、注入参考梯度或参考权重强行通过。
4. 若仍不能通过，说明未对齐路径/误差来源与原门槛冲突，停在诊断结论，不继续无界修正舍入或自动寻找新阈值。若83全过，也只接受本地fp32控制，不提升为bf16/KML通过。
5. 交至多一个下一混合精度边界提案，明确FFN1/ReLU及QKV梯度/bias归约哪些保留fp32、入口量化仍影响哪些路径、dtype接口/转换成本可能如何变化，以及原83项数值通过/否决条件。该提案本轮不实现；若在原门槛和目标下没有合理方案，明确建议结束当前bf16候选方向，不勉强交新方案。
6. 交实际控制结果、简短原因说明、最小diff/来源SHA，代码变化才打新包。无KML/CPU36/性能/峰值/200步/完整模型/S05；按六行摘要更新并汇报，不操作共享Git暂存区。

## 其余与归档

S07原会话待00适配及后续现场结果；本地16项通过不是实际Gloo通过。02已收尾，03/06不重复缺依赖job，05/08等前置。已核07新内包和04归因/失败证据提醒唯一Git窗口按真实边界归档；00/04后来变更另核，本轮不把失败记录标为精度/性能接受。
