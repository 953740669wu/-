# S08 双域DDP：准备完成，当前版本审核拒绝，未运行

状态：PREPARED_ONLY_BLOCKED_FINAL_S01_FAIL。S01于2026-11-06 17:39发布最终decision=FAIL、review_complete=true、execution_authorized=false；本版本不获执行放行。S08结束当前依赖等待并待命，不在本卡重试、改阈值或提交job。

拒绝理由B01_LOCAL_STRICT_NUMERICAL_FAILURE：冻结的本地小B64/双rank比较，在原阈值下13项中3项失败。以下是本地原记录，不是C2完整Encoder/DDP的实际运行结果：

| metric | max_abs | l2_relative | passed |
| --- | --- | --- | --- |
| val.weight | 1.91479921341e-05 | 9.41019108807e-05 | false |
| pos.weight | 1.91479921341e-05 | 9.41019108807e-05 | false |
| tf.weight | 3.72380018234e-05 | 0.00011428691335 | false |

原门槛保留。没有依据把这个版本称为数值通过，也不能将本地小模型失败扩大为C2通信失败或已实测完整模型训练失败。07冻结候选及原失败证据均不改。

本轮S08已完成：按新接口准备标量读取适配与Markdown/JSON输出，复用旧distribution/clean且不改旧PILOT门禁；5个LOCAL_FIXTURE通过；15项训练包/来源/字段核对通过；12项最终拒绝身份/原因原件核对通过。元数据和夹具通过均不替代真实训练门槛。

收尾已收到S00 RUN_COMPLETE及精确analysis_inputs，终态为NOT_RUN_S01_REVIEW_FAIL_NO_JOB。DDP_SUMMARY.md/JSON仅绑定这份未提交终态，实际完整模型更新/本次训练帧均0，所有C2训练阶段NOT_RUN；不是实际训练摘要，不拿准备或夹具填充真实结果，也不报告计划25/50/5或1600帧已完成。

S00目录内已收到的S01_REVIEW与作者最终拒绝逐字节相同，SHA256=f933a3af02a9362b9bce854935cbb18eecebfb38dd761805da163b48ff110f74。S00已发布进度的快照声明new_jobs=0、active_job=null、ready_for_release=false；该快照保留于S00_PROGRESS_OBSERVED_COPY.json，S08未独立查实时队列或推断其它窗口作业。

旧工程16单元/1600帧曝光要求保持；未获得新的实际训练/参考曝光账本，不把旧曝光清零，也不将S00准备读取冒充模型训练或推断为未曾读取数据。独特训练帧、累计观察、失败可能使用范围将在后续真正执行版本按原件核对。

无同job单域对照：speedup/scaling_efficiency/steady_state_gain=NOT_MEASURED。无正式subject/split/val/test，无科学或性能接受。

当前等待结束原因是最终审核拒绝，非90分钟超时；前台等待约47.5分钟，原上限18:26:06+08未用满。会话结束后没有后台监视或S08活动job。

下一步：协调对保留的本地数值失败另定义诊断/新版本与审核，原批量/原阈值不自行更改；S08保留本次准备，等待新具体任务。S08未SSH、训练、读取NPZ或权重、操作共享Git。精确归档见ARCHIVE_FILES.txt；准备与拒绝原件绑定见SUMMARY_READY.json、STOP_POINT.json。
