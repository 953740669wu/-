# S07 R1 通信预备轮

日期：2026-11-05。状态：READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN。

## 1. 结论

已交付最小固定2-rank CPU/Gloo通信探针和正确性/失败检查。只涉及4元素张量，不接入EIT模型、真实数据、训练或优化器。默认本地Python无torch，故本轮**未运行真实通信**；不能宣称通信、同步训练或性能通过。

## 2. 来源与边界

先读HANDOFF_PROTOCOL、总任务表、S07任务卡和模板，并按需读取CPU36政策、R7接受说明/合同、S00环境原始证据及原计划G。来源逐文件SHA/bytes/mtime见 `evidence/reference_sources.json`；结束前重新核对见 `evidence/source_recheck.json`。`candidate/cpu36_contract.py` 是接受来源的逐字节副本，不改原实现；其余探针/检查均本轮新建，未改共享模型或原数据。

所有写入仅 `c2/stage4_sessions/work/S07/`。未操作Git分支/暂存区，未SSH、未调用调度器、未申请资源，无集群job或遗留本轮子进程。初始工作区已有其它任务修改，不归入本轮；最终交付文件SHA见 `SOURCE_MANIFEST.json`（自身不作递归哈希）。

## 3. 环境与资源

- 本机Windows / Python3.11.9：实际torch导入失败，environment命令exit3。见 `evidence/local_environment.json`。
- 原始job2026200记录：torch2.7.1+cpu构建USE_GLOO=ON、MPI/NCCL=OFF。见 `evidence/historical_backend.json`。历史构建支持Gloo；当前API可用性/实际双进程通信未核验。
- S00历史R7使用R4 venv Python3.9.9及torch2.7.1+cpu；这次没有实时探测远端，不将旧job环境当成本轮实测。
- 两个不同授权38物理核域，每rank只用本域前36核、预留末2核；A0/A1不得重叠。实际授权逐CPU列表待新job原始分配，留空模板拒绝运行。方案/逐rank边界/总内存24GiB/≤300秒/停止条件及S00命令见 `INTERFACE_FOR_S00.md`。
- 已有单域授权不自动覆盖两域；没有新增作业/节点小时。正式全局batch、学习率和训练计划保持待定。

## 4. 检查与证据

先写检查并运行，缺少实现时按预期导入失败，见 `evidence/tests_before_implementation.txt`；再实现并运行最终检查，见 `evidence/tests.txt` 和 `evidence/local_checks.json`。

| 本轮检查 | 实际结果/边界 |
|---|---|
| 标准库unittest | 16项：15通过、1跳过；包含真实本地子进程成功、exit17中止peer、截止时间清理和启动失败清理 |
| 合成报告/资源拒绝检查 | 已运行；坏值/NaN/重复rank/旧run_id/PID/shape/dtype/不完整结果、错CPU/越界TID/重叠域拒绝；模拟sysfs不等于现场拓扑验收 |
| 失败用例接受条件 | 已运行标准库检查；不能把前置失败冒充注入成功，collective-timeout要求broadcast实际超时证据，watchdog要求两个rank到注入点 |
| Python3.9 AST语法检查 | 已运行；仅静态语法，不是Python3.9运行或数值验证 |
| Windows实际运行入口前置拒绝 | 已运行；exit1、FAIL、无supervisor/worker；不把资源前置错误写成数值FAIL |
| Linux进程组/孙进程清理 | 跳过；本机Windows，不作已通过声明 |
| Gloo固定张量广播/求和/身份 | 未运行；预定fp32/[4]/元素绝对差0，两rank各自及父进程核验 |
| 真实Gloo通信超时/故障退出/watchdog双rank检查 | 未运行；已交付case和严格复核入口，标准库supervisor检查不能代替 |
| 完整EIT/训练更新等价/收敛/性能 | 未运行；不在本轮范围 |

## 5. 运行设计与限制

父进程不导入torch，按原授权清单/现场sysfs验证两域，缩到selected36并集，再启动两个独立worker。worker导入torch前绑自己的selected36，核对真实torch intraop=36并保存阶段TID快照。Gloo通过同节点lo通信；新文件store只做rendezvous。报告固定tensor、rank/world/backend/PID/run_id，成功要求两个正常退出和完整新结果。

通信timeout默认5秒；父截止30秒及有界清理覆盖worker初始化、collective或销毁阻塞。任何worker非零立即清理peer。Linux只信号本任务新建进程组，Windows检查只验证直接子进程回收。快照不是持续全线程监测、物理核心利用率证明或性能数据。

同步训练、梯度同步与loss分母、optimizer、恢复、batch、学习率、训练计划、真实内存/吞吐均没有结论。不建议集成正式训练；本候选仅供总协调复核和S00获授权后做通信探针。无真实通过前不扩大规模。

## 6. 证据与下一步

详细S00接口与官方PyTorch2.7引用：`INTERFACE_FOR_S00.md`。来源快照/环境提取/本地原始日志在 `evidence/`；候选和测试路径及SHA在 `SOURCE_MANIFEST.json`；当前快照与六行变化为 `SESSION_STATUS.md` / `ROUND_DELTA.md`。

下一步：总协调复核候选；S00只在另有明确合法两域安排时按接口运行四项固定通信检查，回传完整原始证据。没有该资源前提则保持CLUSTER_NOT_RUN，不申请集群资源。
