# S00：2041165 S07 R4单次事件诊断

2026-11-05，Asia/Shanghai；轮次20261105T104153Z；任务已按失败停止边界完成收集，无重试或补跑。

唯一job2041165/cn21338为FAILED/jobExitCode=1。原授权交接、28项Linux检查及环境检查通过，normal初始化失败，crash/collective-timeout/watchdog全部NOT_RUN。双方及父监督完整JSONL原文件已回传，共15/25/10行有效事件；原诊断清单为DIAGNOSTIC_EVIDENCE_INCOMPLETE，保留未闭合区间，没有改写为诊断完整或通信通过。

## 关键阶段观测

以同节点supervisor_begin的monotonic_ns为0；完整逐行时间线见本轮TIMELINE.md及REVIEW.json。下表仅摘录观测，不替代全文件。

| 阶段/事件 | rank0相对秒 | rank1相对秒 |
|---|---:|---:|
| worker_ready | 0.726125 | 0.806368 |
| torch_import_begin | 0.755905 | 0.818202 |
| torch_import_end | 16.383994 | 8.874564 |
| distributed_import_end | 16.387362 | 8.877749 |
| runtime_metadata_begin | 16.388766 | 8.878719 |
| libtorch_cpu.so SHA开始 | 16.420449 | 8.896991 |
| libtorch_cpu.so SHA结束 | 未记录 | 9.291490 |
| runtime_metadata_end | 未记录 | 9.393871 |
| init_process_group_begin，参数5秒 | 未到达记录 | 9.401416 |
| worker_error: RuntimeError: Wait timeout | 无本地错误记录 | 15.924755 |

父监督事件：spawned rank0/PID310132于0.052818秒，spawned rank1/PID310133于0.109341秒；16.567950秒发现child_failed（当时exit_codes=[null,1]），16.569892秒成功向rank0自己的进程组发送TERM/15；16.672296秒回收rank0/exit -15，16.674224秒回收rank1/exit1，16.676003秒supervisor_end/all_reaped=true。正常case未触发原30秒父deadline；S00外层run_checks_receipt也无超时、remaining_live=[]。

本次已经观察到两rank进入初始化前的准备阶段明显错开：rank1的超时错误记录早于rank0的Torch导入结束记录。rank0确实出现了Torch及distributed导入结束事件，不能把本次rank JSON最后before_framework解释为没有完成导入。日志与本次初始化前启动不同步相符；是否解释旧2040233、导入阶段为何不同步以及底层缓存/I/O/调度原因，仍须S07原会话分析，未在本轮证明。

rank0在记录libtorch_cpu.so SHA开始后约0.149秒被父监督发送TERM，故缺少其SHA end不能说明哈希永久卡住或哈希本身导致本次超时。rank1的init begin到worker_error记录约6.523338秒，是包含日志/I/O及调度的观测区间，原pg_timeout仍5秒，没有扩预算。

rank0有3项库SHA的开始/结束事件，进入第4项libtorch_cpu.so后没有结束；rank1的6项库SHA及runtime_metadata结束已记录。事件end未附hash值，rank0在backend_info返回前被终止，最终rank JSON未发布完整runtime字典；不能称rank0完整库身份或导入后CPU/TID实测通过。原始路径、rank1库身份和全部事件字节都保留。

## 完整性与未运行项

三流共50行均可解析、时钟字段/单流monotonic顺序通过，原文件均以换行结尾。本次未见TRACE_WRITE_ERROR，未检出截断/非法JSON行。按已核原清单，rank0 runtime_metadata及libtorch_cpu SHA区间、rank1 init_process_group区间未闭合，因此诊断仍标不完整；该标记不能单独认定丢行、阻塞或故障根因。原事件没有全局序号，不排除不可观测的整对事件缺失。

normal未完成进程组初始化，没有all_gather身份、broadcast、all_reduce结果，checks.json为FAIL/cases=[]/normal communication failed。后三case没有生成目录，未运行、不算故障注入通过。此次仍无小张量通信接受，更无同步训练、吞吐或原故障修复接受。没有单跑normal、补采样、扩大超时、修改候选或重提job。

## 去重、身份及资源

网络最初在认证前中断/超时；恢复后遇新主机密钥，先停止认证。用户确认新指纹并明确授权此C2入口各指纹信任后，精确核对SHA256:l0HMdi2o8v4ZvRridH8xQrZSCNL8plN+e+Ir5A1SVxQ，另存已确认pool并保留旧记录，实际连接仍用StrictHostKeyChecking=yes。信任范围仅10.44.9.4，未修改其它主机设置，认证信息未落盘。连接恢复是传输操作，不是实验重试。

从login05只读查当前队列及所有S07_INIT_DIAG_R4_*目录/提交记录，确认无已有本轮任务后才创建新目录并上传已核外包。REMOTE_DEDUP.json和queue_review_before_submit.raw在完整包内；其它账号job不操作。目录标签104153Z来自本地准备时间，不当作作业启动时间。

外包62715bytes/14文件+空目录，SHA=b20e248be761db6c645fdbcebbbfc61d083642bb0e1d959eb1a0fcfa9b304284；内包31262bytes/12文件+空目录，SHA=af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45。远端清单/原样prepare及登录侧14部署+25交接标准库检查通过，再由原submit_once只提交一次、RUNNING后原publisher单次成功；没有临时修包。

计算端原nonce/request/raw/ready、新鲜度、CCS_JOB_ID、主机/76核/内存/时限授权及两域逐核sysfs核验通过。单节点两个完整38物理核域，每域选36留2，总DDR24576MB且limit同值、exclusive/HBM0，job300秒、consumer统一270秒含交接/检查，原pg5/case30秒不变。具体域号和全部CPU列表保存在job_evidence/verified_allocation.json及REVIEW.json，不复用旧job授权。

同job6诊断+6身份+16原检查共28项Linux全过、无跳过，environment检查exit0，实际Torch2.7.1+cpu/Gloo构建可用、原解释器和库路径、无LD_PRELOAD。该环境命令按原实现为单线程导入，不是两域算子实测。normal两rank已按各自36核绑定，rank1记录实际Torch intra-op=36；rank0未到该测量/导入后TID检查点，不能声称双rank的实际Torch36都已实测完整。

## 终态、成本与交付

job于2026-11-05 19:04:00—19:05:21中国时间运行，起止81节点秒，调度usage也为81秒；maxRetryCnt/currentRetryTimes均0。两worker直接子进程已回收，原监督/S00外层清理回执和调度PID字段`-`一致，无活动S00 job。旧已知20job/964秒，本轮后已知21job/1045节点秒。SSH/SCP正常退出，本轮不重跑02/06、不扩模型训练。

本轮证据根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s07_r4_diagnostic_20261105T104153Z`。

- JOB_2041165_full_evidence.zip：197610bytes/82文件，SHA=f8213b5946d756675e2b890597dd930644346c1c77f3cba2efbedb982038248c；JOB_2041165_receipt.json为远端原回执。
- received/为完整解压原件；COLLECTION_S00.json有81项原bytes/SHA/远端mtime_ns，全部核验通过，82项ZIP与解压字节一致。mtime以元数据保留，不冒称Windows解压时间等于远端原时间。
- 原三流：received/payload/checks_current_job/normal/{rank0.events.jsonl,rank1.events.jsonl,supervisor.events.jsonl}；同目录保留原rank JSON/log、manifest、commands及summary。DIAGNOSTIC_INVENTORY.json、checks.json保持原失败/不完整状态。
- job_evidence/保留28项日志、环境/授权/逐域回执、全部逐step开始结束/退出/清理，包括summary未列入成功steps的run_checks失败独立receipt；调度终态、提交/发布及原包/源也都在完整包内。
- REVIEW.json和TIMELINE.md为原件档案复核/阶段摘要；candidate/audit_s07_r4_diagnostic.py只读原件及重放原诊断清单，不执行框架/通信测试。原包/候选及受保护旧失败/2040363结果SHA均未变。

已更新自己的SESSION_STATUS.md、ROUND_DELTA.md及本轮ARTIFACT_SHA256.txt。仅交本轮变化及证据给总协调/S07原会话，不自动修复或追加实测。
