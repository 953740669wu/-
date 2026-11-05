# S06 R3：修复隔离负例对父启动参数的依赖

2026-11-05；READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN。

本轮只有一处测试逻辑修改：test_isolation_requires_I_and_S从直接调用probe.isolate，改为在明确不带-I/-S的独立子进程执行，并核对非零退出及原RuntimeError完整拒绝原因。隔离正例、全部候选实现、线程/清理策略、模型和数值阈值不变。只写S06，未安装环境、连接集群或提交作业。

## 来源、复现与验证

先读自己的状态/增量、AFTER_MEMORY_PROBE_R2_NEXT的S06节、MEMORY_AND_PROBE_R2_REVIEW的S06节及原失败日志，再核对R2测试、probe和清单。R2完整65项索引及原ZIP先核验，通过后从原ZIP解出独立新目录；原包SHA仍为62b28092892ac7ed87f1bc8b8c7d773678b9a38ea78d42f621ddc2e72e174975。相关最新源码SHA/bytes/mtime见SOURCE_IDENTITY.json。

改前在新副本按文档运行-I/-S完整26项，复现22通过/3跳过/1失败，exit1；原因为负例的RuntimeError not raised，见evidence/tests_before_isolated.txt。协调原失败日志另外原样保留在evidence/S06_R2_REVIEW_TESTS.txt，未覆盖原文件。

修复后均在本机Windows/Python3.11执行全部26项：

| 父解释器启动 | 通过 | Linux跳过 | 失败 | 退出码 | 原始日志 |
|---|---:|---:|---:|---:|---|
| python -B（普通） | 23 | 3 | 0 | 0 | evidence/tests_after_ordinary.txt |
| python -I -S -B | 23 | 3 | 0 | 0 | evidence/tests_after_isolated.txt |

evidence/test_results.json记录两条实际命令、cwd及结果；修改的测试文件通过Python3.9语法解析，该项不是Python3.9实际执行。未新增测试项、删除断言或放宽拒绝条件。候选未改，不重复Bash或模型检查。

3项跳过仍为真实Linux子进程信号掩码、TERM清后代、SIGINT清后代；不能用Windows或模拟分支宣称Linux组清理通过。实际Torch36/TID、C2权限/compile、卷积数值与性能继续未运行。

## 最小差异与交付

- MINIMAL.diff只含tests/test_probe.py一个方法；新增payload/README_R3.md说明本修订包及两种检查命令。
- payload/ARTIFACT_SHA256.txt和S06_R3_PAYLOAD.zip为新的可搬移包；不依赖固定祖先路径。所有包内路径相对payload，源码身份仍使用R2原记录。
- evidence/final_verification.json核对除该测试文件外11项R2 payload文件（含candidate四文件）字节不变、R2原65项索引/ZIP未改、新ZIP/清单一致。
- ARTIFACT_SHA256.txt为本轮清单；当前短状态更新前的副本保存在evidence/before_SESSION_STATUS.md及before_ROUND_DELTA.md。

下一步交协调复核本R3修订包及SHA；本轮无集群操作或活动子进程，未新增执行授权。R2旧包/旧失败证据与此前边界全部保留。
