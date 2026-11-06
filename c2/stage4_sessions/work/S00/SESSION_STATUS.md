# S00简短状态

- 更新/轮次：2026-11-06；S07_R7_FULL_PROTOCOL_PASS_CAPTURE_LIMITS_RECORDED；目录s07_r7_atomic_20261106。
- 终态：01同12项SHA/资源/88项工作量/原判据PASS_FOR_S07_R7_ATOMIC后，唯一2051116/cn21348 SUCCEEDED/exit0；07:56:11Z—07:58:54Z，新增163节点秒/usage163；1新job、0重试、无活动S00 job。
- 原四case：同一job按normal→crash→collective-timeout→watchdog各一次，原checks全接受，probe_exit分别0/1/1/124；normal固定张量PASS，crash注入exit17/父回收、真实collective超时、watchdog双方injected_hang/原deadline清理均成立，无NOT_RUN。不是多域模型训练/性能接受或永久初始化根因修复。
- 正式报告：八份rank JSON均完整且身份有效；crash rank0为10595bytes、stage=broadcast且error已提交，原reader通过。当前原子tmp残件0条，枚举规则保持；中断保全由本job受控原子检查支撑，不声称实际crash恰在commit前被中断。R6原0bytes/FAIL未改。
- 准备与Linux：15本地+15 Linux登录包装夹具及SHA/CRC/LF/AST/bash-n通过；实际新17+旧71=88方法零skip、环境通过。原reader/observer/CPU、四case/pg5/spawn前起case30/清理宽限不变，S00未热改payload或从tmp补正式报告。
- 资源与CPU：76分配/两个38物理域，selected0—35与38—73各36、共72实际；reserved36—37与74—75；DDR总24576MB同limit/exclusive/HBM0，job300/共享270执行+15清理+15收尾。48 worker CPU/TID快照和4 timer+2 helper绑核记录可核，各rank Torch intra36、原库一致。
- 观察分判：bounded_diagnostic_attempt_completed=true；两Python timer因init_end分别在目标前5.918048286/5.918619466秒合法取消，两个python_stack.txt均0bytes，python_stack_capture_complete=false。proc helper2882123完成/reaped/rc0，两rank共用2秒内约0.010804443秒采样；8字段6 OK、两个kernel stack均PermissionError13，proc_fields_complete=false、full_stack_capture_complete=false，不造栈/提权/补采。
- 原生身份与清理：CCS_JOB_ID/host/affinity、nonce/request/raw/ready SHA及30秒新鲜度一致，源码/库/所有终态快照无漂移、旧受保护原件不变；所属22 PID全退出、remaining_live/processes空、调度PID清空。原父故障清理现场有据，外层未追加兜底信号。
- 交接：RUN_COMPLETE.status=RUN_COMPLETE绑定四case/正式报告/events/原checks/索引/审计；OBSERVATION_REVIEW单列合法取消与权限范围。ZIP390914bytes/175文件，SHAfc4ebaa826668fe3f72186e2bdf9b67e0998db52f7c86502bce6cbe0dde38b4b；RUN_REPORT/SHA256_INDEX/ARCHIVE_FILES同目录，供协调/S07直接读。
- 版本与保留：最终P1外包112105bytes SHA963ad618d09c998764342f446207d07ee29fcb95818386503ffea6e232de42e4；内包44414bytes SHA57a1f4c530ce2c9a5edcfe9cc9741129fb1ba4f90459fde459803103a362382d；01原件SHA8493beccf28ed9fe760ff2dd73a157147897aa551860c87aac476956e12b79bd。发布前旧文件名草稿错误及检查/外包保留，01已标发布前解决，没有多余job或旧READY。
- 下一步与边界：交协调/S07基于同一整组新证据安排后续；本轮无待运行项，不追加通信/补case/重试或训练。R12无收益结案保持原fp32基线，不搜索tile/精度、不改旧门禁，未写其它任务或操作共享Git暂存/提交推送。
