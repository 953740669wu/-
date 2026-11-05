# S00续接：S06首次job预检终止，S07执行层已准备

2026-11-05；S06_2039859_TERMINAL_DEPENDENCY_PREFLIGHT_FAIL / S07_WRAPPER_READY_FOR_COORDINATOR_REVIEW。

按指定顺序读取自己的状态、增量、总任务表和AFTER_MEMORY3_S06R3_NEXT.md的S00节，再核对本地最新文件、Git记录、原包、旧失败和执行层。只操作S00目录，没有操作共用Git暂存区或其它任务目录。

## 续接核对与活动job

本地HEAD为e4a8645；短总表仍引用51d4089，不能作为当前提交或作业证据。原会话已留下candidate/run_s06_r3_job.{py,sh}、candidate/bounded_step_s06.py，以及evidence/s06r3_s07wrapper_20261105/{ROUND_REQUEST.json,EXECUTION_FILES.json}。初查本地该证据目录没有submission/job_id/调度终态原件；随后远端确认原会话已经提交，未因本地缺记录而重提。

首次非交互SSH检查通过节点可达/主机密钥校验，但缺少密码连接，认证被拒绝。收到用户提供的认证后，以原账号、原节点及已确认known_hosts严格登录login02，先只读核当前账号队列、S00远端专属目录、提交记录和实际终态。认证信息未写入项目文件或报告，没有更换密钥。

确认原会话job **2039859 / cn21341 / FAILED / jobExitCode=1**，调度PID字段为`-`，当前活动队列无该job。唯一匹配远端目录为`/home/share/dengqingtian/opt/stage4_sessions/S00/S06_R3_FIRST_20261105T084500Z`；提交标记及submission/job_id齐全。远端不存在S07_R2_TWODOMAIN_R3_*目录。本续接提交0个job、重试0次；S00本轮相关job已终态，无活动S00 job。账号中其它任务的job未触碰，不据此声称整个账号队列为空。

原job于2026-11-05 16:37:41—16:37:43（中国时间）执行；分配38核0—37、所选36核0—35、保留36—37；单CPU-bearing DDR NUMA0，物理核siblings逐项核对；8192MB且limit同值、exclusive=true、660秒、外层执行640秒/清理10秒，maxRetryCnt/currentRetryTimes均0。登录端原始djob查询、原子request/ready交接及计算端原生job/host/affinity核验成功，CPU/DDR回执齐备。选定36核不等于已经测得Torch36或实际算子计算。

随后S00执行层在依赖预检断言`required executable: /usr/bin/g++`处停止，SUMMARY为FAIL_STOP_NO_RETRY、steps=[]、job.log为0bytes（异常由包装器捕获写入SUMMARY）。这只证明该节点本次作业环境下该绝对路径不可执行，不能推断所有编译器缺失。依赖身份汇总文件尚未写出，也没有实际Torch版本/线程/库加载验证。本轮没有寻找替代编译器、安装或切换环境，更没有重提。

两种标准库启动各26项全部未运行；imports、pointwise、conv、block、kml-explain、kml六段全部NOT_RUN。没有probe结果、TID快照、实际Torch36/compile、数值或计时结果。原探针子进程尚未创建，因此无逐段退出/清理回执，不能把缺失记为通过；调度终态PID清空。失败属于S00对固定编译器路径的运行前提检查，尚无S06候选失败证据。

节点成本同时保留两种原值：UTC起止相差2秒，调度usage.wallclockDuration=1秒。按原报告累计起止口径，此次增加1个job/2节点秒，已知累计17job/766节点秒；不以调度coreHours字段推算探针耗时。SSH及SCP连接均正常退出。

S06原包仍33571bytes、14文件，SHA256为0aa9bbfe2c7f7bc102da0b4487aba301afbfdce14eeb259f3a9b2b6056162f5c。既有EXECUTION_FILES.json未改，其scheduler_handoff.py是续接前版本，SHA=ca8c7996e14f86d0d497dce912d9af3e829565844826ef69cb88a111182f6e1f；该精确版本另保留于s07_wrapper_r3_20261105/evidence/resume_before/scheduler_handoff.py。下面的新S07 helper不冒充该旧执行清单中的字节。若远端已有S06作业，不改它使用的执行文件。

## S07本轮交付

在原会话已有的新目录s07_wrapper_r3_20261105完成执行层修订。计算节点不再source登录profile或调用调度CLI；登录节点用现有djob查询当前job原文，以计算端现场CCS_JOB_ID、主机、affinity和新nonce绑定请求。request、原始分配、查询回执及ready各先完整写临时文件、flush/fsync、原子替换，ready最后发布。计算端有界等待30秒，核新鲜度、job/RUNNING/exclusive/时限、请求/原文SHA、单节点主机、CPU清单及内存申请/limit；之后仍执行冻结CPU36/sysfs及R2父/worker身份检查。原生CCS_JOB_ID不从JSON赋值，Torch/worker在授权核验后才启动。

续接只增加6项有意义的检查，以及查询失败/超时证据留存修补：原19项先复跑通过；扩展后25项中2项先失败，暴露非零/超时未保存stdout原件；修补后25项全通过。查询失败/超时保留命令、退出或超时回执、stdout/stderr原字节，不发布ready、不自动重发。失败前测试日志与旧helper逐字节保留。

Linux启动脚本通过本地Git Bash的bash -n；受限本地shell首次无法创建MSYS对象，获准执行同一只读语法检查后exit0。Python文件通过3.9 AST语法解析，本地实际测试解释器是Windows Python3.11.9。部署包解压到S00/tmp/s07_r3_deployment_check后再执行25项，全部通过。两次通过是同一组模拟检查的复跑，不是50种独立检查。

未运行Linux现场调度交接、S07原22项Linux检查、两域拓扑、Torch/Gloo、通信或worker；不称两域验收。本轮不提交S07，待总协调核具体包后另行安排。原R2 ZIP的34文件及其SOURCE_MANIFEST核对通过，原S07候选、模板、数值/故障门槛不变；bounded_round_step.py与原S00监督层字节相同。

| 交付 | bytes | SHA256 |
|---|---:|---|
| s07_wrapper_r3_20261105/S07_S00_WRAPPER_R3.zip | 71154 | 08e0c921e33631c9e98ac1465cf854a74c1a353a08ecbc13f480b42f296da821 |
| 原S07_R2_VALIDATION.zip，包含在新包内 | 59801 | 9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367 |

新包为10文件及1个空evidence目录条目，平铺解压至新的S07_R2_TWODOMAIN_R3_<UTC>目录。COMMANDS.md给出精确未来入口和外部前提；ARTIFACT_SHA256.txt核包内9项，MINIMAL.diff包含两个旧包装器差异与新增交接/准备/测试文件。内层原R2包还由prepare.py核原SHA及34项清单，再解压至全新payload，不覆盖旧包。

外部前提包括：仅登录节点存在的调度profile和CLI、共享新目录、30秒内时钟同步/交接、原生作业身份、计算节点Linux sysfs/affinity、既有R4 Python/Torch/Gloo及库路径。没有安装或换环境。将来资源仍76分配/每域36实际、总24576MB同limit、exclusive、300秒；本轮没有该新job安排。

## 证据与保护边界

- 初次续接核证：evidence/s06r3_s07wrapper_20261105/RESUME_AUDIT.json；保留当时认证阻断快照，不覆盖为终态。authentication_block_snapshot/保留认证恢复前状态/报告及索引。
- S06终态复核：同目录TERMINAL_REVIEW.json；candidate/audit_s06r3_terminal.py仅核原件，不重跑模型/编译。完整包S06/JOB_2039859_full_evidence.zip为92956bytes/47文件，SHA256=5437e40a591cdccf5013b0d39f433cb2975a9fdd9593debc7ce36bd69a1a6e1c；S06/bundle_resume_receipt.json为远端原回执，解压于S06/received/。
- 包内46项原文件bytes/SHA及原mtime_ns逐项核验，另外1项为COLLECTION_S00_RESUME.json；47项与ZIP逐字节相同。S06原ZIP、14源文件、6执行文件及既有EXECUTION_FILES均匹配；原mtime仅作为元数据保留，不冒称Windows解压后的mtime。包内含原始调度授权/终态、队列快照、提交命令/回执、环境/执行源、CPU/DDR回执、错误SUMMARY及收集命令。
- 原会话准备记录：同目录ROUND_REQUEST.json、EXECUTION_FILES.json及before状态快照，原样保留。
- 新层检查：s07_wrapper_r3_20261105/evidence/{resume_tests_before_fix.txt,resume_tests_after_fix.txt,deployment_tests.txt}；原tests_before.txt、tests_after.txt、tests_temp_location_failure.txt和old_job2039114.log均保留。
- 续接前草稿快照：s07_wrapper_r3_20261105/evidence/resume_before/；保留旧helper、测试、命令及diff。
- 收口状态：SESSION_STATUS.md及ROUND_DELTA.md；RESUME_ARTIFACT_SHA256.txt为本轮索引。下一步只向总协调提交S06依赖停止证据与S07具体包，等待对运行前提/包装器的复核及另行安排；本轮不自动修复重跑S06或启动S07。
