# S07 R3：2040233初始化失败分析与最小诊断候选

2026-11-05，Asia/Shanghai。状态：READY_FOR_REVIEW_DIAGNOSTICS_ONLY / ROOT_CAUSE_UNDETERMINED；本轮没有集群job或真实通信。

## 结论

rank1在normal的ProcessGroupGloo构造报 `RuntimeError: Wait timeout`，配置pg_timeout=5秒。rank0最后有效记录是before_framework，源码该检查点后还有Torch导入、逐库SHA及其它元数据/检查操作；缺阶段时钟，无法定位其停点或判断是否永久阻塞。现有记录不能确认启动准备不同步、导入/哈希耗时、rendezvous/loopback或其它故障中的哪一项是根因。

normal监督器实测15.916535秒、reason=child_failed，退出[-15,1]并回收两个worker；没有触发30秒deadline。结合原内层清理分支和外层无信号动作，rank0的-15与内层TERM清理一致，不是第二个独立通信故障。旧包没有逐signal时间回执，所以不虚构其发送时点。详细事实/推断边界与中国时间表见 `TIMELINE.md` / `evidence/timeline.json`。

## 来源与旧失败保留

仅写 `c2/stage4_sessions/work/S07/`；新目录为 `round3_init_diagnostics_20261105/`。已读指定交接S07节、短状态、必要S00报告/审核/执行接口，以及本次实际执行的候选/必要rank文件与原始mtime。33项改前来源SHA/mtime见 `evidence/reference_sources.json`，结束复核见 `evidence/source_recheck.json`。

完整原失败ZIP249710bytes/SHA=`82a82866ad2572113d6b85f13995009d8948c8d3bca66b23e3b3d413546dbc7d`复制保留在本轮evidence；必要原件在 `evidence/received/`，均对照COLLECTION_S00核SHA/bytes。原R2候选、S00执行层、远端失败、原证据不改。根短状态覆盖前保存于 `evidence/before/`，R2不可变清单保持。

实际失败候选comm_probe SHA=`13fdc08a872871ae61173f0761e81a961a9ecfa425ee79ff5d3e15d13a6cb5e8`，与本地R2原件相同；manifest也记录该SHA。新候选SOURCE_MANIFEST/ZIP与SHA256SUMS，以及完整本轮EVIDENCE_MANIFEST分别索引部署文件和本地证据。

## 最小诊断修订

缺口已定位为backend_info复合步骤/初始化/监督清理没有细分时间；先写针对性检查，旧代码6项诊断方法未通过（1失败/5错误），原输出在 `evidence/tests_before_implementation.txt`。随后仅补带wall/monotonic时钟的独立JSONL事件、flush/fsync和失败不妨碍清理的日志写入；不声称修好了原初始化故障。

`minimal.diff` 包含comm_probe观测调用，以及原身份检查框架替身的参数断言适配。新增 `tests/test_diagnostics.py` 单独交付。CPU36副本、run_checks四case判据、原test_probe、allocation模板逐字节不变；本轮未改S00或其它目录。保留原pg_timeout=5、deadline=30、故障即停、TERM/KILL/wait，不加barrier或扩大预算。

## 实际检查及未测项

| 检查 | 结果与边界 |
|---|---|
| 新诊断6项 | 全过：时间/刷盘、导入有begin无end、导入后SHA有begin无end、假框架Wait timeout仍保留原FAIL、真实标准库子进程spawn/清理/reap事件，以及fsync失败不跳过清理 |
| 身份6项 | 全过，仍在框架前拒绝旧/缺失CCS_JOB_ID，匹配路径用框架入口替身 |
| 原16项 | 15过、1项Linux组清理跳过；保留原数值/故障接受条件检查和本地子进程退出/截止时间回收 |
| 合计 | 本轮Windows/Python3.11标准库/假框架共28项方法，27过1跳过；不将子场景另计 |
| Python3.9 AST | 6个Python文件语法通过，只是静态检查 |
| 旧2040233 Linux22项 | 历史job的原6+16全通过，与本轮27/1区分；不能据此接受新Linux诊断或通信 |
| 新Linux/Gloo、真实导入/刷盘成本、原失败根因 | 本轮未运行/未确定；没有模型、训练、性能、收敛结论 |

命令/退出与原日志见 `evidence/local_checks.json`、diagnostic_tests.txt、job_identity_tests.txt、regression_tests.txt。合成失败只复现可观测性缺口，不是原故障数值或运行复现。

## 下一步

先由总协调核此时间线与诊断包。若批准复测，S00需在新包装版本固定新ZIP，原prepare硬编码旧包身份不能直接复用；明确提案与精确原四case命令见 `INTERFACE_FOR_S00.md`。本轮不修改S00、不提交job。总job仍300秒、consumer仍270秒；新增刷盘/检查开销未现场测量，不增加超时或静默挪用资源。

本轮本地测试子进程均已回收；未实时查询集群，2040233终态描述来自原调度证据，不声称整个集群当前无作业。正式全局batch/LR/schedule继续待定。交付状态为诊断准备可复核，绝非通信/同步训练/性能通过。
