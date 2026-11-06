# S00简短状态

- 更新/轮次：2026-11-06；S07_R6_RESUME_TERMINAL_FAILED_EVIDENCE_COLLECTED；目录s07_r6_resume_20261106。
- 终态：01同8项SHA/资源/原判据PASS_FOR_S07_R6_DIAGNOSTIC后，唯一2050433/cn21338 FAILED/exit1；06:43:49Z—06:45:34Z，新增105节点秒/usage104秒；1新job、0重试，无活动S00 job，不补watchdog或后两项。
- 停点：71 Linux检查全过零跳过、环境过；normal原固定张量通信PASS。crash rank1到injected_crash/exit17，父child_failed/exit_codes[-15,17]/双方回收；crash/rank0.json为0bytes，原checks.json读取报Expecting value: line 1 column 1 (char 0)，整组FAIL，仅normal列已接受cases；collective-timeout/watchdog NOT_RUN。
- 分判：现存normal/crash events与readiness清单一致，但明确not_run后两项；STACK_INVENTORY NOT_RUN、diagnostic_task_complete=false。未产生watchdog栈/installed Python/proc/helper原件，不把ARMED/EXITED/清理成功当通信或诊断通过，也不拼旧结果。空JSON与邻近worker_error/TERM可能有关，确切根因待S07定向分析，不提前定论。
- 资源/CPU：76分配、两个38物理域，每域selected36，共72实际/4预留，DDR总24576MB同limit/exclusive/HBM0/job300；全前置/71检查/四case共享270执行、15清理/15收尾，未扩预算。normal双方及crash rank1现存报告实际Torch intra36、23 CPU/TID快照可核；crash rank0空报告的序列化快照缺失不补造。
- 身份与清理：原生CCS_JOB_ID/host/affinity、nonce/request/raw/ready SHA及30秒新鲜度一致；原库与同job环境一致；内外包/源码无漂移、旧受保护原件不变。所属14PID全部退出、remaining_live/processes为空、调度PID清空；实际crash父TERM已发生，包装兜底无额外信号；watchdog/helper分支未现场执行。
- 包：R6内包43727bytes/16成员/15文件/14 delivery，SHA32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1；新部署104603bytes，SHA82efe84bc36c34db71e107b64f9ff74641b44495d65452d3ec1a535ad5436dc1；审核SHA=b9082f2385df26e05ff6ccd9b11f421db38e2e597d643bff81b2d9859e09b250。
- 回传：evidence/JOB_2050433_full_evidence.zip，321066bytes/125文件，SHA2b0dfd047aed0a17e745aefd79a0b150358e499eac1b51c52a7bdc1e6d306b7d；全部原始空文件/事件/participants/ready/store/残件按bytes/SHA/远端mtime保存。RUN_COMPLETE.status=RUN_TERMINAL_FAILED，绑定各已到case原件/原checks/索引/审计；RUN_REPORT/SHA256_INDEX/ARCHIVE_FILES同目录。
- 下一步与边界：交协调/S07分析crash空JSON与父TERM/读取顺序；本卡无再运行授权，不热改冻结包/判据后重提。R12按协调CLOSED_NO_TRAINING_GAIN保持原fp32基线，不搜索分块/精度或追加训练A-B。旧2041919仍FAILED/1并保留，未改其它任务/旧门禁或共享Git暂存/提交推送。
