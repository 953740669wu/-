# 首步诊断实际入口

从 `namespace_continue_20261110/M1_NS1_D1` 的冻结包派生。变更只有 `launch.py`、`worker.py` 及新增 `first_error_trace.py`。原内核、派发、比较器、CPU36 和固定数据 SHA 不变。绑定 `58d607a7118f800c2a766dc85fa64f2023dcecbefaf2968669fc126740872868`，包 `c2c468a3728656be11de92fb2852359af9ad3de2868d227e9115ae8673288cec`。

使用 `wujunyi`，从 `/home/share/wujunyi/opt/stage4_sessions/S00/ATTN_R1_M1_FIRST_ERROR_D1` 执行冻结包 SHA、`prepare.py`、`inspect_metadata.py`、`recheck_fixed_inputs.py` 和 `submit_once.py` 原入口。提交参数见 `RUN_BINDING.json` 和原始 `submission.command.json`。本轮唯一诊断 `2085723`，2026-11-10 UTC 15:41:42 创建、15:41:43 获配 cn22036，38 核、DDR 请求与限制各 24576MB、900 秒原生上限。计算监督时钟 `min(START+wall-120, START+300)`。

原 SDPA 与 M1 都按原完整训练入口运行首个更新，记录原输入、掩码、初态、CPU36、命名空间和实际前反向。12 层各取 8192 个预定义位置。第一层注意力的 Q/K/V 全量做逻辑字节 SHA，两侧一致时比较整个注意力输出，保留差值最大位置所属的一个头的 Q/K/V 和两侧输出。参考完整注意力及最后隐藏输出只在作业内暂存，退出时清理。比较发生在更新之后，比较用的隐藏输出来自更新前的同初态前向。此作业只作误差诊断。

`2085723` 结束于原比较器的 `1.output.h` 数值拒绝，原生 FAILED。诊断计算段 64.311 秒、原生分配 68 秒。通过 `djob -J`、`getconf CLK_TCK`、固定数据哈希复核、`/usr/bin/python3 -B collect.py "$PIN"`，再以 `tar -czf JOB_2085723_TRANSFER.tgz JOB_2085723_evidence.zip bundle_receipt.json` 归档。传输 SHA `03c6c81328f322230b3d267c2091eecbf73f3794a6ee01d8c8997a3cf3d04303`，本地用 `settle_diagnostic.py` 校验并按原预算结算。北京时间 23:44:00 四个历史原生 ID 终态、PID 空，`wujunyi` 活动列表为空。快照清理记录包含两个临时参考张量，已归还 HBM 页池。
