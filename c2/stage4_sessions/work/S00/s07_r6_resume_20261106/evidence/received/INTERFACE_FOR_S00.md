# S07 R6内包与S00适配提案

状态：READY_FOR_REVIEW_LOCAL_ONLY；本轮只本地检查/打包，无job授权。S00原wrapper R5及S07 R4/R5原件不改。

## 新内包

`package/S07_ALIGNED_STACK_R6.zip`；实际bytes/SHA以本轮外部 `SHA256SUMS.txt` 为准。16成员=15个文件+1空evidence目录，SOURCE_MANIFEST有14项delivery。内容为candidate四文件、tests五文件、allocation模板、三份说明、minimal.diff和SOURCE_MANIFEST。

已有comm_probe的集成变更见minimal.diff；新增stack_observer.py和test_stack_observer.py作为独立文件随包，SHA在manifest，不依赖S00源码。所有执行文件LF/Python>=3.9；原CPU36、run_checks.py与四份旧测试逐字节不变。

## 离线复核命令

S07_RUN为新包隔离解压根，S07_PY为复核解释器。下面不导入真实Torch/初始化Gloo：

```bash
"$S07_PY" -B "$S07_RUN/tests/test_stack_observer.py"
"$S07_PY" -B "$S07_RUN/tests/test_readiness.py"
"$S07_PY" -B "$S07_RUN/tests/test_diagnostics.py"
"$S07_PY" -B "$S07_RUN/tests/test_job_identity.py"
"$S07_PY" -B "$S07_RUN/tests/test_probe.py"
```

实际方法27+16+6+6+16=71。本机Windows/Python3.11：70过、1项原Linux组清理跳过；新27方法全过。包含一次真实本机faulthandler转储（CPU门禁用夹具）及真实挂起标准库helper的kill/poll回收；Linux/proc、C2线程继承、原生栈权限和Python3.9现场均未实测。不能把fixture/proc数据写成计算节点结果。

## S00新版本须明确适配（仅提案）

1. 固定本次新包名/实际SHA/bytes/16成员；prepare的delivery数14、实际文件15，consumer pre_submit payload_files数量改15。不能覆盖旧包后沿用34295bytes/旧SHA/14成员/12 delivery/13文件。逐字节manifest、LF/语法、部署独立副本检查继续保留，另交新外包SHA。
2. 保留原16/6/6/16四组检查，增加 `('stack_observer_tests','test_stack_observer.py',27,30)`（建议先于其余组），Linux通过总数应为71且无跳过。全部仍共享原270秒consumer，不能叠加30秒到总预算外；job提案仍300秒/总DDR24576MB/76分配72实际/HBM0。
3. 原生CCS_JOB_ID、nonce/request/raw/ready授权交接、原逐CPU拓扑、每rank selected36及4个预留核不变。S07_CASE_DEADLINE_NS由原supervise起点生成；新增S07_PROC_TASK只在父helper启动时内部传递，S00不得预制或从JSON伪造作业号/PID/start_ticks。
4. run源码身份需新增candidate/stack_observer.py；原case manifest/source_sha256会列它。新helper是父监督拥有的独立session，原外层owned-session采样/有界清理必须继续覆盖，不能只收两worker PID。S07父receipt记录helper_pid/kill时刻/returncode/reaped，若UNREAPED必须按外层失败/残留真实记录。
5. 新观测文件必须原样收集：watchdog/rank{0,1}.python_stack.txt、rank{0,1}.stack_status.json、rank{0,1}.installed_python.json、proc_identity.json、proc_fields.jsonl、proc_summary.json、proc_helper.log，连同原events/summary/participants/ready/store与全部残件、bytes/SHA/远端mtime。文件可能缺失/空/部分完成，不能补造。
6. 原readiness/trace清单继续保留，但不足以单独证明取栈完成。需独立核：两rank目标相同且等于原deadline减5秒、ARMED/MISSED/取消时刻与文件生命周期、栈原文非空及其scope、helper基准/重检start_ticks/parent/session/CPU与目标+2秒窗口；权限错误和采样超时标INCOMPLETE。helper EXITED仅是进程状态，proc_summary记录字段可用性；都不是通信PASS。

## 后续入口与停止条件

协调核具体内外包并另行安排后，仅在新合法job目录通过原授权/环境与新71检查，才用原入口：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" \
  --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

正常前三case不启用取栈或proc helper；watchdog先按原ready机制完成准备，原初始化/身份收集/注入点不动。normal/crash/collective-timeout/watchdog仍顺序一次、异常即停、不重试；不先单跑watchdog后拼旧三项。若未到injected_hang，即使原截止/新栈工作仍整组FAIL。

观察细节与已实现边界见OBSERVATION_CONTRACT.md。本轮无集群job/补跑/预算放宽，2041919原FAIL和全部旧失败保留；正式batch/LR/schedule与同步训练/性能接受仍待定。
