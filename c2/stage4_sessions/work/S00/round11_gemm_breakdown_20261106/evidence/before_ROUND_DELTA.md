任务/轮次：S00 / R9_PROFILE5_20261106。
状态变化：S01同SHA专项PASS后，唯一2048959/cn21338成功终态exit0；5连续更新/320帧/2预热3采样完成，无重试、无活动S00 job。
本轮改动：新目录/部署包/marker，适配PROFILE5及完整success/unsupported/limit/incomplete收集；发布S00_DEPLOYMENT_READY和RUN_COMPLETE，原descriptor/旧job输出/正式门禁/PROFILE_READY均未改，未操作Git暂存或其它任务。
验证增量：8本地+8 Linux登录针对性检查/源SHA/语法/元数据通过；15项原loss比较差0，初始化/scale/frame/mask/KML一致；3trace+3events每次10845事件/149标记均在限额内，19 CPU36快照、零更新恢复、PID清空通过。
证据：round9_profile5_20261106/{RUN_COMPLETE.json,RUN_AUDIT.json,RUN_REPORT.md,EXPOSURE_LEDGER.json,SHA256_INDEX.json}及evidence/JOB_2048959_evidence.zip（1066705bytes/105文件，SHA=bb17a1ff559ffe328ae95f23db9f3126158a771052e3350ef435166755a88f5c）；新checkpoint456134879bytes留远端，SHA=2d7dfb1ac8846f4101107924d7f4810b142285dd831b55628d55d686b6e6e64a。
阻塞与下一步：本轮执行无阻塞，供01/02/协调按新证据定向分析；仅工程CPU剖析，不称精确KML内核时间/稳态加速/科学验收。新增94节点秒/usage93分列，未触发信号故障清理，不自动重试/扩预算/补跑。
