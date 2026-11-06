# 工程训练观察（非科学/性能验收）

证据类型：LOCAL_FIXTURE。

状态：EVIDENCE_GAPS；原始运行状态：INCOMPLETE；退出码：124。
无正式 val/test；缺失值均为未知。RSS/HWM 为 process-lifetime，不代表逐步独占内存。

记录步数 1；声明更新数 1；实际记录帧 1。
步耗时秒（min/median/max）：{'observed': 1, 'missing_or_invalid': 0, 'min': 1.0, 'median': 1.0, 'max': 1.0}。
RSS bytes：{'observed': 2, 'missing_or_invalid': 0, 'min': 100, 'median': 125.0, 'max': 150}；HWM bytes：{'observed': 2, 'missing_or_invalid': 0, 'min': 200, 'median': 225.0, 'max': 250}。

| step | batch | voltage | coarse | total | step s | loader s | diagnostic s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1.0 | 2.0 | 3.0 | 1.0 | 0.1 | 0.2 |

实际记录的样本覆盖（case 不代表不同 subject）：

| case | unit | logged frames |
| --- | --- | --- |
| caseA | unitA | 1 |

整体计时（秒；不推算加速百分比）：

- wall_seconds: 10
- data_loading_seconds: 1
- batch_materialization_seconds: 0.2
- training_step_seconds: 3
- diagnostic_seconds: 0.4
- checkpoint_and_recovery_seconds: 2
- unattributed_seconds: 3.4

CPU36 报错：[]；检查点数：1。
KML：kml；Torch threads：36；调用数：40。
checkpoint 声明：{'path': '/remote/final.pt', 'bytes': 123, 'sha256': 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}；恢复声明：{'status': 'PASS_NO_EXTRA_UPDATE', 'extra_updates': 0}。
暴露使用状态计数：{'CONSUMED_CONFIRMED': 1}。
以上为运行证据转述；不加载权重，不独立复核线程实现。完整帧顺序、来源、库路径/SHA和暴露清单见同名 JSON。

缺项/失败（均保留）：

- exit_code is 124, expected explicit 0
- runner_status.json present: retain timeout/runner evidence; no completion inference
- run status: INCOMPLETE
- planned updates not completed or unknown
- interrupted in-flight update: possible exposure requires conservative exclusion review
