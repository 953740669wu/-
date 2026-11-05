# S00简短状态

- 更新/轮次：2026-11-05；SEQUENCE5_S07_20261105T091410Z；由S00维护。
- 本轮完成：顺序各一次S02 R7五步严格对照、S07 R3两域小张量；两个job均终态，不重试；五步内存/S06未运行。
- 活动job：无活动S00 job。2040203/cn21339 SUCCEEDED/exit0；2040233/cn21339 FAILED/exit1；两者调度PID均清空。其它任务job未操作。
- 提交去重/版本：开始无本轮02/07远端目录/提交原件；先核原包/源/case再各单次提交。开始HEAD=e4a8645，收口只读为5a22dbe；共用暂存区未操作。
- S02结果：PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY，completed_steps=5、每步1063/五步5315全过、comparison_failures=0；隔离model/AdamW对象/摘要链/step1..5连续、清梯度合格。
- S02资源/CPU：38分配/36实际留2，NUMA0，DDR24576MB同limit，900秒；24有序同PID CPU36检查完整，Torch36/所有可见TID掩码过门槛，每步KML149/197；原780+15秒入口未改。
- S02身份/门禁：原55378bytes/24文件包SHA=bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092；case前后SHA/bytes/mtime不变；原sequence_gate集群/下载副本均exit0，仅固定case五步引用，不授权内存。
- S07交接/检查：原已核71154bytes包SHA=08e0c921e33631c9e98ac1465cf854a74c1a353a08ecbc13f480b42f296da821；RUNNING后原publisher单次exit0，原生job/nonce/SHA/主机/76核/资源/逐域sysfs核验通过；Linux22项全过无跳过，环境检查通过。
- S07失败：首个normal在进程组初始化失败；rank1实际Torch36、init_process_group报RuntimeError: Wait timeout；rank0最后before_framework、未到Torch36记录，不能证明双rank实际72核。normal exit[-15,1]，all_reaped=true；外层remaining_live=[]。
- S07未运行：normal未到身份all_gather/broadcast/all_reduce；crash/collective-timeout/watchdog均未启动。不接受通信或正式同步训练，不能把normal非零当故障注入通过；未调超时/改包/重提。
- S07资源：76分配、NUMA0/1各选36留2、总DDR24576MB同limit、exclusive、300秒；仅rank1实际Torch36有记录，rank0缺该测量。
- 有限C++查询：在2040203内仅查询g++/c++/clang++及gcc报告路径；默认搜索范围无C++命中，/bin/gcc返回相对g++/cc1plus；无具体C++ ELF/SHA可记录。没有安装、编译、换环境或重跑S06。
- 证据：SEQUENCE5_S07_R3_REPORT.md；evidence/sequence5_s07r3_20261105T091410Z/REVIEW.json及downloaded/{S02,S07}/received/；S02包66文件/229688bytes，S07包101文件/249710bytes；65/100项原mtime/bytes/SHA核对。
- 原包/旧失败：两份已核候选包、旧S06失败ZIP/报告保护哈希未改；候选、阈值、固定输入及其它任务目录未改。
- 成本：2040203起止72秒/usage71秒；2040233起止60秒/usage59秒，两项顺序共132节点秒；已知累计19job/898节点秒。SSH/SCP正常退出，凭据未落盘。
- 下一步：交总协调及S02/S07原会话复核五步PASS和normal初始化失败；未安排五步内存或任何重提，待另行核包排期。
