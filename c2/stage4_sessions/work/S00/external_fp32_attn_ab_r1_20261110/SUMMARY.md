# 32 电极 B32/CKPT12/HBM 外部 FP32 attention

保留 11 月 3 日模型的整条 `mask_tok` 替换语义、固定 800 帧、初态、AdamW、原 FP32 KLinear 和 HBM 分配器。外部内核仅提取 BQ64 的 FP32 前向及默认双 pass 反向。C 分配失败经 ABI 返回 Python，候选派发遇不支持输入即停止。冻结 SHA 见两份 `RUN_BINDING.json`，构建产物和 locking KML、OpenMP 身份见 `ATTN_BUILD.json`。

| Job | 版本 | 实际资源和结果 | 数值与派发 | 终态 |
| --- | --- | --- | --- | --- |
| 2085024 | V1_D1 | cn22036，继承 38 核，调度交接的时间戳检查失败 | 编译和模型未运行 | FAILED，PID 空，子进程清理 |
| 2085051 | V2_D1 | cn22036，1/1 域，36 实际核，24 GiB DDR，HBM 容量及 allocator 检查通过 | C 构建和映射通过，SDPA 参考 5/5 步，候选 0 前向/0 反向/0 比较 | FAILED，后代已回收，HBM 页池归还 |

V2 只修调度交接。现场首读时登录端 header 比计算端本地时间领先约 81 毫秒，等待约 100 毫秒后满足原顺序和新鲜度。候选另在 `cpu36_guard.checkpoint(..., "after_backend", ...)` 停止。`runtime_info()` 对 `/proc/self/maps` 读到的 KML 路径统一用 `ctypes.CDLL(..., RTLD_NOLOAD | RTLD_LOCAL)` 探测。候选已确认映射单独 `dlmopen` 命名空间中的 locking KML，之后该探测报 `OSError('dlopen() error')`。候选尚未进入训练，无法判断融合的数值。证据支持将独立命名空间库的路径、SHA 和原生命名空间身份单独校验，同时保留原基础库、线程数及全 TID 检查。此改动未实施。

两版额度已用。候选未采用，四域和 16 域的严格门、三对整体吞吐、内存、慢域及 5% 稳定门均未运行。单域严格参考的步末驻留 3582 MiB HBM，严格阶段 RSS 高水位加步末 HBM 估算 4413.81 MiB，包含数值快照路径，不能作为性能态内存对照。未观察到 SIGBUS 或明确 OOM。历史 4090 为 BF16/B64 demo，仅见 S11 文档，未连接 GPU 或作比值。

实际使用 2/6 次提交、1/3 台主机、5 秒排队、116 秒计算分配、5 次有记录更新。因候选阶段已启动 worker，按该阶段上界共记 10 次更新。两原生作业终态、无计算残留、无活动作业。
