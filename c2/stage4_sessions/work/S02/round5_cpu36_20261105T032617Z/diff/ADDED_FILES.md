# R3 到 R5 的包装改动边界

`R3_WRAPPER_ONLY.patch` 只包含三个既有执行文件的修改：diagnose_update.py、diagnostic_common.py、run_c2_diagnostic.sh。

新增执行文件为 cpu36_guard.py 和 run_s00_job.sh；新增本地策略测试为 tests/test_cpu36_guard.py。cpu36_contract.py 和 interfaces/cluster_runtime.env 是 S01 R7 冻结接口的逐字节副本，来源及 SHA/大小见 package/PACKAGE_MANIFEST.json。

新包不再包含 R3 的 tests/test_affinity_contract.py（旧四核合同）或 tests/test_diagnostic_controls.py（历史四核数学控制）；原文件仍完整保留在 R3，本轮没有再执行它们。九项完整 Windows 因果实验及全部历史证据未改动。

SOURCE_SHA256.json、C2_HANDOFF.md 已按新包装生成。模型、loss/AdamW 计算、loader、原严格比较器/阈值、投影诊断、固定 case 清单均保持 R3 原字节；没有候选训练计算变更。
