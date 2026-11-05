# S00 wrapper R5：S07双方就绪R4内包部署准备

2026-11-05；READY_FOR_COORDINATOR_REVIEW / LOCAL_ONLY / NO_NEW_JOB。

仅写S00新版本目录及自己的短状态/变化摘要；本轮未SSH、未调用真实调度CLI、未提交job、未运行真实Torch/Gloo/通信。新S07 R4内包原字节保持，S00旧wrapper R4及2040233/2041165失败保留。53项旧包/源/报告/失败及新输入包bytes/SHA保护检查通过，共用暂存区与其它任务目录未操作。

## 固定内包与外包

| 交付 | bytes | 实际成员 | SHA256 |
|---|---:|---|---|
| S07_READY_SYNC_R4.zip | 34295 | 14成员=13文件+1空目录；12项delivery | d39ae26f2b29d53f733bdef937832edeeec4bf4a468adf2d0eff0dbe5fb39c45 |
| S07_S00_READY_WRAPPER_R5.zip | 70373 | 17成员=16文件+1空目录；15项内容索引 | b13b7c1c77241b12e7d07b0ac38d48c996667492e76a69c02f834ba6a1be9a61 |

prepare.py固定新名称/大小/SHA、精确成员与12项delivery的bytes/SHA；pre_submit payload_files和consumer计数均为13。SOURCE_MANIFEST自身通过整包身份固定，所有13文件与内包逐字节一致。已有payload拒绝覆盖，旧内包身份不接受，未修改S07候选。新远端目录前缀为S07_READY_WRAP_R5_，与旧部署目录区分，不能用新目录绕过实际提交去重。

原scheduler_handoff.py、bounded_round_step.py、trace_inventory.py及启动shell与旧wrapper R4逐字节相同。submit_once仍仅登录侧一次dsub、RUNNING后立即原publisher一次；修改仅错误提示随新前缀适配，未重写授权或资源方案。

## 44项及统一预算

消费者CHECKS顺序为16 readiness + 6 diagnostics + 6 identity + 16 probe=44。前两组上限各30秒，后两组各45秒，环境仍上限60秒；所有阶段和原30秒调度交接共同消耗同一个270秒deadline，取剩余预算，不追加窗口。新实际Linux job要求44全通过、无跳过，环境通过后才执行一次原四case入口。

原生CCS_JOB_ID、nonce/request/raw/ready原子交接、新鲜度、主机/当前76核/逐核sysfs、每域36实际留2、总DDR24576MB同limit/exclusive/HBM0均保持。job300秒、原通信5秒、原spawn前计时的30秒总监督和TERM/KILL/wait清理不变；normal失败停止，其他故障注入仍按原具体判据。本轮不设置参与者或worker ready，不设置S07_CASE_DEADLINE_NS，不从JSON补原生job。

## 新就绪原件的终态收集

collect_evidence.py在原三流及原结果之外增加READINESS_INVENTORY.json；COLLECTION_S00同时保留diagnostics与readiness两份独立清单，不重写通信checks/summary。

participants.json、ready_rank0.json、ready_rank1.json以及*.tmp*残件全部保留bytes/SHA/原mtime_ns；缺失、半JSON或写入残件也照原字节收集。已有全目录收集继续包含manifest.ready_token、父/worker events、真实PID、rank JSON/log、commands、原授权/终态及逐step时间/退出/清理。临时残件不替代正式ready、不删除、不修复，不因新核验不完整丢弃原件。

新readiness_inventory.py仅在终态只读检查：

- manifest的run/job/token与当前收集job、participants精确字段/两个不同整数PID一致；PID须同时匹配父summary及spawn事件。
- 原绝对deadline为整数，位于supervisor_begin事件之后且不晚于该事件+30秒；原计时点在该事件之前，不能以日志时间重新赋予30秒。
- 两份正式ready的run/job/token/rank/PID/类型精确一致；每rank自己的after_framework→preparation_complete→ready_published→both_ready→init尝试记录依序出现，PID一致，both_ready/init记录早于原绝对deadline。
- 不比较跨rank的ready_published日志先后，也不用文件mtime充当精确发布时刻。合法原子发布可以先于该rank的后续日志，对方可先读到文件；本地专门正例覆盖此情况。

通过时清单保留verified_context（身份/token/实际PID/原deadline、父起点事件和每rank自身阶段时钟）。缺文件/行、残件或矛盾都标READINESS_EVIDENCE_INCOMPLETE；缺项不等于候选绕过门禁、永久卡住或故障注入通过。进程私有deadline环境不由日志独立恢复，仍由冻结候选与现场源身份共同约束。原trace清单的开放区间和TRACE_WRITE_ERROR规则保持独立。

## 必要本地检查

先建立新收集检查入口，保留实现前readiness_inventory模块尚不存在的导入失败evidence/readiness_before.txt；实现后结果如下。此记录不是旧通信故障复现。

| 范围 | 方法数 | 结果 |
|---|---:|---|
| 新就绪收集/身份/PID/deadline/残件/合法日志交错 | 10 | 全通过 |
| 更新后的部署/清单/44项安排/原收集回归 | 14 | 全通过 |
| 原调度交接正负控，同字节helper | 25 | 全通过 |
| 新内包readiness/diagnostics/identity/probe | 16+6+6+16=44 | 43通过，1项Linux组清理跳过 |

本轮外层49项全过；内包43过1跳过。10项针对性检查覆盖错误run/job/token/rank/PID/类型、parent真实PID对应、deadline被重置/延长、到期init尝试、缺自身阶段、缺participants仍保留ready/tmp、半JSON残件、只读性及模拟终态归档原字节。模拟dsub/假框架/受控时钟均不代表实际调度或通信。

独立ZIP解压副本位于本新版本evidence/deployment_copy，逐项核SHA、解出新内包，再复跑同组49+44，结果相同；不是双倍独立测试。Windows Python3.11.9实际执行；Python3.9 AST/LF及本地Git Bash语法检查通过，未声称Python3.9实际执行或Linux44全过。旧2041165的28 Linux通过仍为历史，不挪作新包通过。

## 交付与下一步

MINIMAL.diff给出旧wrapper R4到本R5的必要源码/检查差异，原授权/清理/trace/shell无差异。ARTIFACT_SHA256.txt索引15项包内内容；外包SHA/实际数量见DEPLOYMENT_RECEIPT.json。COMMANDS.md给出精确上传/解压/prepare/外层检查/登录CLI/单次提交/自动发布及终态收集命令，列明原R4解释器、Torch/Gloo、库路径、共享目录和登录profile等外部前提。没有新安装或工具链需求。

evidence/FINAL_VERIFICATION.json及DEPLOYMENT_CHECKS.json保留包、数量、保护检查、实际命令/退出和未测边界；原始测试日志完整保留。自己的SESSION_STATUS.md/ROUND_DELTA.md与ROUND_ARTIFACT_SHA256.txt收口。

本轮新job/节点秒均0，未实时复查集群队列；上轮2041165终态和原件保持。当前无新通信/根因修复/性能接受。仅将具体包交总协调核验，核包后还需另行安排一次有界实测；不自动重提02/06/07、扩大预算或进入训练。
