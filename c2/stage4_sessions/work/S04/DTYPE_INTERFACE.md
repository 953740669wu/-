# S04 → S05 dtype 接口 R1

状态：候选接口，LOCAL_ONLY；数值/性能接受须查看 REPORT.md。不是对 S05 开工范围的额外授权。

| 边界 | 输入 → 输出/布局 | 计算/转换位置 |
|---|---|---|
| embedding/第一次 block 前 | fp32 → bf16，contiguous [B,M,512] | 整段入口量化一次；本轮不接完整 encoder |
| 相邻 block | bf16 → bf16，[B,M,512] | 不在 block 之间恢复 fp32；fp32 局部残差不跨 block 存储 |
| norm1/norm2 | fp32 → fp32，[B,M,512] | 输入/均值/方差及 affine 均 fp32，norm 后转 bf16 |
| qkv / out / FFN1 / FFN2 | bf16 激活、fp32主权重/偏置 → bf16 | 每次读取主权重转 bf16；无跨 optimizer step 权重缓存；sbgemm fp32 C，加 fp32 bias 后仅一次 bf16 舍入 |
| 当前 attention | bf16 packed QKV → fp32 Q/K/V → fp32 O → bf16 | 原 SDPA，无新内核/全局 patch；原头拆分顺序 [B,8,M,64]，Q/K/V 为 stride view，交 SDPA；投影前合头 contiguous |
| residual add | bf16 分支 → fp32；fp32 残差 + 分支 | 两次 add 均 fp32；第二次 add 后转 bf16 作 block 输出 |
| FFN ReLU | bf16 → bf16，[B,M,2048] | 保持 bf16 穿过 FFN1/ReLU/FFN2，无中间激活往返 fp32 |
| 最后 block / heads / loss | bf16 → fp32 | heads、mean pooling、MSE、mask 分母保持原 fp32 语义 |
| dX | bf16 上游梯度 × bf16权重 → fp32累积 → bf16 | 后端 sbgemm；入口 cast 的 autograd 恢复原 fp32 x.grad |
| dW / db | bf16 g/x → fp32，再 SGEMM / sum | 永远 fp32 dW 累积，不使用未验证长K bgemm/sbgemm 替代 dW |
| AdamW | fp32 参数/梯度 → fp32 参数/exp_avg/exp_avg_sq/step | 原超参；不改全局 optimizer 或训练入口 |
| decoder/conv | 保留 fp32 | 本轮完全未触及 |

候选只支持原规格、CPU、训练/有梯度路径、无 mask/causal/dropout，其他输入明确拒绝，不静默 fallback。原 fp32 文件逐字节保留作为回退。
候选 kml 模式要求 Linux 和实际 KML 库；不存在则拒绝。torch_reference 模式明确用 fp32 GEMM 模拟量化输入的累积，不能当作实际 bf16 核、KML 或速度证据。
KML 原 gemm 的 sbgemm 分支以零 C / beta=1 调用，绕开历史 beta=0 缺陷；当前机器未实测这个假设。dW 用原 fp32 gemm 路径，C2 仍须实际验证。

## S05 可接的边界

未来 attention 接口拟为 bf16 q/k/v、[B,H,N,d] stride 输入或在接口内显式 contiguous、返回 bf16 同形状；score/softmax/LSE 与必要 backward 累积 fp32。
在 S05 独立验证前，当前实现始终用上述 fp32 attention 岛，不替换。mask/dropout/causal、decoder cross-attention 支持范围由原 S05 任务决定。
原 attention 门槛 bf16<=2e-3、fp32<=2e-6（输出及所有输入梯度）不受 S04 block 工程筛选门槛影响。

## 转换与静态字节账

令 T=B*M，D=512，H=2048。每个 block 正向的稳定计算边界有8次激活转换：
x→fp32(TD)、norm1→bf16(TD)、packedQKV→fp32(3TD)、attention O→bf16(TD)、outproj→fp32(TD)、norm2→bf16(TD)、FFN2→fp32(TD)、block输出→bf16(TD)。
另4次权重量化（3D²+D²+DH+HD 元素）；sbgemm 原生返回 fp32 C 后4次输出量化（3TD+TD+TH+TD 元素）。总正向16次显式 dtype 转换；整段入口/出口另算2次。
backward 每个 linear 的 g/x 各一次转 fp32作dW（8次）及dX fp32→bf16（4次）；autograd稳定岛反向转换另计，不能把正向16次当整步总次数。
torch_reference 为模拟 sbgemm 额外把 bf16 operands 恢复 fp32，不能用该模式统计 C2 转换收益。
bf16 block 边界逻辑 payload 为2TD bytes，fp32 为4TD：B64/M208 时13,631,488 vs 27,262,976；M928 时60,817,408 vs 121,634,816。
这些是张量逻辑大小，不是驻留峰值、实际内存流量或实测节省。转换耗时/总步耗时均未测；fp32 islands及C scratch仍可能抵消收益。
