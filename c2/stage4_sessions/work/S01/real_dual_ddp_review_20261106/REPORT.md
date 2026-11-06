# S01 首次真实双域 DDP 专项审核

本轮结论：**FAIL，当前冻结候选不放行真实训练**。这是预提交审核结论；不是 C2/KML 数值失败，也不是已执行完整模型的结论。固定 `S01_REVIEW.json` 的 `review_complete=true` 表示本次拒绝结论已完成，不表示部署或训练通过。00 不得据此提交本轮唯一 job。

具体阻断是 07 已披露、保留在冻结测试中的严格小 B64 对双 rank fp32 梯度失败。独立重核 13 项指标，以下 3 项超出原门槛：

|梯度|最大绝对差|相对 L2|判定|
|---|---:|---:|---|
|val.weight|1.9147992134094238e-5|9.410191088070238e-5|相对差超 2e-6|
|pos.weight|1.9147992134094238e-5|9.410191088070238e-5|相对差超 2e-6|
|tf.weight|3.723800182342529e-5|1.142869133502608e-4|绝对差超 2e-5，且相对差超 2e-6|

证据为 [strict_pair_metrics.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S07/real_dual_ddp_20261106/evidence/tiny_ddp_192181562000000/strict_pair_metrics.json)，SHA256=`2db66215b4fb2584faabbad888c7677a36aa593b4c3e42e8d5312ed3216c6ee2`；[严格断言](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S07/real_dual_ddp_20261106/tests/torch_checks_worker.py:123) 和 [rank0.log](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S07/real_dual_ddp_20261106/evidence/tiny_ddp_192181562000000/rank0.log) 相符。监督结果为 child_failed、exit_codes=[1,0]、all_reaped=true、4.734秒；不是未建立 PG 的假失败。两 rank 参数梯度相等、除2后的输入梯度通过，均不足以代替 B64 参数梯度数值门槛。

[最终 LOCAL_CHECKS](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S07/real_dual_ddp_20261106/evidence/LOCAL_CHECKS.json) 为 19 方法：17通过、1失败、1 Windows 平台跳过；旧通信通过日志不覆盖新失败。根据本轮“失败即停止”和不能豁免数值风险，S01 不把该状态转换为执行 PASS。尚未确定差异的根因；没有据此推断 C2 与 Windows 结果相同，也没有改阈值、缩批、换成 B32x2 参考、重试数值实验或代改作者代码。进一步诊断/新修订应由协调明确安排，当前审核文件不授权任何追加作业。

已完成的数学及静态核验如下（均不冒充运行通过）：

- 真实 DDP 包装完整 Encoder、head_v、head_coarse 与可微误差和，训练走 ddp forward；DDP 参数对象覆盖原 37995777 参数。每批原64索引前32/后32分片，25批并集恰为1600且无重复。全局分母采用脱梯度计数 SUM；本地 loss 为 `2*(Sv/Nv+Sc/Nc)`，空本地 mask 保持图，全局零分母拒绝；日志用全局误差和。默认参数梯度均值后不再除2，拼接的输入梯度除2。没有用总 loss 接近代替逐项门槛。
- 02 为连续原完整 B64/AdamW 五步参考，原 compare SHA=`e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`，原类别/阈值字节不变；原名映射覆盖输出、损失、输入梯度、全部参数梯度/参数/delta、AdamW step/矩与 buffers。保留初始化后 mask RNG、原25批/mask/hash和归一化；额外参考初始化/恢复隔离 RNG；五步后释放参考，不保留全程模型快照。
- 每步 canonical 模型/AdamW 张量身份跨 rank 检查，不比较整个含 rank 元数据的 checkpoint 文件；保存/恢复代码核模型、optimizer、各 rank RNG、private mask 流/游标/身份，恢复不调用 optimizer.step。first5 失败不会进入第6步；optimizer 已提交计数先原子保存，失败阶段/尝试曝光保留。完整恢复、实际同步和全部模型参数的运行门槛仍 NOT_RUN。
- worker 在 Torch 导入前核当前 job/分配并绑定本域36核，实际 Torch36、全部相关 TID 边界、库映射及实际 KML 调用均有拒绝检查；参考和训练调用分列。双 worker 先 ready 后 PG120；父监督器发现失败停止所属双方，有界 TERM/KILL/回收；原子报告复用7个 R7 函数文本无漂移。Linux 真实进程清理尚未在本轮执行。
- 预算固定两域76分配/72实际/4保留、DDR总24576MB且limit同值/exclusive/HBM0；从同一 job 起点840执行、到870清理、到900收尾。更新上限25全局/50rank/5参考=55物理模型更新，训练1600独特帧与参考320额外观察分列；前5参考共存 HWM 不当纯 DDP 峰值，无同 job 单域对照不计算提速。

数学依据及固定 2.7.1 API 边界详见 [MATH_REVIEW_CRITERIA.md](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_review_20261106/MATH_REVIEW_CRITERIA.md)。00 回传的 C2 installed DDP Python 源 SHA=`480213c6546cf6c2d522357a59065d38afbaa16196dc8eabaadf752b5bdcae43` 已与 runtime contract 核对；本轮未在 C2 加载该模块，未冒称核验了当前计算 job 的 reducer 二进制。

冻结来源核验：02 包18成员/17源/12原文件复用，原数据三锚点与7个基线锚点无漂移；02 的7检查/190 tiny指标按已有回执核对，无重复完整测试。07 包21成员/20文件（19交付+源清单）及79份证据、18个参考绑定文件、7个 R7 函数均逐字节/哈希核验；Python LF/3.9语法通过。详见 [reference_review.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_review_20261106/reference_review.json) 与 [training_review.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_review_20261106/training_review.json)。

00 部署只完成**2026-11-06T09:37:47Z 当前快照**核验：36清单文件/37包成员无漂移，内嵌02/07包与当前冻结身份相符；全部26项 Linux 前置与模型共享840秒，reference检查在rank0选中36核上运行。审核消费者拒绝 FAIL、未完成 PASS 和缺 SHA 的 PASS（3项针对性负检查）。当时固定 S00_DEPLOYMENT_READY 未到达，现有 login receipt 对 prepare.py、run_job.py 两文件是旧快照，不能替代最终外包 Linux 核验。因此只绑定所见外包快照，不宣称最终部署就绪，后到 READY 也不改变本次 FAIL。详见 [deployment_snapshot_review.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_review_20261106/deployment_snapshot_review.json)。明确数值失败后无需占用剩余90分钟等待额度，更不占计算节点等待。

本窗口独立做过一次隔离 Windows tiny Gloo 检查：FileStore 25秒超时，停止后未重试，只有父日志保留，测试自动删子日志故根因不确定；OS逐命令行只读检查未见该路径 worker 残留。该检查只用 tiny 图、0 optimizer 更新，无真实语料/完整模型。详见 LOCAL_SMALL_DDP_RESULT.json / LOCAL_PROCESS_CHECK.json；不拿它替代07后来保存完整证据的严格失败。

固定审核 JSON 绑定代码、参考、外包快照、数据/config/本卡 SHA、资源及更新上限，完整输入列表见 FROZEN_INPUTS.json。主要包 SHA：07=`d032d67cd76eddbc372ab6f9dd51c8355c4bb1ef3e7469254c2549a3481623a9`，02=`df7275b06d8ee59cd88c0d17c04b0b64f63605ffa1c4410d3d02307ce848eec5`，所见00外包=`8d4fb023b99109850919b904561b0b228cdce50c607b9c26408adf90ce711434`。

S01 本轮0提交/0 SSH/0完整模型更新；没有收到实际 RUN_COMPLETE，真实前5门槛、25步、同步/恢复/清理结果审核为 NOT_RUN_NO_RELEASE。S00实时队列未由本窗口核实，不因本地无记录断言集群无 job。正式 split/subject 仍 UNKNOWN，无 val/test、效果或性能验收。仅写自身轮次目录及两份短状态，未修改作者源码、历史包/数据/阈值、协调文件或共享 Git。供唯一 Git 窗口按 ARCHIVE_SCOPE.json 精确归档证据；这不等于代码通过核验。
