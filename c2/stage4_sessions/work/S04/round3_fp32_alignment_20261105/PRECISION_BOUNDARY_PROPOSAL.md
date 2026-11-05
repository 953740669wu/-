# 唯一后续提案 P1：扩大内部fp32稳定计算范围

状态：**仅提案，未实现/未运行，不是新bf16接受或S05开工授权。** R3只完成了一次无量化fp32控制对齐；R1实际量化模式仍28FAIL。

目的：针对R2已观察的FFN1/ReLU gate敏感性和QKV梯度量化抵消丢失，只提出一套边界。不附加第二套精度组合。

| 模块/边界 | P1拟采用的dtype与路径 |
|---|---|
| block入口/出口、相邻block | 保留bf16 contiguous [B,M,512]；进入block恢复fp32残差，最后一次残差相加后转bf16 |
| norm1→QKV→SDPA→out projection | 输入恢复fp32后全程fp32；沿R3已对齐的native算子/布局/autograd，不在QKV或其反向梯度中插bf16 cast |
| QKV dX/dW/db、bias归约 | fp32梯度生成、fp32归约和参数梯度；不得把已量化g再float求和冒称“未量化fp32归约” |
| norm2→FFN1→ReLU | 输入、主权重、偏置、preactivation、ReLU保存值和反传均fp32；使用本路径自身preactivation产生gate，不读参考mask |
| 仅FFN2 GEMM | 接收fp32 ReLU输入，算子内部将输入和W2派生为bf16 operands；fp32累积/C、fp32 bias及输出，直接与fp32残差相加 |
| FFN2反向 | 上游g保持fp32；dX用量化后W2恢复float作fp32 GEMM，直接向fp32 ReLU返回fp32梯度；dW用g及量化后激活恢复float作fp32 GEMM，db由未量化g在fp32求和。不能先把g/dX转bf16再恢复float |
| 参数/AdamW、heads/mean/loss、decoder/conv | 沿用fp32主参数/梯度/AdamW moments，原heads/loss；decoder/conv不动，无全局autocast |

FFN2拟为fp32输入/输出、内部bf16 operands的显式混合精度算子，其反传策略须独立记账，不能把它等同于旧bf16输入/输出算子。权重派生仅本次forward使用，不跨AdamW更新缓存。实际KML sbgemm/FP32 SGEMM和库ABI仍须以后另验，当前不作后端承诺。

## 仍可能失败的路径

- 入口x已经量化，恢复float不能找回丢失的信息；norm1、attention、norm2以及FFN1的实际输入仍可能偏移，ReLU gate仍可能改变。把FFN1/ReLU留fp32不等于恢复原参考gate。
- 出口bf16量化仍影响heads/loss及反向梯度；FFN2的量化输入/权重也会扰动梯度符号，fresh AdamW仍可能使增量超过5%。
- P1移除的是R2定位到的**内部**QKV梯度量化和FFN1内部量化边界，不保证原83项通过，更不保证训练质量。

## 布局、转换与成本

block接口沿用bf16 [B,M,512]，attention在内部沿R3的[M,B,D]及[B,8,M,64]布局，稳定计算全程fp32；FFN2输入局部派生bf16，不改变外部FFN1/ReLU的dtype。
若按上述接口实现，单block正向显式dtype转换静态为4处：入口bf16→fp32、FFN2输入fp32→bf16、W2 fp32→bf16、block出口fp32→bf16。整模型入口/heads出口另计，反向及布局contiguous复制另计；这不是实测转换次数或耗时。
FFN1/ReLU与QKV保存张量转为fp32，单个相同shape逻辑payload由2字节/元素升至4字节/元素；例如每个[T,2048]中间张量从2*T*2048变为4*T*2048字节。不能由“转换减少”推出峰值/内存流量或总步收益。
保留更多fp32数据可能抵消原跨层bf16的带宽目标。当前转换耗时/内存峰值/性能全部未测，不以该提案预告收益。

## 唯一有限验证与否决条件（将来另行安排，本轮不执行）

只用原B2/M17/D512、同权重/输入SHA、原heads/loss/AdamW/2线程。先保留R3原fp32控制83项PASS，再对P1作一次原bf16工程83项对照；不更换seed/样本、重置eps或使用参考gradient/gate。
逐tensor门槛完全沿用R1/R2：输出/loss/更新后参数rel<=1%，输入/每个参数梯度及exp_avg<=2%，更新增量<=5%，exp_avg_sq<=4%；ref_norm<=1e-8用RMS_abs<=1e-7。keys/shape/参数与状态fp32/finite/应有梯度/一次step严格检查；所有83项必须通过，不能用平均通过率接受。
任一旧失败仍在或出现新失败，即否决P1并停止本分支追加精度组合；若内部fp32范围已抵消原目标，也建议结束当前跨层bf16候选方向。不得回退到“参考gate反事实”追PASS。
即使本地83全过，亦仅接受该固定单block数值候选，后续KML、性能、完整模型/200步/训练质量门槛独立保留，不自动触发集群试验。
