任务/轮次：S00 / R6独立首步DDR内存诊断 + UBSan恢复/条件C（36核、24GiB）。
状态变化：2037434成功exit0；2037491因有限位置无UBSan库阻断exit1；两job均终态。
本轮改动：新增执行层、完整证据和R6_MEMORY_UBSAN_REPORT.md，更新自己的状态/增量；候选及阈值不变。
验证增量：独立PID各完成一步，训练峰值5836.01/4313.88MiB、KML149/197、各7项CPU36；C正负控/50场景/库均未运行。
证据：SESSION_STATUS.md / ROUND_DELTA.md / R6_MEMORY_UBSAN_REPORT.md / evidence/r6_memory_ubsan_20261105/。
阻塞与下一步：协调补充匹配UBSan路径后另行安排；内存仅首步诊断，无重试、真实HBM或06/07探针，旧证据保留。
