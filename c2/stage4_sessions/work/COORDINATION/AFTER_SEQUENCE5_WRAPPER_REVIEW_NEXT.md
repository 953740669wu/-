# 本轮短交接：五步数值与两域小张量实测

2026-11-05；使用现有S00续接窗口。执行前优先读短状态/总表，再核最新文件、实际活动job和SHA；不要重复提交已存在的任务。

## S00

**本轮目标**：顺序运行两项独立且已核包的任务：S02 R7五步严格对照、S07 R3两域小张量通信。前一job终态后才提交后一job，任一路非预期失败就停止该路径，不自动重试；可继续另一项已明确列出的独立任务。五步内存本轮不运行，S06不重提。

**参考文件**：自己的短状态/增量；COORDINATION/S00_RESUME_S02_SEQUENCE5_REVIEW.md/.json；S02/round7_seq5_20261105T082315Z/{C2_HANDOFF.md,package/PACKAGE_MANIFEST.json,sequence_gate.py}；S00/s07_wrapper_r3_20261105/{COMMANDS.md,ARTIFACT_SHA256.txt,prepare.py,scheduler_handoff.py}；S00/S06R3_S07_WRAPPER_RESUME_REPORT.md。

**完成标准**：

1. S02仅一次新job，单节点单NUMA、38分配/36实际留2、DDR24576MB且limit同值、最长900秒，使用原C2_HANDOFF.md严格入口及780+15秒内层。代码包55378bytes/24文件，SHA=bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092。新隔离目录解压，核全部源/LF/语法与固定case原SHA，沿用已核R4/KML，调度profile只在登录端使用。不要求或加载C++编译器，不因S06缺g++阻断本项。
2. 严格成功必须exit0、PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY、completed_steps=5，每步原1063指标/五步5315全部通过，参数/AdamW承接1..5、隔离实例/状态链/原case与源身份、每步双侧KML、24个有序CPU36检查完整。1/2/超时/信号/缺项均按原状态保留，禁止弱化阈值、换输入、扩配置或自动重试。执行后用原sequence_gate复核回执，仅表示五步引用有效；不得由此自动提交内存job。
3. S07仅一次独立新job：单节点两个不同38物理核NUMA域，76分配/每域实际36留2、总DDR24576MB且limit同值、exclusive、300秒、HBM0。只用已核S07_S00_WRAPPER_R3.zip，71154bytes、10文件加空目录条目，SHA=08e0c921e33631c9e98ac1465cf854a74c1a353a08ecbc13f480b42f296da821。按COMMANDS.md在新S07_R2_TWODOMAIN_R3_<UTC>目录执行，不能临时修改已核包；若必须改包先回报复核。
4. 登录侧提前准备publisher，观察当前job进入RUNNING后立即单次发布，不在计算端30秒交接窗口中等待人工回复；队列观察不是实验重试。原生CCS_JOB_ID不能从JSON手填。核request/raw/ready、当前job/host/76核授权、逐域sysfs及资源；原22项Linux标准库全过，environment通过后才做normal/crash/collective-timeout/watchdog。故障注入必须符合原具体判据，不能仅以非零判通过；不启动同步训练/更多域/多节点，不依赖S06 C++工具链。
5. 可在上述既有job顺带只读检查有限C++来源：原PATH可解析的g++/c++/clang++及GCC报告路径，不全盘扫描。对实际命中路径记录解析位置、版本/ELF/SHA/依赖，每条最多5秒；不安装、编译或换环境，无命中就记录阻塞，不另提资源探测job。若找到现有编译器，只提出S06既有S06_CXX与S00外层预检一致的最小修订方案，本轮不运行06或静默改其包。
6. 回传两job完整调度/终态、实际命令/配置/资源/环境、源码与case前后身份、全部checker或通信case的日志/退出/清理/失败局部结果、bytes/SHA/远端原mtime，记录实际节点秒。明确未运行项，不用checker RSS当训练内存。结束更新自己的短状态和6行变化摘要，汇报活动job或已终态，不操作共用Git暂存区。

## S02 / S06 / S07

本轮均保留原会话。02待五步数值结果再专项审核，完整接受后才安排独立五步内存。06等具体C++路径与外层修订复核，不继续重复缺依赖job。07待新两域结果审核；即使四case通过也只接受小张量通信，不进入正式DDP训练。03缺UBSan仍阻塞，04/05/08不扩大。
