任务/轮次：S07 / R1 通信预备轮。
状态变化：未启动 → READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN；仅候选准备完成。
本轮改动：只写 c2/stage4_sessions/work/S07；交付固定2-rank Gloo探针、CPU36冻结副本、正确性/故障/超时检查、来源SHA和逐rank资源方案/S00命令。
验证增量：16项标准库检查15通过1跳过，Python3.9 AST语法通过；环境exit3无torch、Windows实际入口前置拒绝无worker；14项引用SHA未变；真实Gloo/Linux组清理/训练/性能未运行。
证据：c2/stage4_sessions/work/S07/ 下 SESSION_STATUS.md / ROUND_DELTA.md / REPORT.md / INTERFACE_FOR_S00.md / SOURCE_MANIFEST.json / evidence/local_checks.json。
阻塞与下一步：历史构建Gloo=ON但当前通信未测；待S00具备合法两域安排再执行，不申请资源；正式batch/学习率/训练计划待定。
