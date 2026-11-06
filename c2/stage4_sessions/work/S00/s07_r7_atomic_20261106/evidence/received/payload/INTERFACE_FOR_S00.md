# S07 R7固定交接与S00适配

固定目录：`c2/stage4_sessions/work/S07/round7_atomic_reports_20261106/`。先读INTERFACE_READY.json准备，再读ATOMIC_READY.json取得冻结内包/source/manifest/证据SHA。固定新内包为`package/S07_ATOMIC_REPORTS_R7.zip`，17成员=16文件+空evidence/；manifest有15项delivery。不要复用或覆盖R6部署/包/2050433原件。

内包：candidate四文件、tests六文件、allocation.template.json、REPORT.md、INTERFACE_FOR_S00.md、原字节OBSERVATION_CONTRACT.md、minimal.diff、SOURCE_MANIFEST.json。minimal.diff仅运行源comm_probe的一个函数及三个调用；新测试单独随包。所有10份Python为LF/Python>=3.9。原run_checks/cpu36_contract/stack_observer/观察契约和五份测试SHA必须与R6相同。

## 检查命令与实际计数

S07_PY为已核解释器，S07_RUN为新包隔离解压根；工作在该根，evidence可写。新增组建议首先运行，标准库检查不导入真实Torch。

```bash
"$S07_PY" -B "$S07_RUN/tests/test_atomic_reports.py"
"$S07_PY" -B "$S07_RUN/tests/test_stack_observer.py"
"$S07_PY" -B "$S07_RUN/tests/test_readiness.py"
"$S07_PY" -B "$S07_RUN/tests/test_diagnostics.py"
"$S07_PY" -B "$S07_RUN/tests/test_job_identity.py"
"$S07_PY" -B "$S07_RUN/tests/test_probe.py"
```

实际方法17+27+16+6+6+16=88，原71+新增17。Windows本地87过1原Linux清理skip；Linux唯一job须88全过且零skip。新增组可沿原包装单步30秒上限，但全部检查、环境、四case、观察及清理仍共享原consumer270/job300，不追加预算。不要用旧71或只17计数。

## 资源与原契约

| rank | 授权边界 | 实际CPU边界 | 预留 |
|---|---|---|---|
| 0 | 当前job原生授权的第一38物理核域D0，须现场拓扑和receipt一致 | sorted(D0)[:-2]，36核；每个TID不得越出自身selected | sorted(D0)[-2:]两核不使用 |
| 1 | 同job同节点另一38物理核域D1，与D0不交叠 | sorted(D1)[:-2]，36核；每个TID不得越出自身selected | sorted(D1)[-2:]两核不使用 |

总76分配/72实际/4预留，DDR总24576MB同limit/exclusive，HBM0；每rank实际Torch intra-op=36。CPU号由原生授权receipt决定，不从旧job复制；helper及两worker身份/session/亲缘/start_ticks/CPU校验、外层owned清理沿原契约。启动worker前及导入Torch前CCS_JOB_ID检查保留，不伪造job/PID/ready。

pg timeout=5秒；case总监督30秒，起点及TERM/KILL/清理宽限逐字节不改；watchdog原case起点+25秒一次栈、proc总2秒及取消机制不改。cases必须normal→crash→collective-timeout→watchdog同job各一次、失败停止。原reader对缺/空/残JSON、双rank和注入点均原样；到截止并清理不等于到注入点。

## 临时残件收集及报告含义

各case同目录可能存在`.rank0.json.*.tmp`、`.rank1.json.*.tmp`，包括隐藏、零字节、半份、完整但未提交；收集器必须保留这些原始残件，记录路径/bytes/SHA256/远端mtime，不能只匹配非隐藏`*`。不要将它们作为正式报告、覆盖rank.json或在收集前删除。每个写入只处理自己创建的路径；SIGTERM不新增等待或补写。

正式rank.json只表示最后已replace的完整checkpoint。crash rank0可能仍为broadcast且没有error；需同原events核最后checkpoint_end、worker_error、TERM与回收，不能声称异常处理报告一定提交。若从未发布则缺失，原检查必须FAIL；空/残正式报告仍FAIL。原ready/store/事件/summary/检查、CPU/库/源码、全部栈与proc原件/缺项继续按R6收集。

## 唯一现场入口及版本门禁

S00新部署发布S00_DEPLOYMENT_READY，S01同具体内外包及所有SHA的PASS_FOR_S07_R7_ATOMIC/review_complete=true后，S00直接执行任务卡授权的唯一新job。S07只交固定文件，不提交job。原入口为：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" \
  --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

独立新目录、实际队列/系列marker去重及单次提交门禁由S00负责。所有前置共享300/270预算，失败停止、无补case/重试/延长。旧失败及当前新现场尚未运行边界保留；正常小张量PASS不能推出整组、同步训练或性能接受。
