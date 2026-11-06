# 02无候选提案独立审核与最小取证规格

本卡仅交原01窗口；已发布不等于接收/启动。02提案NO_JUSTIFIED_CANDIDATE、候选0个；协调已核36唯一来源/交付SHA并定向读冻结kml_ops分派/反向。当前无实现或实验许可，原训练FAIL/阈值保持。

## 本轮目标

独立审核02的Tiny→完整Encoder/KML路径映射及“不足以选择单个fp32改动”的结论，把M01–M05区分为真正需要的新证据、已有证据可回答项、仅需保留的历史限制。若确需新证据，只写一个最小、可审核的取证规格，不执行、不实现工具。

## 参考文件

以下以E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work为根。
1. 自己SESSION_STATUS/ROUND_DELTA及本卡。
2. S02/real_dual_ddp_minimal_candidate_proposal_20261106/{PROPOSAL_READY.json,PROPOSAL.json,evidence/SOURCE_INPUTS.json,evidence/R11_EXISTING_CALL_METADATA.json}。
3. S02/real_dual_ddp_reference_20261106/{baseline/kml_ops.py,baseline/s4_models.py,tests/check_equivalence.py}仅核相关分派/反向/原比较门槛。
4. 自己real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_REVIEW.json、real_dual_ddp_evidence_closeout_r1_20261106/EVIDENCE_CLOSEOUT_REVIEW.json及原最终FAIL。
5. COORDINATION/REAL_DUAL_DOMAIN_DDP_START_20261106.md：保留数据/参考/模型契约，不借用其旧执行授权。

## 完成标准

- 先核READY及来源SHA。只写S01/real_dual_ddp_proposal_review_20261106/及自身短状态；不修改02提案/冻结代码/原比较器或历史FAIL。
- 独立核Tiny原生路径与full val/head_coarse原生分派、其它直接KML路径，检查dX/dW/db、rank32静态推导和R11 B64既有149计数的证据范围。无须重做旧数值或矩阵。
- 对NO_JUSTIFIED_CANDIDATE给ACCEPT/REVISE及具体原因；不同意则指出源字段/代码和最小更正，不自行制作候选。
- 逐项判断M01–M05：哪些证据对选择修改点必需，哪些只是运行/历史限制。历史无法恢复项不自动要求补跑，也不把有限归档接受解释为数值或运行通过。
- 需要取证时，最多一份MINIMAL_EVIDENCE_SPEC.json：写明一个可证伪问题、选用的固定首批/参考/归一化/mask及原阈值、必要输出与匹配身份、对X/G/前向/dX/dW/db的定位方法、最少计算路径、拟议资源/超时/清理/保存上限和失败即停。明确哪些元数据足够、哪些张量必须取得，避免完整模型全层全步副本。
- 原完整B64/fp32仍是正式参考，顺序32+32若出现只能作定位控制，不替代参考；已有Tiny失败保留，不自动再复现一次。规格不包含优化器训练、性能矩阵、试tile/精度、完整25步或DDP自动重试。若某项无法在现有约束下取证，明确NEEDS_NEW_EXECUTION_AUTHORIZATION/具体缺项，不擅自批准。
- 核查“拟议取证”是否与旧小DDP失败门槛冲突，写清仅用于定位的独立边界；旧FAIL继续有效。若不能给出既有约束内可行规格，交BLOCKED_SPEC_WITH_REASON，不能用更换参考/放宽阈值解除阻断。
- 输出PROPOSAL_REVIEW.json、必要的MINIMAL_EVIDENCE_SPEC.json、简短REPORT及精确归档清单；更新自己的短状态/六行摘要，给绝对路径。
- 本轮0模型/收缩/测试/DDP/SSH/集群/安装/提权，不运行作者脚本，不导入Torch或反序列化张量，不新查询进程。无监视或90分钟等待。

## 接续

02/07/00/08/Git待命。01结果到后协调明确选择：现有证据足够则唯一最小候选方案；证据不足则审最小取证规格及执行授权边界；不能执行则向用户列具体必要条件。不以静态审核替代实际C2数值证据。02提案和本轮审核待成套核验后另列Git精确批，不自动追加已完成99批。
