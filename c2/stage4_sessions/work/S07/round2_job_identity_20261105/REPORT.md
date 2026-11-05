# S07 R2：当前作业身份检查

日期：2026-11-05。状态：READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN。

本轮只修复R1允许旧allocation作业号被当作当前job的问题。父入口在启动worker前，将allocation.job_id与现场CCS_JOB_ID精确比对；worker在CPU绑定和Torch导入前，再比对manifest的顶层与allocation内作业号。缺现场值、缺配置值或不匹配均拒绝。

## 范围与来源

全部写入仅 `c2/stage4_sessions/work/S07/`。新候选位于 `round2_job_identity_20261105/candidate/`；原R1代码/接口/报告/清单/证据不改。R1清单包含的可变状态和增量已在更新前一并留存于本轮 `evidence/R1_snapshot/`，该目录可按原清单复核17/17文件；旧根清单对当时状态的引用应到该完整快照核验。

参考S07短状态/增量、AFTER_S06_S07_NEXT的S07章节、总表、本次协调审核S07节及最新代码/原接口。改前逐文件SHA/mtime记录于 `evidence/reference_sources.json`；结束前复核11项引用SHA未变，见 `evidence/source_recheck.json`（在覆盖可变状态前核验）。

原comm_probe SHA256：`ba11ab467af7d876ba041068fcd2d79f1545e7f1aea4b4c6cacacb1a96f7866f`。原R1清单SHA256：`1b6fc9f6fa27e1805e2b9ff65f6ea1e3584f913db3e6c20082d5b59b3299ed5e`。修订源码及所有交付SHA见本轮 `SOURCE_MANIFEST.json`。

## 最小变更

`minimal.diff` 仅包含comm_probe的共享身份检查/父子入口调用，以及原回归夹具补充匹配的模拟CCS_JOB_ID。新增检查单独放 `tests/test_job_identity.py`。冻结CPU36合同、run_checks、allocation模板均与R1逐字节一致；张量值、rank数、逐rank授权/调度原件检查、数值容差、故障判据、超时与清理代码未改。

## 实际验证

先写新增检查，未实现时运行失败（6方法，4失败/20错误包含子场景，见 `evidence/tests_before_implementation.txt`），再实现并复跑：

| 检查 | 本轮实际结果 |
|---|---|
| 新身份检查 | 6项通过；覆盖匹配、现场缺失/空白、配置缺失/旧号、父入口拒绝前不访问CPU/不启动worker，以及两rank各自manifest/allocation缺失或旧号在框架前拒绝 |
| 匹配正控 | 原合成sysfs资源路径通过；两个worker匹配身份后均到达框架入口替身。替身主动退出用于证明身份门禁放行，不是Torch/通信通过 |
| 原回归 | 16项：15通过、1 Linux进程组检查跳过；含原真实本地子进程退出和有界回收检查 |
| Python3.9 AST | 5个修订/随包Python文件语法通过，仅静态检查；当前实际解释器仍为Windows Python3.11.9 |
| R1保留/来源 | 17项归档文件符合原清单；11项引用SHA复核未变，CPU36/run_checks/template副本原字节保留 |
| 当前集群CCS_JOB_ID、Linux进程组、Gloo两rank | 未现场运行；本轮只做标准库/模拟检查，不导入Torch、不SSH、不申请资源 |

原始输出为 `evidence/job_identity_tests.txt` / `evidence/regression_tests.txt`；命令、退出状态及边界为 `evidence/local_checks.json`。共22项方法：21通过、1跳过；不将子场景重复计数。

## 修订接口与后续

S00使用本轮 `INTERFACE_FOR_S00.md` 与候选；CLI不变，现场CCS_JOB_ID须由调度器提供并由worker继承，不得根据配置伪造。现场字段缺失就停止。逐rank授权仍需S00对照调度原件人工核验，不把CPU可见性或job号匹配等同资源授权。

修订待总协调核验；未申请/运行76核两域小试，没有本轮集群job。本地标准库检查的子进程均由监督器回收；真实通信/同步训练/性能未运行，正式batch/LR/schedule仍待定。
