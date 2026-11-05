# S00 wrapper R4：S07初始化诊断包部署准备

2026-11-05；READY_FOR_COORDINATOR_REVIEW / LOCAL_ONLY / NO_NEW_JOB。

本轮只在S00新修订目录准备包装层，未SSH、未调用真实调度CLI、未申请资源、未运行模型/通信。S07 R3新诊断内包保持原字节，S00旧wrapper R3、2040233失败及2040363五步内存结果保留；26项保护文件的bytes/SHA核验通过。旧通信失败根因仍未确定，新包只增加观测能力，不是已修复结论。

## 固定包与执行层变化

| 项目 | bytes / 文件数 | SHA256 |
|---|---|---|
| S07新内包S07_INIT_DIAGNOSTIC_R3.zip | 31262 / 12文件+空目录 | af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45 |
| S00新部署包S07_S00_DIAGNOSTIC_WRAPPER_R4.zip | 62715 / 14文件+空目录 | b20e248be761db6c645fdbcebbbfc61d083642bb0e1d959eb1a0fcfa9b304284 |

prepare.py在解压前固定新包名称/大小/SHA，精确要求12文件及evidence/空目录，按SOURCE_MANIFEST的11项delivery核bytes/SHA并拒绝多余/缺失/不安全成员；已有payload拒绝覆盖。源/文档12项与新内包逐字节一致。它不接受把新内包换成旧R2包或旧SHA。计算端在原授权/框架之前再次核新包身份和12项源文件。

原scheduler_handoff.py和bounded_round_step.py字节保持，前者SHA=f907cbf8286f7bc9035c9e58f986c3b342b2a6f6f5a1c60f97834915f2a7065c，后者SHA=b9fa564e89edcdaaf9e597f6511e84fb8b845cddd6c065ae489ba61d1f2dc697。原生CCS_JOB_ID、nonce/request/raw/ready、原子发布、新鲜度、30秒等待、单节点76核授权、两域sysfs及每域36/留2核检查保持。

run_s07_diag_job.py按6项诊断、6项身份、16项原检查安排共28项；新增诊断单项上限30秒，原身份/原检查各45秒及环境60秒仍取同一个270秒消费者deadline的剩余预算，未叠加窗口。Linux实际执行必须28全通过且无跳过，之后原environment通过才运行一次原run_checks.py。四case顺序及normal失败即停、pg_timeout=5、case deadline=30、原有界清理均不变；270秒包含授权等待，job仍300秒。

submit_once.py是未来另行安排后的登录侧入口，先独占写单次标记、只发一次dsub，观察RUNNING后立即调用原publisher一次，避免计算端窗口内等待人工回复。真实CLI没有在本轮调用；本地测试使用明确替身。发布/观察失败不重提、不重发，不从JSON设置CCS_JOB_ID。

## 事件收集及证据完整性

collect_evidence.py只在登录侧、当前job终态且PID清空后运行，保存调度原件和所有实际文件：两rank及父监督三个完整events.jsonl、原rank JSON/log、manifest、summary/checks、commands、S00逐step时间/退出/清理、内包/源及授权交接。bytes/SHA/远端原mtime_ns逐项索引。收集在job终态后执行，不追加计算预算。

trace_inventory.py独立生成DIAGNOSTIC_INVENTORY.json。TRACE_WRITE_ERROR、缺事件流/身份、父spawn/cleanup/reap缺行、JSON或时钟格式错误、末行截断及可见begin未闭合都标为不完整，尚未到达case标NOT_RUN；不改变原通信PASS/FAIL或故障判据。即使事件或源完整性异常，收集器仍保留原始字节和异常清单，不因诊断失败丢弃失败证据。

缺end不能单独证明永久卡住，异常返回/监督终止与日志缺口须一起分析。原事件没有全局序号，清单不能排除整对事件同时遗漏；COMPLETE_AVAILABLE_TRACES_ONLY只表示所收集流通过可观测结构检查。阶段间隔包括flush/fsync及I/O，不能视作纯框架导入/通信性能；共享盘成本尚未现场测量，不承诺Python层硬实时保证。

## 必要本地检查

先建立部署检查入口，保留实现前prepare模块尚不存在时的导入失败记录evidence/tests_before.txt；随后实现，不把该记录称为旧通信故障复现。

| 本地范围 | 方法数 | 实际结果 |
|---|---:|---|
| 新部署/包身份/清单/28项安排/事件收集/模拟单次发布 | 14 | 14通过 |
| 原授权交接正负控，同字节helper | 25 | 25通过 |
| 新内包诊断+身份+原probe | 6+6+16=28 | 27通过、1项Linux组清理跳过 |

14项包括新内包完整解压及12/11清单、旧/坏身份拒绝、清单更改/缺成员、同一270秒安排、三流原字节保留、缺流/截断/缺end/TRACE_WRITE_ERROR/身份错误/父reap缺失拒绝、未到达case、模拟终态收集损坏流，以及模拟一次dsub后RUNNING单次发布。假调度/假事件不算现场授权或通信通过。

实际解释器为Windows Python3.11.9；Python文件3.9 AST/LF通过，启动脚本本地Git Bash的bash -n通过。解压到S00/tmp/s07_diag_r4_deployment_check独立副本后，同组14/25/28再跑，结果相同；不是两倍独立测试。之后仅修正文档中的收集命令，避免将仍在写入的collection.log放入待索引目录；执行文件未变，最终外包与该已测试副本执行文件逐字节相同，并另解压核最终14项。修正前草包保存在evidence/draft_bundle_before_command_fix.zip。

未执行Linux新28项、现场新内包授权交接、真实Gloo/四case、共享盘刷盘计时或故障修复验证。旧2040233的Linux22项属于历史，本轮不移用为新包通过。

## 交付、命令及停止条件

- MINIMAL.diff：与旧wrapper R3的prepare、执行Python/启动shell差异，以及新增事件清单/收集/单次提交/针对性检查；两个旧授权/清理helper不在修改差异内。S07候选本轮没有改动。
- ARTIFACT_SHA256.txt：部署包内13项内容SHA，另1项为该清单；外包本身身份见DEPLOYMENT_RECEIPT.json，避免循环哈希。
- COMMANDS.md：精确解压、prepare、本地检查、登录source、单次提交/自动发布及终态收集命令；包含外部共享目录、原R4解释器/Torch/Gloo/库路径及CLI前提。
- evidence/FINAL_VERIFICATION.json：最终包、26项保护、同字节源/已测试副本、检查数量及未测边界；evidence/DEPLOYMENT_CHECKS.json保留搬移副本实际命令/退出，原始日志全部保留。

未来资源仍单节点两个38物理核域，76分配/每域36实际留2，总DDR24576MB且同limit、exclusive、300秒、HBM0。任何身份/依赖/检查/通信非预期失败即停，不自动重试、放宽超时、换环境或扩大域数。总协调核本具体外包后才另行安排实际诊断job；本轮新增job及节点秒均0，未重跑02/06/07或追加内存。

自己的SESSION_STATUS.md和ROUND_DELTA.md已更新。当前集群队列本轮未重新探测；上次已核2040363终态证据保留。共用Git暂存区及其它任务目录未操作。
