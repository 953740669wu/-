# S01 夜间真实语料工程小试专项前置复核

日期：2026-11-06（Asia/Shanghai）；任务卡轮次20261105，固定目录不改名。
状态：**PASS_FOR_ENGINEERING_PILOT / PRE_SUBMISSION_REVIEW_COMPLETE / ACTUAL_TRAINING_NOT_YET_REVIEWED**。

## 1. 结论

本轮S01专项前置审核完成，无未解决阻断项。允许S00在提交前再次核实同一组身份、实际队列/唯一标记后，按任务卡直接执行已授权的唯一有限真实语料工程训练，无需用户转发或另等总协调在线。

仅工程协议ENGINEERING_REAL_CORPUS_PILOT_V1。工程小试不创建正式split，不构成数值等价/科学效果/泛化/正式性能/内存收益或生产验收；原R8正式门禁及DATA_NOT_READY记录均保持。S01没有提交作业、读真实NPZ、导入Torch或跑完整模型。

## 2. 具体交付身份

四类固定就绪文件已齐且实际内容/包/清单均核对；本次审阅的67个冻结输入在FROZEN_INPUTS.json列绝对路径/bytes/SHA。代码包29个成员/28源码、部署包27成员（26文件及空evidence目录）CRC和逐字节身份一致，无重复或不安全路径。

| binding | SHA256 |
|---|---|
| code_package_sha256 | `add690cf983d5902c78586101ee6250358380786a8c13aa209b0a024735835a7` |
| code_source_manifest_sha256 | `e4acbbcb604dc3afd22b462bbfc2c3e348108c32e004557b891de7e14978b7d2` |
| deployment_package_sha256 | `938f7df81f3f7fa8c61239f8041950e4eb47043e869bbbd5aad7be8e6d27359e` |
| descriptor_sha256 | `b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6` |
| interface_sha256 | `8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669` |

代码包71182 bytes，部署包135582 bytes。descriptor 12222 bytes；固定接口自首次发布未改。包、源码清单、descriptor、接口和ready记录均相互一致，review_gate使用上述五个binding，不接受“PASS”字符串或缺review_complete。源码清单及部署source index SHA也单独核验。

## 3. 数据、模型与工程/正式隔离

manifest准确锚定任务卡14300版：14300单元/1430000对/143case、3399057 bytes、SHA bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032。它是工程版本锚，未称正式语料重冻结或恢复11900版。S00登录侧原manifest前后SHA一致，119 cases.txt只作工程选样范围，seed2026选s0285/s0593，各8个16_adjacent单元，共1600帧；case不当subject。

descriptor/样本检查逐项核对case/unit/belt/placement/contact/NPZ与sidecar SHA/bytes，base_of_pair与states一致、shape/dtype/有限值/参考分母正值。工程loader在固定manifest重算同一选择，不允许失败后换样；读取前后再核源SHA。真实共享NPZ由S00有限读取检查，本窗口只审核其原始收据，没有冒称独立重读数据。

输入保持同unit/belt/pair行，原参考均值归一化*100，无epsilon/clip，训练样本image absmax只拟合一次；预期固定样本absmax=0.03546142578125，实际应用仍自行拟合记录。engineering_only=true，formal_split_status/subject_mapping_status=UNKNOWN，validation_status=NOT_RUN_NO_FORMAL_SPLIT；无val/test，不造split/mapping，旧正式CLI拒绝该描述。

18项原R8复制文件逐字节一致（其中13项关键运行文件）；engineering_training与原pilot_training的AST只差两处明确checkpoint协议标签，损失、优化器、保存/恢复逻辑无算法变化。完整Encoder37995777参数，原12层512维8头/native SDPA/KML linear，fp32/CKPT0、AdamW lr1e-4/betas(.9,.999)/eps1e-8/wd.01。无decoder/HBM/bf16/compile/微批/新attention。训练seed0、一次打乱、batch64，不填充重复末批，1epoch或200更新先到；当前规划25更新，连续复用一个AdamW，每批新mask。

初始暴露清单为SELECTED_RESERVED/NOT_STARTED；运行清单在模型前创建，逐单元记录读取/统计，forward前持久化可能消费帧，成功核状态并落步日志后确认消费。失败/中断保留in_flight，不伪造已训练；恢复探针另记前两帧、0额外更新。未来必须按真实subject映射追溯并排除工程暴露对象的最终测试，当前无无泄漏保证。

## 4. 必要检查与修订闭环

S02冻结证据14项本地夹具/小型native Torch36通过：8项工程门禁/范围/顺序/暴露、3项小型连续batch/原mean+AdamW/工程checkpoint零更新恢复、3项既有配对/零参考/cross-belt拒绝；CLI缺描述/正式入口拒绝工程描述发生于框架前。原测试并非真实完整Encoder或C2证据，本窗口未重复旧5315/全模型矩阵。

S01补充1个真实工程descriptor元数据正例、7个必要拒绝检查（正式协议、false engineering、伪造validation、第三源版本、subject伪造、重复unit、正式loader拒绝工程描述），均符合预期；无Torch/Numpy导入。另用冻结S00实际review_gate核具体binding正例及5种逐项错误SHA拒绝，无调度调用。

预读未发布的S00草稿发现旧S02_REAL_DESCRIPTOR接线错误；通过S01固定文件给出定位，S00在**首次S00_DEPLOYMENT_READY之前**改为S02_ENGINEERING_DESCRIPTOR/_SHA256，并补实际调用链测试。本窗口未改作者源，也未接受发布后热改。原发现/中间BLOCKED及修正收据保留；最终ZIP确实包含修正。

S00本地12项包装检查及Linux登录侧12项mock检查均通过；真实登录侧完成ZIP/解包/源码SHA、LF/AST3.9/bash-n、工程metadata/hash门禁，未导入框架、未训练。调度资源/进程操作mock通过不等于真实计算节点已验。

## 5. 唯一执行边界及尚待作业验收

单节点单NUMA、调度38个物理核、同域前36实际/末2预留；DDR24576MB且limit同值、exclusive、job900秒，retry0。整个外层Python入口从最初计时起共840秒，门禁30秒包含其中；共享清理TERM15/KILL15总30秒，最晚870秒，留30秒收尾，不是给每个子进程重新840秒。内层720秒后不再启动新更新，未完成必须INCOMPLETE。

唯一提交使用排他submit_once.marker，失败/超时/ID不明也不重试；实际RUNNING后用nonce/job/rawSHA的新鲜调度回传核主机、CPU、请求/实际内存及limit/exclusive/无retry。计算端查原生CPU拓扑/物理核/DDR；模型同PID框架前收窄selected36，框架后及每步/保存/恢复/发布查实际Torch36、非空全TID子集、真实KML/OMP/shim路径和SHA/GEMM调用。不用setter伪造现场36线程。

外层subreaper追踪所有自有后代，包括setsid/reparenting，发信号前核PID/start ticks，统一有界清理，不操作外部任务。收集成功/失败同样保留原调度、源包、命令/退出/时限/清理、步骤/loss分量和真实帧序、RSS、诊断和整体壁钟、CPU/KML、checkpoint路径/bytes/SHA/零更新恢复、暴露原件与未知范围。权重远端保留不进Git。

以下尚无本轮实际计算节点证据，必须纳入唯一job结果复核：原生授权与38/36/2边界、实际Torch36/KML/GEMM和全TID、真实完整Encoder有限训练与有限loss/状态、最终checkpoint/恢复、全部自有PID清空/调度终态。若未实际触发TERM/KILL，不能称失败清理分支实测。任何异常、SOURCE_CHANGED、资源错、NaN/Inf、退出非0或超限停止、不调参/重提/扩样或预算。

## 6. 当前结果与后续

本文件是**前置技术复核**，没有工程训练结果。S00可读固定S01_REVIEW.json，核该原件SHA和五项binding/资源完全一致后执行唯一job。S01在本轮原90分钟等待期限内可读RUN_COMPLETE再作结果复核；未到则交已完成前置复核，不声称后台继续。结果复核另存ENGINEERING_RESULT_REVIEW.json，不热改已发布的S01_REVIEW身份。

## 7. 证据

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\overnight_engineering_20261105

- interface_review.json、INTERFACE_FROZEN_COPY.json：接口/预算。
- data_review.json、audit_data_delivery.py、S00_FROZEN_DATA_READY.json及descriptor/初始ledger副本：固定数据收据。
- code_review.json、audit_code_delivery.py、frozen_code/：代码ZIP/SHA/AST和最小独立门禁检查。
- deployment_review.json、audit_deployment_delivery.py、frozen_deployment/：部署ZIP、Linux收据、binding及资源门禁。
- preliminary_findings.json、PRE_FREEZE_REVIEW.json、preliminary_source_review.json：预冻结问题与原始定位。
- FROZEN_INPUTS.json：具体审核输入身份；WAIT_LOG.jsonl/REVIEW_PROGRESS.json：有限等待。
- S01_REVIEW.json：原子发布的唯一专项执行复核记录；不代表科学/性能接受。

## 本轮结束状态（2026-11-06T00:05:18.792363+08:00）

S01前置专项已完成并发布固定PASS；审核原件SHA256为`da7e84289a905466bc5bfdaa1e9cf7a1b80c41ace0cfaae63488d11ae8f6e408`，发布后未更改。结束前再核67项冻结输入仍全部一致。

当前RUN_COMPLETE.json尚未收到，未做本次实际工程训练结果审核；按任务卡允许，交已完成前置复核即结束，不为等结果增加作业，也不表示后台继续守候。本窗口新增job=0/模型运行=0；未直接查询远端队列，不断言S00此刻没有活动job。00负责唯一作业执行/终态及清理，08整理结果。若后续另行恢复S01，先读原job和RUN_COMPLETE，不重复提交。

本轮阻断问题为空；先前draft环境变量问题已在首次部署就绪前闭环。正式效果、split、数值等价、性能与内存收益均未接受。精确待Git范围见ARCHIVE_FILES.json；没有操作共享暂存、提交或推送。
