# S04 R2 本轮状态

- 轮次：R2_LOCAL_ATTRIBUTION_20261105；本地归因完成，NUMERICAL_FAIL / NOT_ACCEPTED。
- 来源：R1旧包28成员及原件已核；夹具/16参数payload与R1完全一致；B2/M17/D512、loss/AdamW/2线程/原门槛保持。
- 新对照：同一候选重写结构关闭量化，83项76PASS/7FAIL；输出及全部梯度PASS，严格参数/增量仍FAIL。
- R1复现：bf16 83项指标逐项完全相同，仍55PASS/28FAIL。
- 归因：63个ReLU gate变化足以造成linear1/norm2四项大范数梯度FAIL；恢复gate的诊断反事实28FAIL→14FAIL，不是修复。
- 更新定位：256项AdamW重放逐位一致；QKV梯度bf16量化使key-bias归约范数5.69e-9→3.71e-5，放大packed bias更新差。
- fp32首处分歧：linear1 fused addmm与mm后add的舍入，max_abs2.3842e-7，无gate变化；整步7项FAIL不豁免。
- 改动：仅R2诊断模式/检查/观测；R1文件30项SHA保持，根两短状态旧版本另存；bf16候选未修、未集成。
- 验证：10项合同/attention/模式检查PASS；新增fp32、原bf16复现、局部VJP、gate反事实、归约及AdamW证据详REPORT.md/evidence/。
- 包/来源：SOURCE_MANIFEST.json、ARTIFACT_SHA256.txt、package/PACKAGE_MANIFEST.json；最小diff84行。
- 未运行：KML/CPU36/集群/性能/峰值/完整模型/200步/S05。新增job=0，节点小时0，本轮本地进程结束。
- 下一步：协调评审敏感精度边界与有限新候选范围；严格fp32整步和bf16门槛仍未通过，不改阈值追PASS。
