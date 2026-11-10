# S00 外部 FP32 attention R1

预算从北京时间 11 月 10 日 22:04:34 起算，11 月 12 日 22:04:34 截止。继续使用 `wujunyi`，独立于 R2。外部 S11 评审 SHA 已核，冻结源仅移植 FP32 BQ64，保留旧模型掩码、KLinear、数据、AdamW、CKPT12 和 HBM 库。

单域 `2085024` 在调度器登录端与计算端时间戳交接处终态失败，6 秒分配，未编译 C 或执行模型，PID 和清理均已核。第二版只加有界时间戳等待，内核和派发 SHA 不变。V2 单域终态前不进四域。4090 仅历史文档对照。

结案 `BLOCKED_CPU36_LIBRARY_NAMESPACE_AFTER_TWO_VERSIONS`。V2 `2085051` 在 cn22036 单域通过资源、原 HBM 库、C 编译链接及 5 步 SDPA 参考。候选库和 locking KML 映射成功，随后 CPU36 的 `runtime_info()` 对映射路径执行 `RTLD_NOLOAD` 报 `OSError('dlopen() error')`。候选 0 前向/0 反向，0 更新、0 数值比较。四域与 16 域未运行，候选未采用，旧原件保留。两版已用完。

两原生作业均为 FAILED、已取回并核终态和进程清理，实际用过的 HBM 页池归还。当前无活动作业。预算 2/6 提交、1/3 主机、排队 5 秒、计算分配 116 秒，确认 5 更新，保守记账 10。结果 `FP32_ATTN_AB_RESULT.json`。
