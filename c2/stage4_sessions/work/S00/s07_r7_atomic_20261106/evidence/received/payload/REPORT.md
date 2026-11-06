# S07 R7 原子rank报告发布

本轮仅修复rank报告覆盖发布可能损坏上一份完整checkpoint的问题。R6及2050433原件保留；该job整组FAIL、后两case/取栈NOT_RUN不变。时间线与机制/证据缺口见本轮外部TIMELINE.md；不宣称已证实现场精确syscall或修好watchdog初始化。

先写17项定向检查，保留evidence/atomic_red.log，再增加write_rank_report及替换worker的checkpoint/成功/异常三处调用。minimal.diff仅含comm_probe.py这一个运行源的变化；新增tests/test_atomic_reports.py单独交付。通用write_json、ready的publish_json、run_checks、cpu36_contract、stack_observer及旧五份测试均保持R6原字节。

新函数完整序列化（indent=2、allow_nan=False、同原换行/字段/值），在目标目录用NamedTemporaryFile独占创建`.rank{rank}.json.<random>.tmp`，写完、flush、fsync、关闭后os.replace正式文件。正常及可处理异常只清理本次生成的确切临时路径；不glob删除别人的残件。OS终止前未replace时保留旧报告/可能留下临时残件；无旧目标时仍缺失。目标是最后已提交checkpoint，不能声称worker_error的最终报告一定已完成。只保证进程中断的原子发布，不承诺断电或任意远端文件系统的持久性。

本地新增17方法全过：首次/替换及原序列化一致、NaN/不可序列化、write/flush/fsync/replace错误、同目录独占文件与提交顺序、只清理自身文件、旧写空/半份复现、新写零/半份/replace前中断、无旧目标拒绝、双rank缺/空/残拒绝、ready拒绝覆盖。原71方法回归为70过/1原Linux进程组清理跳过；总88方法87过1跳过，10份Python文件LF且Python3.9 AST语法检查通过。Windows/Python3.11本地结果不能替代Linux/Python3.9、C2/Gloo/网络文件系统及真实清理验证。

原pg5、case30监督起点、ready、注入点、四case/双rank reader、TERM/KILL和有界回收、R6一次取栈/proc观察均不变。正式batch/LR/schedule仍待定；本轮无模型、数据、训练、性能或集群job。独立ZIP检查结果与输入复核原件在本轮外部evidence目录及ATOMIC_READY中绑定。

固定交接先INTERFACE_READY.json，后ATOMIC_READY.json；后者发布后代码/内包冻结。S00按INTERFACE_FOR_S00.md准备新R7部署，S01绑定具体内外包SHA审核PASS后，S00按任务卡执行唯一一次四case；失败停止，不补旧case、不重试或扩预算。S07不承担提交或替代审核。
