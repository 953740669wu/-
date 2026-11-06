# S07 简短状态

- 更新/轮次：2026-11-06，REAL_DUAL_DDP；仅执行本窗口S07节。
- 当前状态：TRAINING_CANDIDATE_FROZEN_LOCAL_NUMERICAL_FAIL_REVIEW_REQUIRED。固定TRAINING_READY已发，供S00打包/S01具体版本审核；不是数值或训练放行。
- 本轮实现：完整原Encoder及两head位于DDP forward，跨rank两个全局分母/反向乘2、原32+32/全局64分片与mask，前5完整B64连续对照，过才同状态续25步。
- 状态与恢复：逐步canonical参数/AdamW名字和张量字节hash、有限梯度/step/cursor、分rank与参考暴露；远端原Encoder/AdamW/RNG/独立mask RNG/游标保存及零额外更新恢复，权重仅回索引。
- 来源：S02冻结包df7275b06d8ee59cd88c0d17c04b0b64f63605ffa1c4410d3d02307ce848eec5，18文件核过；原模型/KML/两reference/INTERFACE锚点实核，原比较器类别/阈值不改。
- 复用边界：R7原件不改，仅复制CPU36与七个job/ready/原子报告小函数，逐函数AST核同；15项初始输入bytes/SHA/mtime末次未变。
- 本地最终：19方法17过/1数值FAIL/1 Linux后代清理skip。已有Torch2.7.1+cpu真实图/RNG/空mask与输入缩放过；两rank Gloo/DDP/backward和梯度一致到达，但完整fp32小B64配对13项有3项失败，不能称小DDP数值通过。
- 失败度量：val.weight/pos.weight相对9.410191e-5；tf.weight绝对3.723800e-5、相对1.142869e-4。原绝对2e-5/相对2e-6不改，未换数据/参考或删失败检查；此诊断已停止。
- 平台证据：默认Python无Torch，按02 READY发现已有venv只读借用，无安装。Windows FileStore停before_pg至25秒父截止；TCP沙箱10013/10049原件保留，沙箱外可到DDP/backward，不能归因为C2故障或声称训练通过。
- 包复核：21成员/20文件/19 delivery，12 Python文件LF/Python3.9 AST通过；隔离包源/共享参考导入通过，默认无Torch解释器16过3skip仅包装证据，不能冲掉真实数值FAIL。
- 冻结包：real_dual_ddp_20261106/package/S07_REAL_DUAL_DDP.zip，59416bytes，SHA256=d032d67cd76eddbc372ab6f9dd51c8355c4bb1ef3e7469254c2549a3481623a9。
- 入口/manifest SHA：train_ddp.py=6a8b3cd69051f149f3b3e6ee786b0ff32a8c3bdf951dfcc635b051df51084e94；SOURCE_MANIFEST=9a124291713f0798df8b4d783f2f8cb36cbeb6f13c0dbe400f9767e1d37db739。
- 资源/预算：各rank独占当前授权38物理核域前36、留末2，总76/72/4；DDR总24576MB同limit/exclusive/HBM0。单job900、共同起点前置+应用840、清理30/收尾30；训练PG120，原R7 pg5/case30不改。
- 固定交接：real_dual_ddp_20261106/TRAINING_READY.json绑定参考/内包/源/config/本卡/命令/收集/本地FAIL；REPORT、TRAINING_CONTRACT、INTERFACE_FOR_S00、minimal.diff、SOURCE_MANIFEST、SHA256SUMS、EVIDENCE_MANIFEST、ARCHIVE_SCOPE列精确范围。
- 下一步：S01须明确处理本地数值FAIL并绑定S00部署具体版本；仅最终PASS_FOR_REAL_DUAL_DDP/review_complete=true可按本卡放行S00唯一job，Linux19方法及02七方法须零skip全过，前5失败即停。
- 活动/未运行：本窗口无SSH、申请资源或job；自建本地短子进程均回收。C2原始初始化/数据归一化/KML模型DDP/完整五步/25步/恢复均NOT_RUN；无补跑、重提、放宽阈值或扩大预算。
- 结论边界：原R7/历史失败保留；工程subject/split UNKNOWN，无val/test；无同job单域对照，性能/扩展效率NOT_MEASURED，无同步训练/收敛接受；未操作共享Git。