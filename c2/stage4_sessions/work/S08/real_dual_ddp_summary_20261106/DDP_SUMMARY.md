# 首次真实双域DDP：未提交终态摘要

**NOT_RUN_S01_REVIEW_FAIL_NO_JOB。** S00已交未提交终态；S01对具体冻结版本最终FAIL、review_complete=true、execution_authorized=false。本轮没有真实C2模型训练结果，不将准备或本地小模型结果当作已执行双域训练。

| 项 | 00终态记录 |
| --- | --- |
| job | job_id=null / NOT_SUBMITTED |
| 新job / 活动job | 0 / null |
| 新增节点秒 | 0 |
| 全局更新 / 两rank物理更新 / B64参考更新 | 0 / 0 / 0（本轮未提交的完整模型工作量） |
| 完整模型物理更新总数 | 0 |
| 独特训练帧 / 参考语料观察次数 | 0 / 0（本次C2模型训练范围） |
| 实际模型报告 / metrics / checkpoint / 曝光账本 | 均为空 |

Linux26前置、C2资源/环境门禁、小DDP、完整B64 strict5、继续至25步、实际KML/CPU训练证据、保存恢复全部NOT_RUN_S01_FAIL_BEFORE_JOB。调用耗时、同步等待、最慢rank、参考共存/后段RSS/HWM均NOT_RUN；不补0耗时或用旧结果替代。未创建compute worker，清理为NOT_APPLICABLE_NO_COMPUTE_WORKERS，不称训练清理实测通过。

未获放行原因：B01_LOCAL_STRICT_NUMERICAL_FAILURE，冻结的本地小B64/双rank比较13项中3项在原阈值下失败，原记录如下。它不是C2完整Encoder的数值结论或通信失败归因。

| metric | max_abs | l2_relative | passed |
| --- | --- | --- | --- |
| val.weight | 1.91479921341e-05 | 9.41019108807e-05 | false |
| pos.weight | 1.91479921341e-05 | 9.41019108807e-05 | false |
| tf.weight | 3.72380018234e-05 | 0.00011428691335 | false |

每域32/全局64、每域实际36核/总76分配72实际、25全局/50 rank/5参考/总55上限、1600独特训练帧+320参考观察均为**计划值**，本轮没有实际执行这些工作量。原数值门槛、原基线与冻结失败包不改，不重试、不扩预算或静默切换参考。

旧工程16unit/1600帧的历史曝光要求保持。本次未生成模型训练曝光，不将历史账本清零；S00准备读取与原训练曝光不混算或声称未触数据。checkpoint未产生，S08未读取任何NPZ/权重。

提速、扩展效率、稳态收益均NOT_MEASURED；无同job单域对照，无正式subject/split/val/test、泛化、科学或性能接受。

来源核对：16项本次终态/绑定/拒绝/空报告/未运行阶段核对通过；S00 review副本与S01最终原件SHA一致，训练包和READY绑定一致。源path/bytes/SHA与精确analysis_inputs见NO_RUN_INPUT_VERIFICATION.json及同名JSON。S08仅核本地已收原件，没有独立SSH/队列查询。

准备增量：5个LOCAL_FIXTURE通过；15项冻结训练元数据/字段核对、12项最终拒绝身份核对通过。这些不是实际训练通过。预备读取器summarize_ddp.py保留给后续真正有运行原件的版本，本次不把未运行交接强行喂入rank结果解析器；STOP_POINT保留等待与拒绝过程。

当前依赖路径因最终FAIL结束，S08待命，无后台监视或集群job。后续诊断/新修订由协调另定义，不能在本卡豁免失败或重提。精确归档见ARCHIVE_FILES.txt，交接见SUMMARY_READY.json。
