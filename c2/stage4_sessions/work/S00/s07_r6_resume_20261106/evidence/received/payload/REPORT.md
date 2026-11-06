# S07 R6：单次对齐取栈实现与本地检查

2026-11-05。状态：READY_FOR_REVIEW_LOCAL_ONLY；观测实现完成，不是2041919根因修复或通信验收。本轮未SSH/补跑/申请资源/提交job。

## 结果与范围

只在S07新目录实现watchdog原case绝对起点+25秒的一次Python取栈，以及同一目标下共用最多2秒采样窗口的独立proc helper。父监督不等helper结果，不使用无界wait/join；旧5秒通信、30秒原起点、注入点、四case故障判据及原worker清理保持。S00文件、已投R4、R5分析和旧失败不改。

源为已投R4候选及已评审R5提案，19项改前来源SHA/mtime见 `evidence/reference_sources.json`，结束前核验见source_recheck.json。本轮前短状态在evidence/before保留；新模块/包身份在SOURCE_MANIFEST及SHA256SUMS。最小集成diff仅comm_probe.py，新增观测模块和检查文件独立随包。

## 已实现

- worker只在watchdog绑核/原生job门禁后、导入前设置一次timer；按deadline-5秒计算剩余延迟，开文件耗时导致错过也标MISSED，不补设。repeat=False/exit=False，cancel先于close；初始化结束及finally均调用幂等取消。取消失败保留描述符引用，并保留首个取消原因。
- 设置前后检查诊断线程TID CPU边界；安装的distributed_c10d/rendezvous小Python文件在准备阶段记录真实路径/SHA和必要函数调用的静态位置，不改共享源码、不在采样窗口重复大库哈希。
- helper只操作父实际创建的两worker，native job/父/session/start_ticks与CPU重检；每rank采样前绑定其selected36，未扩大初始授权。只取主TID wchan/syscall/可读native stack、mount及有限FD线索，权限错误/空/截断原样保留。
- helper单独alarm与父非阻塞poll/kill共用原目标+2秒截止，TimeoutError不得按普通字段权限错误吞掉；正常、异常与超时在原共享cleanup内回收。未退出则显式UNREAPED，由原S00外层覆盖，不伪称回收。文件/诊断失败不跳过原worker清理。

详细时序、文件生命周期、helper身份与预算见 `OBSERVATION_CONTRACT.md`，参照其中Python3.9官方说明。ARMED并非已取栈，helper EXITED并非proc字段有效，不提升为通信PASS。

## 本轮实际检查

先写取栈检查，模块未实现时运行失败；另保存辅助预算异常、日志关闭错误、取消原因等针对性红灯，再修正复跑。原始红灯日志在evidence/，没有把这些本地失效注入称为真实Gloo故障复现。

| 检查 | 实际结果/边界 |
|---|---|
| 新27方法 | 全过：绝对触发/不重置/一次、错过、先取消再关闭/取消错误保留FD、job与CPU错误、安装源SHA/调用位置、proc权限/空值/超时/旧PID/父/CPU边界、真实helper回收、集成正常/异常取消及原父截止 |
| 真实本机timer | 短延迟一次Python栈输出通过；CPU guard为夹具，不能称C2 Python3.9/CPU36实际通过 |
| 真实本机helper | 标准库挂起子进程被kill并poll回收，无无界join；不代表Linux native/proc权限可用 |
| proc/受控时钟 | 夹具验证两rank共享目标+2秒，晚唤醒只用余量、错过不重置、alarm不被吞掉；无Linux实际采样结果 |
| 原44方法 | 43过/1项Linux组清理跳过；CPU36/原生job/ready/原四case接受检查未改 |
| 合计 | 71方法：70过1跳过；独立解压复核见deployment_checks.json，不把子场景另计 |
| Python3.9 AST | 9个Python文件仅语法通过；本机实际Windows/Python3.11 |
| 新Linux/Gloo/C2/原生栈 | 未运行；真实FS/内核不可中断I/O和调度时效尚无现场证明，保留实际时钟/超期/UNREAPED而非宣称硬实时 |

命令/退出与详细日志在 `evidence/local_checks.json` 及各test_*.txt。源码预检和mock不是科学数值/性能验证，旧2041919的44项Linux及三case有限PASS仍为历史，整组FAIL不变。

## 交付与下一步

内包 `package/S07_ALIGNED_STACK_R6.zip`，16成员（15文件+空目录）、14项delivery；SOURCE_MANIFEST逐源、SHA256SUMS列包/diff/核心SHA，EVIDENCE_MANIFEST索引本轮证据。`INTERFACE_FOR_S00.md` 具体列明新数量、71检查、helper session/观测文件收集及原270/300预算适配，提案未改对方源码。

待协调核包，S00再交其新适配并另排一次有限观测；本轮不直接补跑2041919。完整同步训练/性能/收敛未接受，正式batch/LR/schedule继续待定。
