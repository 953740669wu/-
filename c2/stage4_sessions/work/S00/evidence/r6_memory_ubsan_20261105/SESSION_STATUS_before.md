# S00简短状态

- 更新/轮次：2026-11-05；S02_R6_CKPT64_S03_R2_UBSAN；由S00维护。
- 当前目标与进度：本轮两个限定新job均已终态并完整回传；S02固定B64 CKPT0/1严格PASS，S03默认工具链不能链接-lubsan，C场景/库未到达；无重试。
- 修改的文件：本轮执行层/原样包副本/证据及R6_S03R2_EXECUTION_REPORT.md；更新本文件和ROUND_DELTA.md。未改候选算法、数值阈值、输入或其他任务目录。
- 测试结果及证据：job2037034/cn21339，exit0、1063/1063、双方KML149/197、7同PID CPU36检查；job2037064/cn21339，exit1，previous编译链接缺-lubsan，无50场景或新库结果。
- 资源/实际消耗：两项分配38核/实际36留2核、24576MB及同值limit；时限900/300秒，实际33/2秒。未运行训练内存、clear_refs、真实HBM或旧R5/R7。
- 证据路径：c2/stage4_sessions/work/S00/evidence/s02_r6_s03_r2_20261105/；详细报告c2/stage4_sessions/work/S00/R6_S03R2_EXECUTION_REPORT.md。
- 阻塞：S03本次默认工具链找不到-lubsan，必须保留sanitizer；两job终态及PID清空已由本轮回执核实，SSH已退出；其他任务进程不作结论。
- 下一步：总协调审核R6固定case PASS；为S03提供受控可用UBSan编译/链接环境后另行授权一次新C job。内存/真实HBM仍需另行安排，不自动执行。
