任务/轮次：S07 / REAL_DUAL_DDP，2026-11-06，首次真实双域训练候选准备。
状态变化：新入口/固定TRAINING_READY已冻结交接，但本地严格fp32配对FAIL保留；供S00打包/S01审核，不是训练放行。
本轮改动：完整Encoder+双head DDP、全局分母/32+32原分片mask、连续B64前5门槛及同状态25步、逐步参数/AdamW同步、暴露与零更新恢复；S02/R7原件不改。
验证增量：19方法17过1数值FAIL1 Linux skip；真实小DDP到backward/两rank梯度一致，13项B64配对3项FAIL，tf.weight绝对3.723800e-5/相对1.142869e-4；原阈值不改，C2训练未运行。
证据：real_dual_ddp_20261106/TRAINING_READY.json、REPORT.md、SOURCE_MANIFEST.json、SHA256SUMS.txt、EVIDENCE_MANIFEST.json、ARCHIVE_SCOPE.json；包59416bytes/21成员/20文件，SHA256=d032d67cd76eddbc372ab6f9dd51c8355c4bb1ef3e7469254c2549a3481623a9。
阻塞与下一步：S01明确处理本地FAIL并绑定S00具体部署后按卡给最终结论；S00仅最终PASS后唯一job，每域32/全局64/实际36核/DDR总24GiB/900秒原预算，失败即停，本窗口无job。