任务/轮次：S00 / S02_R6_CKPT64 + S03_R2_UBSAN（实际36核、24GiB）。
状态变化：两job已终态；S02固定case严格PASS，S03因UBSan链接前提阻断。
本轮改动：新增本轮执行/证据与报告，更新SESSION_STATUS.md、ROUND_DELTA.md；候选和阈值不变。
验证增量：2037034为1063/1063通过、KML149/197；2037064缺-lubsan，新50场景及独立库均未到达。
证据：SESSION_STATUS.md / ROUND_DELTA.md / R6_S03R2_EXECUTION_REPORT.md / evidence/s02_r6_s03_r2_20261105/。
阻塞与下一步：S03补齐受控UBSan环境后另行授权；本轮无重试、训练内存或真实HBM，旧失败证据保留。
