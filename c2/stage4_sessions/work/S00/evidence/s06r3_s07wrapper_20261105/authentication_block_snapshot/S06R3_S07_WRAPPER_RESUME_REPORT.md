# S00续接：S06现场状态待认证，S07执行层已准备

2026-11-05；S06_REMOTE_STATE_UNKNOWN / S07_WRAPPER_READY_FOR_COORDINATOR_REVIEW。

按指定顺序读取自己的状态、增量、总任务表和AFTER_MEMORY3_S06R3_NEXT.md的S00节，再核对本地最新文件、Git记录、原包、旧失败和执行层。只操作S00目录，没有操作共用Git暂存区或其它任务目录。

## 续接核对与活动job

本地HEAD为e4a8645；短总表仍引用51d4089，不能作为当前提交或作业证据。原会话已留下candidate/run_s06_r3_job.{py,sh}、candidate/bounded_step_s06.py，以及evidence/s06r3_s07wrapper_20261105/{ROUND_REQUEST.json,EXECUTION_FILES.json}。本地该证据目录没有submission/job_id/调度终态原件；这不证明远端尚未提交。

严格使用既有已确认known_hosts、禁用公钥的只读SSH连接检查：10.44.9.4:22可达、主机密钥校验通过，但新会话没有继承密码认证，返回Permission denied (publickey,gssapi-keyex,gssapi-with-mic,password)。没有尝试任何密码、猜测凭据或更换密钥。已向用户请求可用登录认证；这是缺少认证信息，不是重新请求提交授权。

因此**活动job、远端队列、原会话是否已提交以及是否已有结果，全部尚未核实**。本续接会话提交0个job、重试0次，没有把旧状态的“无活动job”沿用为当前事实。当前也无法新增实际节点秒；远端未知成本不能记作0。

认证恢复后的第一条动作是只读查询当前账号队列，并检查共享S00目录内S06_R3_FIRST_*的提交标记、submission、job_id、job.log、job_evidence、调度原件及实际进程。找到已有job就续收，不重复提交；已有终态先整理。只有确认没有本轮执行，才按原交接执行一次38分配/36实际、8192MB同limit、exclusive、单NUMA、660秒/外层640+清理10秒的原包探针；失败即停。

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

- 续接核证：evidence/s06r3_s07wrapper_20261105/RESUME_AUDIT.json；记录真实SSH认证阻断、HEAD、新包SHA及11项原包/旧报告/旧失败保护哈希。
- 原会话准备记录：同目录ROUND_REQUEST.json、EXECUTION_FILES.json及before状态快照，原样保留。
- 新层检查：s07_wrapper_r3_20261105/evidence/{resume_tests_before_fix.txt,resume_tests_after_fix.txt,deployment_tests.txt}；原tests_before.txt、tests_after.txt、tests_temp_location_failure.txt和old_job2039114.log均保留。
- 续接前草稿快照：s07_wrapper_r3_20261105/evidence/resume_before/；保留旧helper、测试、命令及diff。
- 收口状态：SESSION_STATUS.md及ROUND_DELTA.md。本报告不替代尚缺的集群实际状态与终态证据。
