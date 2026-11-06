# S00 S07 R7：原四case通过，观察捕获边界分列

唯一2051116/cn21348 SUCCEEDED/exit0，2026-11-06T07:56:11Z—07:58:54Z，新增163节点秒/usage163。01 PASS_FOR_S07_R7_ATOMIC绑定12项SHA/资源/88项工作量/原判据后，重新去重才唯一提交；无补旧case/重试/扩预算。原R6/2050433仍FAIL、原空rank0.json=0bytes及所有旧证据保留。
最终P1部署112105bytes，SHA963ad618d09c998764342f446207d07ee29fcb95818386503ffea6e232de42e4；R7内包44414bytes/17成员16文件15 delivery，SHA57a1f4c530ce2c9a5edcfe9cc9741129fb1ba4f90459fde459803103a362382d。原reader/observer/CPU与旧判据逐字节不变，新comm源42424581db02b15ee8af0c65f85553dff61767979d9644b40fe954f779434608；worker三个rank发布点经同目录独占临时文件完整写/flush/fsync/close再replace，ready不可覆盖语义保持。

| 原顺序/判据 | 本job实际证据 | 原checker接受 |
|---|---|---|
| normal | probe_exit0，双方exit0，固定fp32 shape4 broadcast/SUM/身份/barrier通过 | 是 |
| crash | probe_exit1；rank1 injected_crash/exit17，父child_failed、双方回收 | 是 |
| collective-timeout | probe_exit1；rank0 broadcast真实Gloo超时，rank1 injected_hang，父回收 | 是 |
| watchdog | probe_exit124；双方injected_hang，父deadline、exit[-15,-15]、全部回收 | 是 |

checks.status=PASS_PROBE_CHECKS_ONLY，四项均为这一个job的新原件，无NOT_RUN。故障case自身summary保留FAIL/非零退出，这是原注入判据的要求，未被后处理改写。仅有限小张量协议通过，不是实际同步模型训练/性能或永久Gloo初始化根因修复。此次cn21348初始化顺利，不能把与先前主机不同的一次成功归因成根因已消除。

15本地+15 Linux登录包装/收集夹具及源SHA/CRC/LF/Python3.9 AST/Linux bash-n通过；现场新增17+原71=88方法零skip、环境通过，均在同一consumer预算内。原native job/host/affinity→nonce/request/raw/ready/30秒新鲜度、逐CPU拓扑保持。76分配/两个38物理域，selected0—35与38—73各36，总72实际，reserved36—37与74—75；DDR总24576MB同limit/exclusive/HBM0，job300/全部前置与执行270/共享清理15/收尾15。48份worker完整CPU/TID快照、4份timer绑核和2份helper绑核记录均可核；各rank实际Torch intra-op36，无线程setter扩资源。

八份正式rank报告均为有效完整JSON。crash rank0为10595bytes、stage=broadcast、error已提交；rank1为10544bytes、stage=injected_crash。RANK_REPORT_INVENTORY记录各正式最后checkpoint、checkpoint_end/worker_error、父TERM/reap，未将临时文件提升为正式报告。本次没有残余.rank[01].json.*.tmp；所有隐藏残件仍按收集规则枚举，零条照实记录。受控Linux17项覆盖commit前终止与旧报告保持；这一次真实crash的error记录已提交，不能宣称它恰好在commit前被中断。R6的空JSON/原checks未被改写或替换。

观察结果独立于通信PASS：watchdog两worker的init_process_group均已返回，timer在init_end合法取消，分别早于原deadline-5目标5.918048286/5.918619466秒；两python_stack.txt为0bytes，没有Python栈捕获，不冒称已转储。两份stack_status、两份installed_python（各两个小源码的路径/bytes/mtime/SHA）全部原样保存。
proc helper2882123由原父创建独立session、原生job/亲缘/start_ticks/CPU边界与前后重检一致。两rank共用原2秒窗口，实际采样约0.010804443秒；父记录EXITED/returncode0/reaped=True，没有额外helper等待/预算。8字段中wchan/syscall/mountinfo两rank共6项OK，两项kernel stack为PermissionError(13, Permission denied)，完整保留；不安装、提权或补采。
因此bounded_diagnostic_attempt_completed=true，python_stack_capture_complete=false、proc_fields_complete=false、full_stack_capture_complete=false；原STACK_INVENTORY不完整字段保持，不因helper退出或通信通过而提升。OBSERVATION_REVIEW单独解释合法取消和权限范围，没有伪造空栈内容或改原通信判据。

所属22个PID/start_ticks均退出，remaining_live/processes空，调度PID清空；故障case原父TERM/回收和helper退出现场有据，外层兜底没有额外发信号动作，不把未触发的额外清理分支称现场故障注入通过。实际源码/库、所有终态快照bytes/SHA一致、读取稳定，旧受保护原件不变。
完整证据JOB_2051116_full_evidence.zip：390914bytes/175文件，SHAfc4ebaa826668fe3f72186e2bdf9b67e0998db52f7c86502bce6cbe0dde38b4b；CRC与逐文件bytes/SHA核过，原远端mtime、正式rank/事件/ready/store、空栈、proc权限错误、所有原件/缺项全部保留。
发布前S00曾遗留旧内包文件名于审核绑定，第一草稿尚未READY/提交便发现；旧外包和检查记录保留，改为唯一prepare.ARCHIVE并新增真实包名回归，在全新P1目录重新核包。01将该草稿问题标RESOLVED_BEFORE_FIRST_READY_OR_JOB后才最终放行，没有使用别名包/旧审核或产生额外job。

RUN_COMPLETE绑定本地索引/四case的报告与事件/原checks/观察审计，供协调及S07直接读。本轮无活动job或待运行项；不续跑、不训练、不再R12分块/精度搜索，原fp32基线和旧正式门禁保持，未操作其它任务或共享Git暂存/提交推送。
