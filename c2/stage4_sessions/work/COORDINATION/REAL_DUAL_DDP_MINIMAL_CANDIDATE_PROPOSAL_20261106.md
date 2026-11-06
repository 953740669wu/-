# 完整Encoder/KML最小数值候选提案（仅静态评估）

发布给原02窗口；未确认接收或启动。07/01证据收尾已接受有限归档，原数值门槛/训练FAIL保持；真实模型DDP尚未运行。

本轮目标：回答一个具体疑点——原Tiny线性权重梯度的分组累计敏感性，在冻结完整Encoder的实际KML反向路径中哪些部位可对应、哪些不能外推；据此只提出一个最小候选方案或明确目前无充分依据。

参考文件（先短后详，以下以c2/stage4_sessions/work为根）：
- S02/SESSION_STATUS.md、ROUND_DELTA.md；自身real_dual_ddp_reference_20261106/REFERENCE_READY.json、冻结baseline/kml_ops.py、baseline/s4_models.py、原compare。
- S01/real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_REVIEW.json；必要时读S07同轮DIAGNOSIS.json及原tiny测试/训练图。
- S01/real_dual_ddp_evidence_closeout_r1_20261106/EVIDENCE_CLOSEOUT_REVIEW.json及收尾限制。
- COORDINATION/REAL_DUAL_DOMAIN_DDP_START_20261106.md，仅用于保持原B64参考、目标模型、精度、资源和比较要求。

完成标准：
1. 只读核来源SHA。仅写S02/real_dual_ddp_minimal_candidate_proposal_20261106/和自身短状态；不改冻结源/比较器/数据/原FAIL，不修改其他任务目录。
2. 列出实际线性反向的dX/dW/db调用和归约路径，明确Tiny原算子与KML实现相同/不同及证据边界。不得将Tiny fp64原因对照宣称为完整Encoder/C2修复。
3. 只选择一个有来源依据的最小修改点，写明预期机制、受影响张量/函数、数学不变量、风险和可证伪条件；若不能合理提出，则交NO_JUSTIFIED_CANDIDATE及具体缺项，不搜索矩阵。
4. 正式参考仍是原完整B64/fp32，原compare/阈值不改；不能用B32x2替代参考、改变seed/样本/归一化/损失/优化器，或靠放宽阈值通过。不要默认以float64替换生产计算。若任何设想需要改变既有精度/执行契约，只记录为超出当前约束、不执行。
5. 提案说明将来如何在独立候选目录先复现原失败、验证唯一改动，再保留完整模型严格前5步门槛；仅拟定最小回归验收，不运行。本轮0模型/收缩/新DDP/测试/基准/SSH/job，不安装或提权。
6. 输出PROPOSAL.json、REPORT.md、PROPOSAL_READY.json（源绑定、唯一候选或无候选、后续最小验证建议及未知项）、精确归档清单，更新短状态/六行摘要。

07/01/00/08本轮待命，不重复分派；02交付后总协调先判断是否有充分依据，再给01独立方案审核及是否制作候选的明确范围。当前无实现或实验授权。Git按新精确清单可并行归档已闭合诊断记录，02新提案目录不在该批范围。
