# S04简短状态（R2）

- 更新/轮次：2026-11-05（Asia/Shanghai）；R2_LOCAL_ATTRIBUTION_20261105。
- 当前状态：本地归因完成 / NUMERICAL_FAIL / NOT_ACCEPTED；不是重复R1准备总结。
- 本轮目录：round2_local_attribution_20261105/；报告为该目录REPORT.md。
- R1保留：候选/原夹具/权重/AdamW/门槛/失败/旧包等30项SHA保持；根两短状态R1版本保存在R2/evidence/R1_*.md。
- 新增对照：同一候选重写结构关闭量化，83项76PASS/7FAIL；输出/全部梯度及moments过，严格参数/增量7项FAIL。
- fp32已观测首处分歧：linear1 fused addmm与mm后add偏置的舍入，max_abs2.3842e-7、ReLU gate变化0；不豁免整步失败。
- bf16复现：原83项指标逐项一致，仍55PASS/28FAIL，未放宽阈值或改变随机样本。
- FFN归因：63个ReLU gate变化足以产生linear1/norm2四个大范数梯度FAIL；诊断反传恢复gate后28FAIL→14FAIL，不是真实候选修复。
- 更新归因：256项AdamW重放逐位一致；QKV梯度bf16 cast使key-bias归约范数5.69e-9→3.71e-5，放大packed bias更新差。
- 验证：10项合同/attention/诊断模式检查通过；新增fp32/局部VJP/符号与归约/AdamW证据详R2/evidence/。
- 改动与身份：R2仅诊断开关/观测，无bf16修复；最小diff84行；R2/SOURCE_MANIFEST.json、ARTIFACT_SHA256.txt和package/PACKAGE_MANIFEST.json。
- 后端：已有Windows Torch2.7.1+cpu独立环境只读使用，2线程；量化FP32模拟，非实际KML。
- 未运行：KML/CPU36/集群/性能/峰值/完整模型/200步/S05；新增job=0、节点小时0，本轮本地进程已结束。
- 阻塞与下一步：严格fp32整步及bf16门槛仍FAIL；交协调评审敏感精度边界和有限新候选范围，不自动搜索/改门槛/上集群。
