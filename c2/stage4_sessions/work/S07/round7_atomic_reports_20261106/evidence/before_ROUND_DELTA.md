任务/轮次：S07 / R6 单次对齐取栈实现，本地检查/打包。
状态变化：已评审诊断提案 → READY_FOR_REVIEW_LOCAL_ONLY；仅观测实现，2041919整组FAIL及旧失败保持。
本轮改动：watchdog原case+25秒一次取栈/取消及FD生命周期，绝对2秒共享proc helper身份/CPU/超时回收，准备阶段安装Python源SHA；交diff/内包/SHA/S00提案，原5秒/30秒/注入点/判据不改。
验证增量：新增27方法全过，加原44共71项70过1跳过，独立ZIP复核同结果；9文件AST语法通过，19引用及R4 37项/R5 73项SHA不变；Linux/proc/C2/Gloo本轮未运行。
证据：c2/stage4_sessions/work/S07/ 下 SESSION_STATUS.md / ROUND_DELTA.md；round6_aligned_stack_20261105/ 下 REPORT.md / OBSERVATION_CONTRACT.md / minimal.diff / package/S07_ALIGNED_STACK_R6.zip / SHA256SUMS.txt / EVIDENCE_MANIFEST.json。
阻塞与下一步：待协调核包及S00适配后另排；本轮无job/资源申请/补跑，新包43727bytes、16成员/15文件/14 delivery，正式batch/LR/schedule待定。
