# S04 R2 本地归因协议（运行前）

仅在本目录工作，另更新S04根短状态；R1候选/协议/失败/包不改。根短状态原件已另存。
复用R1原字节baseline、tests/common.py的fixture；原权重/输入payload SHA必须逐项匹配R1 block_numeric.json。
B2/M17/D512、heads、原loss、fresh AdamW超参/一步语义、2线程、R1全部工程门槛不变。

1. 先写诊断模式检查，记录候选尚不支持该模式的红灯。新增torch_fp32_control只关闭各bf16量化，仍调用同一BF16EncoderBlock.forward、同一custom linear forward/backward、同一QKV/SDPA/残差/FFN编排。禁止用原模块deepcopy代替这个对照。
2. 原fp32控制协议沿用S02 VALIDATION_PLAN：逐tensor max_abs<=2e-5（moments<=2e-6），norm>1e-8时还须rel<=2e-6；norm<=1e-8只用max_abs。keys/shape/dtype/有限值/梯度/step严格检查。输出、输入/参数梯度、更新后参数、增量、moments共83项。该严格门槛与R1 bf16工程门槛分别报告，不自动豁免AdamW近零敏感项。
3. 用R2未改变的torch_reference路径复现R1原83项指标/28FAIL，验证没有随诊断改动改变bf16候选；记录激活和对应梯度的ref_norm、max_abs、rel、RMS、精确零/符号变化。
4. 仅观测一次原block和一次原bf16 block，重点norm2输入/输出、linear1输入、pre-ReLU、ReLU输出及FFN2；必要时用固定上游gradient和原权重进行局部VJP：只替换ReLU gate，测linear1/norm2梯度变化；同时重构完整bf16局部反传核对实际梯度。
5. 若fp32控制失败，先区分首次前向/反向的舍入差异与真正的编排/导数错误；针对发现的具体环节作一个固定输入的局部对照，不做阈值/随机序列/精度组合搜索。仅在能证明实现错误时修候选。
6. 若量化敏感gate有直接证据，可做一次“固定原forward、反传恢复原fp32 ReLU mask”的诊断反事实；它不是真实候选或正确训练导数，不能据此宣称优化通过。仅用于量化4项大范数梯度失败的来源，不更改原门槛。

无KML实测、集群、完整模型、200步、性能/峰值或S05开工；来源/最小diff、实际新增结果和已证实/未证实边界随R2报告交付。
