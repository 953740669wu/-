任务/轮次：S06 / R2_THREADS_CLEANUP（2026-11-05）。
状态变化：R1待修订 → READY_FOR_REVIEW（R2修订包）；LOCAL_ONLY / CLUSTER_NOT_RUN。
本轮改动：新round统一OpenBLAS1、删除Torch线程setter并核实际36/全部可见TID，补TERM/中断/异常/超时有界组清理；完整R1及旧可变状态已先归档。
验证增量：26项23通过/3 Linux实测跳过；任意目录搬移复跑通过；Python3.9语法/bash -n通过；真实Torch36/C2/组清理未测，不作性能结论。
证据：c2/stage4_sessions/work/S06/SESSION_STATUS.md / ROUND_DELTA.md；round2_threads_cleanup_20261105T064456Z/{REPORT.md,MINIMAL.diff,ARTIFACT_SHA256.txt,S06_R2_PAYLOAD.zip}。
阻塞与下一步：总协调核R2及SHA后，S00按payload/README_R2.md在明确安排资源内执行；无新job，无安装/框架重编或性能搜索。
