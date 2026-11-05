任务/轮次：S03 / ROUND2_API_BOUNDS_20261105。
状态变化：新轮候选READY_FOR_REVIEW；新增Linux C/UBSan验证未运行，保留上轮有限C接受。
本轮改动：新round候选+14/-3行，修节点解析、大小/arena运算及对齐；free/realloc与策略恢复不变，旧19文件不变。
验证增量：本地7项交付检查通过；新增50场景仅已编写（旧候选预期21失败/29控制），未重跑原25场景。
证据：SESSION_STATUS.md；round2_api_bounds_20261105/REPORT.md、ARTIFACT_SHA256.txt、evidence/local_validation.json。
阻塞与下一步：无本地Linux C工具链；总协调核包后由S00运行新轮Linux命令，无活动进程/job，不开展真实HBM/性能。
