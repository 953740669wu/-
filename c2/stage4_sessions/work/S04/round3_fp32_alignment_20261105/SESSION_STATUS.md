# S04 R3 状态

- 轮次/更新：R3_FP32_ALIGNMENT_20261105，2026-11-05（Asia/Shanghai）。
- 状态：PASS_LOCAL_FP32_CONTROL_ONLY；BF16_NUMERICAL_FAIL / NOT_INTEGRATED。
- 有限尝试：仅一次无量化fp32路径对齐；原fixture/初权重/loss/AdamW/2线程/83项门槛不变。
- 实际结果：83/83 PASS且全部逐位一致，原7FAIL全部消失，新增FAIL=0。
- 定向检查：2项红灯后转PASS；禁止整个参考block/MHA调用，native epilogue/autograd及packed布局已核。
- 旧bf16：原83项指标与R1/R2逐项相同，仍55PASS/28FAIL；不是bf16接受。
- 改动：只在torch_fp32_control对齐native linear/autograd、QKV/SDPA布局；48行最小diff；R1/R2既有71文件SHA保持。
- 提案：唯一P1见PRECISION_BOUNDARY_PROPOSAL.md，未实现；注意入口量化、更新敏感及更多fp32数据成本。
- 证据：REPORT.md、evidence/{fp32_aligned,failure_transitions,bf16_unchanged,summary}.json。
- 身份：SOURCE_MANIFEST.json、ARTIFACT_SHA256.txt、package/PACKAGE_MANIFEST.json；终检evidence/delivery_verification.json。
- 环境：已有Windows Torch2.7.1+cpu只读，2线程；无KML/CPU36/性能/峰值/完整模型/200步/S05。
- 作业/进程：集群job=0、节点小时0；本轮本地检查结束。
- 下一步：协调仅评审本地fp32控制和单一P1；本轮停止改动，不扩搜或自动执行后续精度候选。
