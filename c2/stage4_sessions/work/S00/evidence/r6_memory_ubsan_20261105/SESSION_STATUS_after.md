# S00简短状态

- 更新/轮次：2026-11-05；R6_MEMORY_UBSAN_RECOVERY；由S00维护。
- 当前目标与进度：本轮两个限定新job均已终态；R6独立B64 CKPT0/1首步DDR内存诊断完成，UBSan恢复因有限位置无库阻断；没有重试。
- 修改文件：本轮执行准备/UBSan条件执行层/收集与本地复核、证据、R6_MEMORY_UBSAN_REPORT.md及本文件/ROUND_DELTA.md；候选、case、数值阈值未改。
- 测试结果：2037434/cn21339 exit0，独立PID1428225/1429732，各7项CPU36检查及KML149/197，原memory_gate通过；训练峰值5836.0078125/4313.87890625MiB。
- 测量边界：完整B64、fp32、fresh AdamW一步、HBM0；clear_refs=5成功且训练起始HWM重置到RSS、HugetlbPages=0；仅首步诊断，非内存收益或稳态吞吐接受。
- C阻断：2037491/cn21339 exit1，编译器报告路径及有限系统目录没有libubsan；正负控、新50场景和独立库均未运行；不删sanitizer、不安装或换工具链重试。
- 资源与消耗：均分配38核/实际36留2核、24576MB且limit同值；时限900/300秒，实际UTC墙钟38/2秒，本轮40节点秒；累计14job/483秒。
- 证据：evidence/r6_memory_ubsan_20261105/（90/49文件，SHA/bytes/原mtime_ns核对）；详报R6_MEMORY_UBSAN_REPORT.md、机读review.json。旧R6数值PASS及历史失败原件未改。
- 执行修正/收尾：提交前整块case哈希异常，保留失败后改回原分块方法，未改输入且无job重试；两job终态PID清空，SSH/下载连接均正常退出；无真实HBM或06/07探针。
- 下一步：S02/总协调复核首步原始数据；协调提供可核实匹配UBSan位置后另行授权新有界C任务，仍先正负控。本轮没有活动job，不自动复测或扩大。
