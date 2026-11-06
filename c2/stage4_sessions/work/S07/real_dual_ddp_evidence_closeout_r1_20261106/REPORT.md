# S07 诊断R1只读证据收尾

本轮完成的是“缺口如实定稿”，没有补齐历史进程清理证明。原诊断、READY、FAIL和冻结包均不改。每项原件的绝对路径、bytes/SHA、字段原值和SUPPORTED/UNSUPPORTED/NOT_RECORDED分类见EVIDENCE_CLOSEOUT.json；核对56项来源，只定向读取原目录和明确引用原件。

| 路径/角色 | Popen PID | compute PID | 已支持的范围 |
|---|---:|---:|---|
| full | 111828 | 124816 | 同逻辑路径的两套PID不同 |
| sequence | 121848 | 117608 | 同逻辑路径的两套PID不同 |
| fp64 | 123160 | 未记录 | 仅有Popen句柄记录 |
| DDP rank0 | 116596 | 118980 | 同逻辑rank的两套PID不同 |
| DDP rank1 | 111740 | 123980 | 同逻辑rank的两套PID不同 |

RUN命令顺序、mode/rank和initial字段支持上述逻辑关联，但没有PPID、创建身份或原生父子事件，实际后代归属仍UNKNOWN。虚拟环境解释器路径可核，不能据此认定PID差异必由启动器转接造成。

四份supervision和controller原文支持5个直接Popen句柄的退出码及all_reaped记录。DDP的cleanup_seconds=0.016、seconds=2.719也只属于该监督列表；源码Windows分支仅对这些句柄terminate/kill/poll/wait。没有实际compute及其后代的TERM/KILL/退出时间、完整后代清单或15秒内回收链，因此“全部实际工作进程及后代在15秒内回收”不获支持，结论为UNKNOWN，不能改称实测清理失败。

上轮短状态/报告“双方、五个自建子进程均回收”表述过宽：本轮将状态收窄为“有5个Popen句柄回收记录”。原文和READY的all_owned_children_reaped=true原样保留，本收尾明确其证据限制。

01的CURRENT_PID_CHECK仅记录2026-11-06T10:42:27.6659060Z没找到四个已知compute PID；它不证明何时退出，也不覆盖未知fp64计算PID和完整后代。本轮没有再查询PID。RUN起点、相对耗时、文件mtime和计算hook时间均不冒充进程退出事件；未合成缺失时间戳。

fp64命令使用同一已记录解释器，源码无调线程调用；但fp640.log为空、无fp64_initial，控制结果没有自身PID/实际线程字段，仍NOT_RECORDED。01后续指标读取进程的8线程不能代替原fp64快照。新四进程初态/RNG摘要及8/8设置可核，旧失败的实际初态/线程/中间向量、原始初始参数张量和精确native内核证据仍无法恢复。

两份raw归档仅以ZIP/pickle元数据opcode只读检查，未反序列化张量；可见PID、初态摘要、计算hook时间和梯度记录，没有父PID/创建/退出字段，不能补齐生命周期链。额外DDP效应仍UNKNOWN；原DDP未完成PG，后续验证仍NOT_RUN。

本轮0模型、0测试、0收缩、0DDP/通信、0进程查询、0远端扫描、0安装/提权/job/Git操作。没有改原数值阈值或训练FAIL，也不把可归档解释为清理/数值/训练通过。无需要02回答的具体疑点；交01核能否按“有限诊断、缺口保留”归档，不等待新实验。
