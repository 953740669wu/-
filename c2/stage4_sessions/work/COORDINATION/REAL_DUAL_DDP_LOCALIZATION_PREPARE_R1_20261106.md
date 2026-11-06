# 固定首批零更新定位：本地取证工具准备

本轮只交原02窗口，卡已发布、未确认接收启动。总协调接受01的无候选审核及最小规格用于本地准备，授权仅限本卡指定新目录内的取证代码/文档和标准库夹具检查。并未授权规格中的实际模型运行、SSH、部署上传、资源申请或集群job。用户“不追加集群作业”约束继续有效；原训练FAIL/数值阈值保持。

## 本轮目标

将01 MINIMAL_EVIDENCE_SPEC转成具体、可审核的取证准备包；先解决可观测性、身份映射、保留量和有界退出的工程可行性。不是数值修复候选，不能用准备完成宣称实际KML/模型验证通过。

## 参考文件

以E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work为根：
- 自己SESSION_STATUS/ROUND_DELTA及real_dual_ddp_minimal_candidate_proposal_20261106/PROPOSAL_READY.json。
- S01/real_dual_ddp_proposal_review_20261106/PROPOSAL_REVIEW.json及MINIMAL_EVIDENCE_SPEC.json；规格SHA=d1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2。
- 自己冻结real_dual_ddp_reference_20261106的READY、原模型/KML/loader/mean损失/compare，只按规格相关位置读。
- S00/real_dual_ddp_20261106已保存的C2已装DDP/Torch来源及R4运行时记录仅作只读依据；不重新SSH获取。
- S01/real_dual_ddp_evidence_closeout_r1_20261106/EVIDENCE_CLOSEOUT_REVIEW.json，避免将Popen句柄当实际compute/全部后代清理证据。

## 完成标准

1. 仅写S02/real_dual_ddp_localization_prepare_r1_20261106/及自己的状态。不得修改原MINIMAL_EVIDENCE_SPEC、已发布READY/包/比较器/数据/旧FAIL；需要改变规格时明确CONTRACT_CONFLICT并交协调裁决，不静默预设。
2. 编码前在DECISIONS_BEFORE_CODE.md记录：实际2.7.1可用API依据、attention等token-major张量的逻辑样本轴映射、每算子实际dX观察位置、保留内存/输出量上界、直接启动解释器及compute PID/PPID/start identity/进程组所有权记录方案。
3. 不复制全项目，不建通用平台。只封装首批零更新诊断，复用冻结源。参考用原mean表达式；不得调用会执行optimizer.step的train_step/B64Reference.advance。顺序32+32用全局分母、系数1、参数/input grad均不除2；原153参数/所有输出/损失/输入梯度覆盖保持。
4. 核心先判可行：实际VJP必须来自被动观察，不能用合并叶梯度冒充，也不能额外backward/autograd.grad/GEMM。不能可靠观察或证明逻辑映射时交BLOCKED_PREPARATION_WITH_REASON，不降低覆盖或伪造字段。已有源码/API不足只列具体缺项，不安装/联网/导入Torch运行验证。
5. 先写针对性标准库夹具再最小实现：样本轴映射/重缺样拒绝、顺序分母与缩放契约、单次路径计数/禁止优化器更新、内存与输出量计账、共同截止、PID身份不一致拒绝、缺失/残报告拒绝。仅元数据/替身夹具，标LOCAL_FIXTURE，不称autograd/KML/Linux验证。不得重跑Tiny或已有大套件。
6. 未来实际计算严格按原规格：B64一次、顺序32+32一次；0优化器更新/0DDP/0额外收缩；首64原样本/seed0/mask/scale及原比较器不变。数值失败停止新计算路径，仅整理已有证据。300秒及CPU36/24GiB等只是未来拟议上限，不是本轮资源许可。
7. 未来进程记录必须来自实际compute自身PID/PPID/start ticks/当前job身份，并关联监督器与全部所属后代；明确回收事件/缺失证据的处理。标准库夹具无法证明Linux实际退出时序，须列NOT_RUN。
8. 先交INTERFACE_READY.json供后续部署准备，列输入/CLI/结果/退出码/收集项；稳定后交PREPARATION_READY.json、源码清单/最小diff/包/SHA、原规格绑定、保留量证明、实际本地检查与明确未测项。接口发布不授权00启动部署或job。
9. 若阻断，交PREPARATION_BLOCKED.json列唯一具体技术阻断/现有证据/需要的最小后续动作，不为完成包绕过规格。
10. 更新自身短状态和六行摘要，给精确归档清单。无共享Git暂存/commit/push；无Torch导入/张量反序列化/模型/收缩/数值/DDP/SSH/集群/安装/提权/大范围进程扫描。

## 依赖与下一步

原01/00/07/08/Git待命，不重复分派。02准备包或具体阻断到后，总协调再给01代码/规格独立审核及00本地部署准备范围；所有准备和审核完成后，如确需计算节点取证，必须把具体包、资源、工作量和风险交用户明确决定。当前不询问空泛执行许可，也不预先授权任何新job。静态提案与审核材料留下一批精确Git归档，到提交节点主动提醒。
