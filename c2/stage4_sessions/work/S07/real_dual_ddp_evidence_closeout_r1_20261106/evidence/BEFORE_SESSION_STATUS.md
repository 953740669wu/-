# S07 简短状态

- 更新/轮次：2026-11-06，NUMERIC_DIAGNOSIS_R1，当前07窗口续接；仅新诊断目录及自身状态可写。
- 当前状态：STOPPED_DDP_PERMISSION_FAILURE；新两rank在before_pg报本地10013/10049后立即停止，双方回收，无重试、换backend、提权、安装或job。
- 本轮范围：原seed7/TinyEncoder AST、输入/初值/mask/原比较器固定；一次完整B64、一次顺序32+32、一真实DDP尝试，另一次有证据前提的float64操作数收缩对照。
- 最早数值差异：前向逐层输出、反向中间adjoint完全一致；coarse loss标量归约差2.9802322387695312e-8、total差5.960464477539063e-8，均过原门槛。
- 最早越阈值：按反向依赖为tf.weight权重梯度收缩；tf最大绝对3.723800182342529e-5、相对1.142869133502608e-4；val.weight/pos.weight相对9.410191088070238e-5。
- 原失败复现：不经过DDP的顺序分片已复现同3项失败，全部13项标量误差与旧DDP原件精确相同。完整B64仍是正式参考，顺序分片仅用于定位。
- 原因证据：失败3个weight对应输入及输出adjoint逐位相同；float64同操作数全归约/32+32归约在val/pos差0，tf差6.827871601444713e-14。支持fp32权重收缩/累计精度受分组形状影响，未定位精确native内核/指令。
- 原因边界：新DDP未完成PG，无新输出/梯度；DDP额外影响仍UNKNOWN。旧13标量一致不证明旧未保存梯度向量相同。没有证据判定分母/DDP缩放实现缺陷，不能用float64给fp32 PASS。
- 一致性：四准备进程初值SHA及post-init RNG SHA一致，实际intra/inter-op均8/8且环境相同；原实际线程数未记录，为历史比较缺口。mask1+3=4、coarse16384；分母及输入梯度缩放来源/新观测在JSON分列。
- 检查/预算：34项扩展原指标及原13项保留；完整B64/顺序分片/float64均完成，DDP唯一尝试2.719秒停/清理0.016秒，5个自建子进程均回收，总路径壁钟11.594秒；原每路径60/清理15/总300上限未扩。
- 固定交接：real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_READY.json，SHA256=de9c6e26ea7d2f280b835e1de44dbc4697d0fee2c0cc69fe66b4fa986bf07dde；含DIAGNOSIS/REPORT/来源/指标/进程回收及精确归档清单。
- 证据：同目录HYPOTHESES_AND_CHECKS.md、SOURCE_INPUTS.json、evidence/FULL_VS_SEQUENCE.json、FLOAT64_CONTROL.json、ddp0.log/ddp1.log及监督记录；原始激活/梯度仅本地raw索引，不保存模型权重，归档排除环境/数据/权重/raw张量。
- 保持不变：17项必要来源bytes/SHA末次全匹配，原TRAINING_READY/训练包/原FAIL/01最终FAIL均未改，原绝对2e-5/相对2e-6及所有失败项不动；无数值重跑寻PASS。
- 下一步：01按DIAGNOSIS_READY独立核归因及缺口，交协调决定是否另定候选；本轮不改冻结训练包、不补跑DDP、不恢复900秒job。需要02回答的具体接口/数学疑点：无。
- 结论边界：C2模型训练、真实语料、优化器更新、性能/扩展效率均未执行/接受；原训练FAIL继续保持；无Git暂存/提交/推送。通信失败后仅JSON解释、报告与索引闭合及本状态更新，无新张量计算。