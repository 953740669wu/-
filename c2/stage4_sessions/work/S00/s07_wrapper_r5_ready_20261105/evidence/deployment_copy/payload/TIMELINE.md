# 2041165时间线复核与R4修订依据

本次job2041165/cn21338；以原supervisor_begin的同节点monotonic_ns为0。以下值逐行从原事件重新计算，不使用Windows文件时间。原三流SHA/bytes按COLLECTION_S00核验，完整旧失败ZIP和所需原件留在本轮evidence；机读复核为 `evidence/timeline_recheck.json`。

| 原事件 | 相对秒 | 结论边界 |
|---|---:|---|
| rank1 Torch导入结束 | 8.874563692 | distributed/元数据仍需随后完成 |
| rank1 runtime_metadata_end | 9.393871239 | 库身份元数据已返回；随后原init检查点完成并核Torch36/TID |
| rank1 init_process_group_begin | 9.401416219 | 原参数5秒，未等rank0准备完成 |
| rank1 worker_error: Wait timeout | 15.924754694 | 观测间隔6.523338475秒包含事件I/O及调度，不称精确5秒运行时长 |
| rank0 Torch导入结束 | 16.383993928 | 晚于rank1超时；不能再把before_framework解释为永未完成导入 |
| rank0 libtorch_cpu.so SHA开始 | 16.420449274 | 无结束事件；此时尚未完成整套元数据/Torch36及导入后TID检查 |
| 父cleanup_begin / child_failed | 16.567949732 | 原30秒case截止尚未触发 |
| 父向rank0进程组发TERM成功 | 16.569892145 | 是发送信号的观测，不是rank0执行信号处理函数的时刻 |
| 父supervisor_end / all_reaped | 16.676002744 | 退出[-15,1]，原失败与清理保留 |

本次可证实：rank1初始化等待已经耗尽时，rank0连Torch导入结束都尚未记录，因此两侧准备阶段错开侵入了初始化等待窗口。rank0 SHA开始距TERM发送只有约0.149443秒，缺SHA end不能证明该哈希永久卡住。准备耗时差异的底层来源未确定；旧2040233没有同等事件，不能宣布旧job必然同因，也没有排除双方都就绪后仍可能发生的store/loopback/Gloo问题。

R4只把原初始化调用放到双方准备就绪门禁之后。准备完成定义为：Torch/distributed导入与库身份元数据返回、实际Torch intra-op=36、导入后全部可见TID掩码属于本rank selected36，并将该检查点成功写入。原 `worker_ready` 事件仍表示进程早期身份记录，**不等于新协议ready**。

新协议的30秒起点仍是原supervise第一条 `started=time.monotonic()`，覆盖spawn、导入、SHA、CPU/TID检查、就绪等待与后续通信；门禁不新开窗口。准备过慢即使没有进入通信也必须按该预算失败/清理，不通过放宽5秒进程组超时消化准备耗时。

本轮本地受控时钟案例把另一侧ready推迟6.25秒，验证初始化不早于双方合法ready且调用参数仍5秒。这是控制流检查，不是2041165真实Gloo重放，不承诺现场30秒内一定完成。当前全部新通信、同步训练和性能均未运行。
