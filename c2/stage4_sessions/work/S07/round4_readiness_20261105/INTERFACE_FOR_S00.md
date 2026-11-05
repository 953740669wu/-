# S07 R4：双方就绪后初始化，S00适配提案

状态：READY_FOR_REVIEW / LOCAL_ONLY。仅本地交付；本轮未提交/授权job。S07自身R4与S00已有wrapper R4编号独立，后者原件不改。

## 内包与成员

新包 `package/S07_READY_SYNC_R4.zip`，bytes/SHA见同轮外部 `SHA256SUMS.txt`。包内13个文件及1个空evidence目录，共14成员；SOURCE_MANIFEST有12项delivery（不递归索引自身）。包含candidate三文件、tests四文件、allocation模板、REPORT/TIMELINE/本接口、minimal.diff及SOURCE_MANIFEST。

CLI不变，原Gloo/lo/file-store、四case顺序/故障判据、张量值、CPU36、现场CCS_JOB_ID检查、总DDR24576MB、270秒consumer/300秒job提案保持。

## 就绪协议

1. 原父监督器从原位置开始30秒计时，生成该起点+30秒的绝对monotonic deadline，通过自己的 `S07_CASE_DEADLINE_NS` 传给两个子进程；不从allocation或worker重新计算30秒。此变量仅为本探针内部期限，不能代替调度器原生CCS_JOB_ID。
2. manifest增加每次全新生成的128-bit `ready_token`。父Popen两rank后，将 `{run_id, job_id, ready_token, pids:[实际rank0 PID,实际rank1 PID], deadline_ns}` 原子发布为case目录的 `participants.json`。发布错误进入原launch_failed清理路径。
3. worker完成导入、全部库身份元数据、实际Torch36及新增after_framework CPU/TID检查点后，记录preparation_complete。核对participants身份、原deadline与自己的真实PID，再原子发布 `ready_rank0.json` 或 `ready_rank1.json`，字段严格为 `{run_id, job_id, ready_token, rank, pid}`。
4. 读到两份合法ready才记录both_ready并进入原init_process_group；进入前再次检查原deadline，原pg_timeout仍5秒。缺文件只在剩余原预算内等待；旧run/job/token、错rank/PID/字段类型、半JSON、旧自有ready或写入错误立即失败，不重试覆盖或跳过门禁。
5. participants/ready先写同目录独占临时文件，flush/fsync后os.replace；错误不采用record_event的日志容错，不能把诊断I/O错误放行变成就绪放行。临时残件保留作失败证据，旧输出目录不重用。

各rank的ready只证明已完成本轮准备，不保证之后不会退出；peer失败仍由原监督器/5秒通信超时及原清理处理。整个等待是同节点协议，不扩成跨节点训练平台。

## 本地复核命令和结果

以下不需要Torch/Gloo，使用标准库、假框架及受控时钟；S07_RUN为本轮隔离解压根：

```bash
python -B "$S07_RUN/tests/test_readiness.py"
python -B "$S07_RUN/tests/test_diagnostics.py"
python -B "$S07_RUN/tests/test_job_identity.py"
python -B "$S07_RUN/tests/test_probe.py"
```

实际方法数为16+6+6+16=44；本轮Windows/Python3.11为43通过、1项Linux组清理跳过。新增16项覆盖6.25秒准备错开后才调用假初始化、run/job/token/rank/PID/期限错误、半文件/缺ready、原剩余deadline、ready刷盘致命错误、parent真实PID、peer/启动/参与者发布失败以及等待时有界回收。原Linux44项尚未运行；2041165的原28项Linux全过属于旧包历史。

## S00新执行层必须适配的确切位置（提案，未实施）

- 在自己的新版本固定新包名/SHA/bytes/14成员；原prepare固定31262bytes/旧SHA/13成员/11项delivery/12实际文件，不能替包沿用。新的check_members应为12 delivery、13实际文件、1个evidence目录，pre_submit payload_files数量及consumer检查改为13。保持LF/Python3.9语法/逐文件SHA门槛，另生外包SHA。
- 原CHECKS三组保留6/6/16，新增 `('readiness_tests','test_readiness.py',16,30)`（建议放原诊断组之前）；总通过数改44且Linux仍不允许跳过。沿用270秒统一剩余预算，不把这30秒追加到consumer或300秒job之外，任一检查失败即停。新执行层及部署检查需由S00/协调另核，不直接修改旧包装器。
- 保留当前nonce/request/raw/ready调度授权交接、两域原件/逐核拓扑、原生CCS_JOB_ID及无LD_PRELOAD环境。不得预先伪造participants或rank ready，也不得从旧2041165复制0—75授权。rank0/1各自使用当前授权域前36物理核、各留末2；具体域号和CPU清单以新job原件为准。
- 原trace_inventory可继续核旧事件完整性，但不等于已核新门禁。新增收集/复核participants、两ready及.tmp残件、manifest.ready_token与summary.pids；检查每rank准备完成→自己ready_published→both_ready→初始化尝试的次序及原总deadline。跨rank不要以ready_published日志时刻作为原子发布的精确时点：peer可能在发布后、记录该事件前就读取文件。TRACE_WRITE_ERROR继续标诊断不完整，不能绕过ready的强校验。

核包并另获一次明确授权后，只有在该新job内生成合法allocation并通过前置检查，才运行原四case入口：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" \
  --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

normal失败即停，不单跑再重跑suite；原crash/collective-timeout/watchdog注入点及接受条件不改。就绪失败不算故障注入成功。保留完整rank/父events、原JSON/log、commands/manifest、原始调度终态和各step清理回执，以及mtime_ns/bytes/SHA。5秒通信、30秒原case监督和原TERM/KILL/wait不放宽；本地毫秒耗时不预测现场I/O开销。

正式全局batch、学习率、schedule继续待定；该修订不是通信/同步训练/性能通过。
