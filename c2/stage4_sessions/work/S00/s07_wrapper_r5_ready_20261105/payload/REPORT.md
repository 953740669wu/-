# S07 R4：准备阶段就绪门禁，本地候选

日期：2026-11-05。状态：READY_FOR_REVIEW / LOCAL_ONLY / NEW_COMMUNICATION_NOT_RUN。

## 原因证据

先重新读取2041165双方/父原事件并核COLLECTION_S00的SHA/bytes。以同节点supervisor_begin为0，rank1在9.401416219秒进入初始化、15.924754694秒报Wait timeout；rank0到16.383993928秒才Torch导入结束、16.420449274秒开始libtorch_cpu SHA，父16.569892145秒向其组发送TERM，16.676002744秒结束。该次准备错开已侵入rank1初始化等待窗口，有事件支持。详见 `TIMELINE.md` / `evidence/timeline_recheck.json`。

这不证明导入差异的底层原因，不证明rank0 SHA永久卡住，也不把旧2040233判为必然同因；没有排除双方准备完成后其它通信问题。2041165原28项Linux检查通过、normal失败和后三case未运行保持，未改成通信通过。

## 最小修订

仅新建 `c2/stage4_sessions/work/S07/round4_readiness_20261105/` 并更新本任务根短状态；R1/R2/R3、2040233/2041165旧失败及S00代码保持。完整2041165旧失败ZIP原字节保留于本轮evidence；本轮前状态在evidence/before，来源逐项SHA/mtime及结束复核分别为reference_sources.json/source_recheck.json。

父在原supervise计时起点派生绝对deadline，原子发布真实子PID参与者清单；每rank在导入/元数据/实际Torch36与导入后TID检查成功后，才发布绑定run/job/rank/PID及本次随机token的ready。只有两份均合法才调用初始化。新增token区分同job下重复的normal目录标签，PID来自父Popen而非peer自报。缺失就绪在原剩余预算内等待，错误或写入失败直接停止。

`minimal.diff` 对照实际执行的R3，仅涉及comm_probe门禁，以及原诊断检查针对“初始化超时”测试的就绪替身/内部deadline夹具适配。新增 `tests/test_readiness.py` 单独交付。CPU36合同、CCS_JOB_ID检查、原test_probe/身份检查、run_checks四case故障接受条件、Gloo/lo/store/张量值保持；没有修改S00执行层。

原30秒起点和监督循环不变，覆盖spawn、准备、等待及通信，不在ready后重启；进程组及collective仍用原5秒，原有界TERM/KILL/wait不变。ready写入采用强制失败语义，与可容错的阶段事件日志分开；不因TRACE_WRITE_ERROR跳过清理，也不因其日志容错跳过ready条件。

## 实际检查

先写14方法门禁检查并红灯（1失败/25错误，含子场景），再实现并补齐严格PID类型及2个过期/父发布失败方法，最终为16方法。原始输出为 `evidence/tests_before_implementation.txt` 及strict_pid_test_before_fix.txt，不改写成原Gloo故障复现。

| 检查 | 本轮结果与边界 |
|---|---|
| readiness新16方法 | 全通过；受控6.25秒准备错开仍在30秒原预算内，初始化不早于双方合法ready且调用参数5秒 |
| 错误/缺失/过期ready | run/job/token、rank/PID/类型、参与者期限或PID、半JSON、缺peer/父清单、过期、旧自有文件均拒绝或原预算超时；失败CPU36/TID不发布ready |
| 准入写入错误 | fsync错误不发布最终ready、parent参与者写错即原失败清理；不适用诊断日志容错 |
| 真实标准库子进程 | 验证parent PID绑定、原deadline从spawn前起算，missing-ready/peer失败/启动失败时有界回收；不初始化Gloo |
| 原28方法回归 | 6诊断+6身份+16原probe，27通过、1 Linux组清理跳过 |
| 合计与部署复核 | 44方法：43通过、1跳过；独立ZIP解压应同结果，见deployment_checks.json |
| Python3.9 AST | 7文件仅语法检查通过；实际本地解释器Windows Python3.11，不能称Linux/Python3.9运行通过 |
| 新Linux/真实Gloo、完整训练/性能 | 本轮全部未运行，未SSH/申请资源/提交job；旧28项Linux是2041165历史结果 |

命令与退出保存在 `evidence/local_checks.json`，各原始测试日志在同目录。方法数不叠加计算子场景，不把假框架初始化边界视为真实Gloo通过。

## 交付与后续

新内包 `package/S07_READY_SYNC_R4.zip`；部署SOURCE_MANIFEST与外部SHA256SUMS索引包/源码/diff，EVIDENCE_MANIFEST索引全部本轮证据。13实际文件+1空目录=14成员；12项delivery，不自哈希；独立解压复核逐字节SHA。旧R3的payload/包保持。

`INTERFACE_FOR_S00.md` 列明新prepare的成员/文件数量、新44项检查、原统一270秒consumer/300秒job以及新ready证据的收集提案。待协调核具体包和S00新适配后才另排一次有限小试。本轮本地子进程均已回收，不实时查询集群其它任务。正式batch/LR/schedule待定，当前不宣称通信、同步训练或性能通过。
