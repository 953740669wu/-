# 本轮短交接

2026-11-05；保留现有会话。AFTER_S06_S07_NEXT.md本轮已结束，旧文保留；动手前核最新文件及实际活动job。

## S00

**本轮目标**：先做R6原样内存测量的3个新增配对，再做一次S07 R2两域小张量通信。两个独立新job顺序执行，非预期失败即停，不自动重试。06等小修；不重复UBSan缺库job。

**参考文件**：自己的短状态；COORDINATION/STATUS.md及MEMORY_AND_PROBE_R2_REVIEW.md/.json；S02/round6_ckpt64_20261105T043038Z/C2_HANDOFF.md内存节及原run_c2_memory.sh、memory_gate.py；S07/round2_job_identity_20261105/INTERFACE_FOR_S00.md及evidence/R1_snapshot/INTERFACE_FOR_S00.md；COORDINATION/S07_R2_VALIDATION_MANIFEST.json。

**完成标准**：

1. 内存job单域38分配/36实际、总24576MB且limit同值、最长900秒，外层执行截止850秒/清理宽限15秒。3个新隔离目录各解压原R6包，28源字节不变，每份只调用一次原memory入口，顺序CKPT0→CKPT1，共6个新PID/3配对。只读沿用原固定case及2037034严格PASS引用，不覆盖2037434。新增外层只编排，不改训练/比较器/门禁/原timeout。若必须修改冻结payload先停下回报。
2. 每个进程完整保留case/source、memory_gate、CPU36/KML、clear_refs/HWM、hugetlb=0、一步optimizer、退出清理证据；缺项不计有效。分别列3配对峰值/步末RSS/时间与中位数/范围；旧首组单列，不挑结果。仍是首步DDR RSS重复性诊断，无稳态/真实HBM接受，计时波动不单独算数值失败。
3. 可在该job顺带只读采集/etc/os-release、uname、getconf GNU_LIBC_VERSION、cc -dumpmachine/-dumpfullversion/-print-search-dirs、系统已有包管理器对cc真实路径/libubsan包的身份查询。每条最多5秒，不全盘搜索/联网/安装/改环境；查不到照实记录，不假称解决UBSan。
4. 内存job成功终态后，S07另开一次单节点两域job：76分配核、两个不同38物理核NUMA域，每域前36核实际/后2核保留，总24576MB且limit同值、300秒，HBM=0。核S07_R2_VALIDATION.zip的34文件/59801bytes/SHA=9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367，新目录解压后核SOURCE_MANIFEST。不得复用单域授权；无法得到合法两域时交回阻塞，不另试资源方案。
5. 同一job先跑22项标准库检查，Linux项须实际通过；按R2与冻结R1接口核现场Python/Torch/Gloo身份、逐核授权和调度原件，保留现场CCS_JOB_ID，不手填环境伪造。environment检查exit0后只运行原run_checks.py的normal/crash/collective-timeout/watchdog四项；故障注入按原具体判据，非零不单独算通过。非预期失败即停，不改候选/后端、不装包，不启动训练/更多域/多节点。
6. 回传两个job完整调度/终态、命令/资源/环境、全部子进程结果/日志/退出清理、bytes/SHA/远端原mtime_ns，记录节点秒。未运行及阻塞单列。更新自己的短状态/6行变化摘要，不改别的会话状态。本交接不授权后来修订包静默替换。

## S06

**本轮目标**：只修R2隔离负例测试对父启动参数的依赖，让文档检查可运行；不改线程/清理实现，不启动集群。

**参考文件**：自己的短状态；COORDINATION/MEMORY_AND_PROBE_R2_REVIEW.md和S06_R2_REVIEW_TESTS.txt；R2/payload/tests/test_probe.py、candidate/probe.py、README_R2.md、ARTIFACT_SHA256.txt。

**完成标准**：保留R2原包及失败证据，在新修订目录将test_isolation_requires_I_and_S放到明确不带-I/-S的独立子进程验证原拒绝原因，保留隔离正例。先复现再修复；普通父解释器与-I/-S父解释器各跑全26项，Windows预计均23通过/3 Linux跳过；照实记录。模型/候选实现字节不变，新payload可搬移，重建清单/包/SHA。只更新自己的短状态与变化摘要，交协调复核，不覆盖R2旧证据。

## 其它现有会话

S07 R2本地准备通过，待S00实际结果再专项审核，不继续开发或训练。S02待新增配对齐后评估空间/时间取舍，不重跑原数值。S03等匹配工具链依据，不删sanitizer或盲重试。S04/05/08暂不扩。Git窗口按本轮已核清单归档。
