# S04 R2 最新变化

任务/轮次：S04 R2_LOCAL_ATTRIBUTION_20261105。
状态变化：R1准备 → 新fp32对照/局部归因完成，NUMERICAL_FAIL保持。
本轮改动：R2独立目录新增关闭量化的同一重写结构及观测；R1源/原夹具/AdamW/门槛/旧包保留，未修bf16路径。
验证增量：10项检查通过；新fp32 76/83通过（7参数/增量FAIL）；bf16逐项复现28FAIL；63个gate变化及QKV梯度量化归约有直接证据，256项AdamW重放逐位一致。
证据：REPORT.md、evidence/{fp32_control,local_vjp,key_bias_rounding,adamw_replay}.json；SOURCE_MANIFEST.json与package/PACKAGE_MANIFEST.json。
阻塞与下一步：gate反事实仅将28FAIL降至14FAIL，不是修复；严格fp32整步/原bf16仍未接受，待协调评审有限边界；0job/无性能或200步。
