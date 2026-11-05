# S01 R6：36核诊断准备复核

日期：2026-11-04。复核入口：`work/S01/revisions/R6_CPU36_DIAG_20261104T143214257047Z/REPORT.md` 与 `DIAGNOSTIC_PLAN_FOR_S00.md`，work/相对c2/stage4_sessions。

## 接受决定

**ACCEPTED_FOR_BOUNDED_DIAGNOSTIC / C2_DIAGNOSTIC_NOT_RUN / MODEL_RESTART_NOT_ACCEPTED**。

接受 S01_CPU36_THREAD_DIAG_V1 作为下一项有限诊断包，不接受其已解决C2线程问题，也不将合同原型视为新的正式模型运行器。

## 独立检查

- 复跑11项CPU36正负检查，全部通过。覆盖域内选择36核/保留末2核、授权不足/跨域/SMT重复拒绝、单核TID掩码合法、越界与缺证据拒绝、torch线程数1不能按36核通过。
- 21项交付索引、6项冻结源清单、ZIP内12个文件全部核对一致；包内shell/env原始字节无CR。
- 诊断ZIP SHA256：`1db8b1818a387a0c3dd404bf1efd40a3aba777bad7d7c4226379ef369ad9fd81`。
- R6报告 SHA256：`202ddee714b14af4c6dc12c24c04b1ce9142a765a81016836f6c8ffb270c58e3`。
- 静态审查了诊断driver、worker和CPU合同：仅计算job允许运行；基于实际授权/NUMA/物理拓扑选择36核，观察器和worker都收窄到这36核；五组worker串行、各45秒有界，失败/越界停止；不运行完整模型、NPZ、AdamW、HBM或吞吐搜索。

本聊天未连接集群、提交作业或执行诊断算子。Linux/C2实际运行、库调用兼容性与结果仍待验证，Windows本地通过不能替代。

## 诊断范围

在一个新计算节点作业内，单38核NUMA域分配、实际选36核并预留末2核，内存上限仍24576MB；建议job最长300秒，外层270秒TERM/5秒KILL，不超过前次小试范围。运行前由S00核对实际分配、依赖与远端SHA/LF/bash -n；不占用既有作业，不自动重试。

五组固定对照：A的MKL=1为标明的单线程负控；B移除MKL；C设MKL=36；D相对C关闭OMP绑定；E相对C把OpenBLAS设36。其余变量固定，新进程隔离，每个worker的CPU边界仍是同一36核。单线程负控用于定位问题，不是恢复正式单线程模型测试。

DIAGNOSTIC_DATA_COMPLETE只表示收齐五组数据，不能直接解释为正式36核模型/性能通过。需要S01根据实际torch线程、各TID边界、阶段活动、OMP/BLAS/KML实际库与API综合判断；不得仅凭主线程掩码、总TID数量、CPU集合并集或omp_max做结论。

当前MKL_NUM_THREADS=1及旧调用线程掩码检查是待验证方向。先收C2单变量证据，再选择最小环境/验收修复；保留越权用核与实际线程数错误的拒绝检查。

## 下一步分工

- S00：执行本有限诊断，回传实际job分配/终态、完整日志、results、CPU receipt、五组command/worker/samples/assessment、SUMMARY与COLLECTION。COLLECTION保留原始mtime_ns/bytes/SHA，失败case也原样保留。
- S01：收到数据后解释A/B/C线程差异、D绑定差异与E的OpenBLAS影响，提交最小环境和合同修订；当前先等待实际结果。
- 总协调：复核诊断结论后再决定新的36核完整模型恢复包。
- S02：继续数值差异诊断；C2等价与训练内存测试仍未解锁。S03仍限安全与观测准备。

## 可发给 S00

```text
总协调已复核接受 S01 R6 的36核有限诊断准备。
请读取 work/S01/revisions/R6_CPU36_DIAG_20261104T143214257047Z/DIAGNOSTIC_PLAN_FOR_S00.md
及 work/COORDINATION/CPU36_DIAGNOSTIC_REVIEW.md（work/相对c2/stage4_sessions）。
按计划仅执行一次小型线程诊断：单域分配、实际36核、24GiB，建议最多300秒。
提交前核对实际执行文件SHA、LF与Linux bash -n；使用新目录/新job。
五组对照串行，失败或CPU越界即停止，不重跑完整模型、不提交S02、不测训练内存。
回传完整诊断数据给S01和总协调；不要把数据收齐标记当作36核模型验收通过。
```
