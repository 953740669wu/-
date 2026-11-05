# S07 R3诊断候选接口：仅补阶段观测，尚非故障修复

状态：READY_FOR_REVIEW_DIAGNOSTICS_ONLY / ROOT_CAUSE_UNDETERMINED。此处R3为S07自身修订；S00已有wrapper R3保持原样。**本轮未提交或授权新job，未经具体包/执行层提案复核不得重跑。**

## 交付与变化

- 新内包为 `package/S07_INIT_DIAGNOSTIC_R3.zip`；SHA/bytes见外部 `SHA256SUMS.txt`。包内平铺candidate/、tests/、allocation模板、SOURCE_MANIFEST、diff及本轮说明，按SOURCE_MANIFEST逐文件核验。
- 候选只补 `record_event` 和调用点：rank各自追加 `rank0.events.jsonl` / `rank1.events.jsonl`；父监督追加 `supervisor.events.jsonl`。原JSON/summary/stage字段和退出判据保持。
- 每条事件记录epoch纳秒、monotonic纳秒、写入PID；worker首条绑定rank/job/run，父spawn绑定child_pid。事件分别标识Torch/distributed导入、runtime元数据/逐库SHA、checkpoint、init_process_group入口/正常返回或错误，以及父清理原因、成功发送的信号/直接终止、wait回收。
- 事件追加后flush+fsync。时间为事件采集时刻，阶段间隔含日志I/O开销，不称纯导入或通信性能。未测现场共享盘刷盘成本；原证据mtime毫秒倒置问题不能通过新代码倒填旧时间。
- 诊断I/O报OSError时打印 `TRACE_WRITE_ERROR`，不抛异常跳过原清理、不重试。若出现该提示、缺行或截断末行，本次诊断证据不完整；不得把缺end事件单独判为永久阻塞。原通信数值/故障接受逻辑不因此变化。
- CPU36合同、原生CCS_JOB_ID门禁、allocation/原始调度核验、Gloo/lo/file-store、张量值和四case检查器不变。没有就绪barrier或超时放宽。

## 本轮实际离线命令

任意隔离副本根作为S07_RUN；不需要torch，不初始化Gloo：

```bash
python -B "$S07_RUN/tests/test_diagnostics.py"
python -B "$S07_RUN/tests/test_job_identity.py"
python -B "$S07_RUN/tests/test_probe.py"
```

本轮6项诊断检查全过，6项身份检查全过，原16项15过1项Linux组清理跳过，共27过1跳过。诊断使用假框架模块、合成Wait timeout与真实标准库子进程；证明新增观测可区分入口/完成及清理，不复现2040233根因、不证明真实通信通过。旧job2040233的Linux22项全过是另一次历史实测。

## S00执行层变更提案（未实施）

已有 `s07_wrapper_r3_20261105/prepare.py` 固定旧R2包名、59801bytes、SHA和34项条目，不能把新ZIP覆盖成旧名或只换payload文件。S00须在自己的新版本中固定新内包身份/条目数，重新生成pre_submit_checks并复核打包/部署SHA；原wrapper、旧失败包和共享环境不得改写。新的条目数与SHA以本次交付实际包为准。

原执行层原生job/nonce/raw/ready/30秒交接、76核两域sysfs、DDR24576MB及同值limit、exclusive、270秒consumer和300秒job总界限保持。原两组检查仍为6/16方法，断言无需改变；新增6项诊断检查交S00在新执行层按剩余总预算安排（建议单项上限30秒），失败即停、不重试；具体执行层仍需另行复核。不得叠加预算使总job超过300秒。

核包后、另有一次明确授权的新job内，由新执行层生成同job的allocation.json并核环境；随后**原四case入口**仍为：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" \
  --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

它依次normal/crash/collective-timeout/watchdog；normal失败即停，不额外单跑normal再重跑suite。每case仍pg_timeout=5秒、deadline=30秒；原清理共享宽限2秒、每child wait上限2秒不变。fsync等I/O成本尚无现场测量，原外层剩余时间/作业边界继续有效；不以本地毫秒测试许诺现场硬实时界限。

若原normal失败重现，下次回传双方events全文件、原rank JSON/log、父events/summary、commands/manifest及原mtime/bytes/SHA，连同S00各step开始结束/清理、调度终态。先以同节点monotonic比较阶段顺序及区间，epoch用于对照外层时钟；确认日志完整再讨论根因。若依然无法缩窄，交回证据缺项，不现场加时/换store/改判据。

rank0只在自己的授权NUMA域A0内选其域前36核；rank1在实际另一授权域A1内选前36核，各留末2核且A0∩A1为空；实际域号/逐CPU列表由该新job原件决定，不从2040233沿用0—75授权。无新真实通信/节点小时；正式batch/LR/schedule继续待定。
