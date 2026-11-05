# S01 R5：候选确认与首次完整启动小试复核

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW / FIRST_STARTUP_FAILED_BEFORE_RUNNER / LF_PACKAGE_IDENTITY_CONFIRMED / FULL_MODEL_NOT_RUN**。

## 1. 结论

R2五个候选源文件身份已确认不变，S00当前LF修正包及14项清单全部核验。首次job2026356实际返回FAILED、jobExitCode=2；错误发生在包装器第3行的CRLF选项解析，尚未到达runtime_preflight、runner或模型。不能把这次作业记成模型/运行器启动通过，也不能把查询命令返回0误当作作业退出0。

当前LF修正版与失败包只差包装器CRLF→LF及嵌入清单哈希；修正版尚未重跑。本轮只读S00证据/包，在S01独立补充目录留存快照与结论，没有改共享/接受代码或重新提交作业。

## 2. 前置条件与执行范围

已读最新STATUS、PILOT_REVIEW_20261104、ROUND1_ACCEPTED_FILES、S00计算环境报告/compute_environment_verified、CLUSTER_EXECUTION_PLAN、S00包和实际作业证据。最新环境证据已在job2026223/cn21417真实导入torch2.7.1+cpu、numpy1.26.4；旧R4报告中的“解释器未验证”已由S00新增证据补齐，但该已结束作业不能复用为本次allocation。

接受候选仍为S01_LOCAL_RUNNER_R2_20261104。接受根报告SHA：`e0a840aa4552fc52f5d6748591c6d3b8c5b4d1d651540a178ca29b1059fb8420`。

| 文件 | SHA256 |
|---|---|
| run_node16.sh | `aaac8557b00abbf68a0e296e7119c0150c3fbfd467c42d132035ed69f929fd5f` |
| runner.py | `692113888fab4ac23c0188f39731ceea0f0fec1a8ef09f25cee872515ba7dd0b` |
| s4_models.py | `512dc202e4c0d60363b57317ed612694b80a4d5d3467740ed582bcf600bf1d92` |
| kml_ops.py | `e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26` |
| legacy_inputs.json | `24df1ad655fa3263efaf1ec8a721074fdfbae15fcb1d054b30d88bf5b9734835` |

版本链：

| 包/包装器 | SHA256 | 本次认定 |
|---|---|---|
| 总协调早先准备包 | 1765cce6e9b3bacbdf23e3d30191afe8db9ae5fc7c3b95273292d1a4bc9b378c | 旧审查版本，不作为本次作业执行身份 |
| job2026356实际包 | 5bb0a6718ec8ae3eb794e7f05f0faae9addd22342df0253833234320427a7616 | 已执行并在包装器失败 |
| 失败包装器 | d9d37eedb0ab30754754418aa9397fd53a6f2a585e329f967a23520c288eda80 | 31个CRLF |
| 当前LF修正包 | 747f9c36354136afa3383a3d836c7e3db7568a043d1712fb2f03765068b4ec5e | 身份/全部条目已核验，未执行 |
| LF修正包装器 | 72ba04253bc4b68446d642a70bcc0571ee926b71bc81e553c1a385d91dc1709f | 与S01保存的仅LF转换建议逐字相同 |

包共15条目，PILOT_MANIFEST约束14项，自身为第15项。对冻结的失败包与修正包逐条比较，仅pilot_s01_startup.sh和PILOT_MANIFEST_S00.json变化；接受候选5文件没有变化。所有包与清单已冻结在本目录snapshot，避免随S00活动文件继续改变后混用哈希。

包装器的新目录约束接受 `/home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S01_*/payload`，与实际job路径一致；S00旧计划中的S01/PILOT示例不可直接套用新版包装器。两者都在当前账号自有目录，未写共享项目owner目录。

## 3. 环境、复现方式与成本

| 项目 | 实际证据 |
|---|---|
| job/node | 2026356 / cn21338 |
| 起止 | 2026-11-04 21:46:29–21:46:30 +08，约1秒；不是模型计时 |
| 调度终态 | FAILED，jobExitCode=2；调度exitCode=10001、exitMessage包含errCode2 |
| 查询退出 | djob_exit=0，仅表示查询成功 |
| 调度资源 | exclusive=true，申请/分配38CPU、24576MB；resLimit.mem=24576，hwThreads=0-37 |
| 资源验证边界 | 包装器在检查之前失败；没有本次Python进程affinity、NUMA实测或cgroup硬限证明 |
| 实际执行路径 | /home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S01_20261104T134538Z/payload |
| 失败后状态 | model_execution=NOT_REACHED；S02_job=NOT_SUBMITTED；retry=STOPPED_AFTER_FAILURE |
| 本窗口动作 | 无SSH、无调度提交、无模型计算；仅本地核验及Git Bash诊断 |

预期小试不变：单域38CPU/24GiB/900秒，16-pre+dec B32/fp32/KML、CKPT0/HBM0、3轮REPS1。原预热/完整前反向与AdamW不改变。包装器780秒后TERM、15秒后KILL，每轮180秒、barrier120秒。任务结果不作为正式性能轮次或科学训练正确性。

失败日志由S00保存，核心文本为：

```text
pilot_s01_startup.sh: line 3: set: pipefail
: invalid option name
```

原始CRLF字节快照与shell_bytes_cr_count=31共同支持包装器换行错误判断。修正仅规范LF，不修改候选算法、参数或资源。

## 4. 失败处理、退出状态与结果完整性

| 检查 | 本轮结论 | 接受边界 |
|---|---|---|
| 候选5文件/包身份 | 接受清单与ZIP逐字节一致；新包14项清单全匹配 | 候选身份通过 |
| 失败传播至调度器 | job终态FAILED且jobExitCode2，S00记录NOT_REACHED并停止 | 未将包装器失败误报PASS |
| 查询返回码解释 | djob_exit0与jobExitCode2分开记录 | 不能把查询成功当执行成功 |
| 本次wrapper/runtime预检 | 在第3行失败，预检未到达 | 不能复用2026223预检冒充本次预检 |
| runner/subprocess实际链 | 尚未到达 | 本次没有验证真实模型PID/退出/超时清理 |
| 模型manifest/每rank JSON/状态/summary | 未随此收据收到；日志表明模型未到达 | 不补造文件、不计算部分域吞吐 |
| 输出目录是否为空 | 收据未提供目录清单 | 不把“未收到”写成独立验证的“0文件” |
| 独立重算summarize | 没有真实模型run目录可重算 | NOT_APPLICABLE；不预写PASS |
| Windows Git Bash检查 | 失败/LF快照的-n和单独set行均返回0 | 不能用本地兼容解析替代实际Linux执行；本次以真实job失败为准 |
| 输出/loss/梯度/optimizer/state_dict | 未执行模型 | 科学数值均未运行 |

本轮不能把四项Linux清理检查的既有PASS解释为真实模型故障处理已全部验证；R4证据与首次模型作业分开记账。

后续正常单域三轮应精确提供3个结果JSON和3个逐rank状态JSON，rank从manifest实际domains取，不预设d0。需检查相同run_id/host/rank/PID/时窗、配置/输入/源码/库、线程和实际affinity，并用接受runner独立重算对照保存summary。缺域/坏或旧数据/非零退出/超时均不得PASS，完整但UNSTABLE原样保留。

接受runner严格比较模型记录的sched_getaffinity与manifest；若遇不一致，保留实际线程/绑定/OpenMP证据定位，不能临时删除检查求PASS。该项是需要观察的诊断，不是已经发生的模型故障。

## 5. 性能与内存

本次模型没有启动。约1秒只表示调度记录中的失败作业墙时，不能产生训练步、吞吐、内存或HBM结论。

| 范围 | 结果 |
|---|---|
| 16-pre/dec完整模型 | 未到达，未运行 |
| 三轮REPS1结果/波动 | 没有实际结果，不能PASS |
| DDR峰值/内核硬限 | 未测，不能以24576MB分配数充当峰值或独立cgroup验证 |
| HBM/CKPT/32电极/四域/整节点 | 未运行 |
| 正式数值/性能/第二主机/DDP | 未运行 |

LEGACY_TIMING_ONLY保持，16电极目标错配仍不能作为科学正确性参考；不改变数据或直接整合S02。

## 6. 结论与下一步

确认R2候选身份及当前LF修正包身份。首次完整启动小试结果为 **FAIL_BEFORE_RUNNER**，不是模型或性能通过。修正包应保留新SHA与新唯一运行目录，不覆盖/删除失败证据；由S00/总协调按失败停止约定决定是否重新排期，本窗口不自动重试或扩大。

当前尚无实际模型结果可完成逐rank/完整计数验收。下次回传需含新job终态/资源、包装器退出、本次预检、完整run目录manifest/状态/结果/日志/summary及缺失清单；若外层超时，仍保留真实退出码及清理证据。收到后继续在本补充轮新增RUN_REVIEW结果，不把旧作业记录重命名为新运行。

## 7. 证据索引

补充根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z`。

| 产物 | 绝对路径 |
|---|---|
| 给S00的版本/结果确认 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\CONFIRMATION.md` |
| 本复核报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\RUN_REVIEW.md` |
| 机器可读候选/作业复核 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\CANDIDATE_CONFIRMATION.json` |
| 首次真实job冻结收据 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\first_job_2026356.json` |
| 首次小试请求 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\first_pilot_request.json` |
| 失败包/清单快照 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\S01_pilot_prepared.zip`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\PACKAGE_MANIFEST.json` |
| 当前LF包/清单快照 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\S01_pilot_LF_corrected.zip`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\PACKAGE_MANIFEST_LF_corrected.json` |
| 原CRLF包装器 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\snapshot\pilot_s01_startup.sh` |
| 仅LF建议/最小diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\proposed\pilot_s01_startup.sh`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\proposed\wrapper_lf_only.diff` |
| Windows Bash诊断 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\bash_syntax_review.json`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\wrapper_option_line_review.json` |
| 全补充SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R5_STARTUP_CONFIRM_20261104T134751535165Z\ARTIFACT_SHA256.txt` |

没有改S00文件、根接受文件或发送跨聊天消息；该确认文件可由用户交S00/总协调使用。实际修正由S00完成，本地建议仅供对照。所有判断针对已冻结证据及明确SHA，不跟随活动文件自动沿用旧结论。
