# S02 固定更新语义与预先确定的检查

日期：2026-11-04。此文件在候选实现和数值运行之前写入。仅适用 fp32、dropout=0 的当前模型。

## 一次更新

参考有效批量为 B64；比较 B64×1、B32×2、B16×4，并分别比较编码器 CKPT=0/1。它们是测试配置，不是正式训练批量或 schedule 决定。每组从同一个 enc+dec state_dict 和 AdamW state_dict 恢复，学习率 1e-4，betas=(0.9,0.999)、eps=1e-8、weight_decay=0.01。先清梯度一次，逐微批 backward，最后 step 一次；无微批 scheduler.step。当前没有 DDP，不能把 16 个独立进程的 batch 相加称作全局训练批量。

令 N=sum(mask)，C=B*256，D=B*1*64*64：

- pre：L=sum((head_v(h)-v)[mask]^2)/N + sum((head_coarse(mean(h))-pool16(y0))^2)/C。
- dec：L=sum((dec(xt,t,h)-e)^2)/D，xt=sqrt(abar[t])*y0+sqrt(1-abar[t])*e。
- 每个微批的两个 sum 分别除以整批 N、C；不是除以本微批 N_j，也不是简单平均各微批 mean。dec 的等大微批 mean 可除累积次数，但候选统一用 sum/D，可覆盖最后不足一个微批的情形。
- 整批 N=0：原始 mean(empty) 为 NaN；候选在任何清梯度/更新前拒绝，不重采样、不更改目标。N_j=0、N>0 的微批合法，masked sum 为零，coarse loss 仍计算。

先采样整批 mask、t、e、idx，再按相同样本顺序切片。仅重置 seed 不足以证明等价（不同形状调用可消耗不同 RNG）。当前模型无 dropout/BatchNorm；checkpoint 使用已有 use_reentrant=False，不引入新随机源。候选不改变模型、输入归一化、数据或精度。

## 真实数值检查（无 torch 时必须退出 2 / NOT_RUN）

使用冻结原始模型定义，不使用缩小层数/宽度/图像或桩模型。两种协议 M=208/928，完整 12×512/8 编码器和原 U-Net。合成输入仅用于计算等价性，不证明真实 NPZ/语料、训练质量或 C2 性能。参考 loss 直接使用原始 mean 定义，不能拿候选自己的 B64 路径当唯一 oracle。

固定 seed=0。为确保能暴露分母错误，mask 在不同样本块有不同密度，第一 B16 完全无 mask；同一 mask 对所有候选复用。覆盖两个 belt、pre/dec、三个微批及 checkpoint 开关。另用小张量真实 autograd/AdamW 检查：故意平均微批 masked mean 应被拒绝；缺失/NaN/Inf 梯度、错误 step 次数必须失败。不能以这些小检查替代完整模型。

每个浮点张量记录 max_abs、L2 relative=||candidate-reference||2/max(||reference||2,1e-12)、reference norm。逐 tensor 比较；reference norm<=1e-8 仅用 max_abs 判断，避免近零相对误差失真。以下容差预先固定，失败保留证据，不自动放宽：

| 对象 | max_abs 上限 | L2 relative 上限（norm>1e-8 时也必须满足） |
|---|---:|---:|
| 输出 h/prediction、loss | 2e-5 | 2e-6 |
| v/y0 输入梯度、所有预期参数梯度 | 2e-5 | 2e-6 |
| AdamW 更新后参数、相对初值的参数增量 | 2e-5 | 2e-6 |
| AdamW exp_avg、exp_avg_sq | 2e-6 | 2e-6 |

整数/step、keys、shape、dtype、应有/不应有梯度集合严格一致；所有实际张量有限。更新增量也单独比较，防止大初值掩盖错误更新。AdamW 在第一次更新对接近零梯度敏感，若 fp32 累积导致失败，应报告失败位置，再由协调评审，不凭 loss 近似一致接受。

pre 预期 encoder 全部参数有梯度，decoder 无；dec 预期 encoder 除 mask_tok/head_v/head_coarse 外全部有梯度、decoder 全部有。先在 fresh optimizer 上检查 lazy state，再从所有参数均有 AdamW 历史状态的冻结 synthetic state 检查跨 pre/dec 的状态保留；不应更新的参数、已有状态和 step 必须严格不变。

## 内存与远程门槛

静态张量字节/参数计数不是峰值。先交权重/梯度/AdamW 状态的精确逻辑字节和 B/M 相关大张量尺寸，给 S03 的实际同时占用/大小类 trace 暂缺。不要求和互斥生命周期或重复引用 storage，不将 attention N² 理论 score 张量断言为 SDPA 的实际分配。

远程由 S00 恢复连接，使用 S01 已接受运行器再配对：同 host、相同 fp32/KML/HBM 策略、有效批量、固定输入和计时规则，单域→四域→整节点、三有效轮和第二主机。每个有效批总耗时包含全部微批 backward、checkpoint 重算和一次 AdamW；DDR RSS/PSS、hugetlb/HBM 驻留、tensor 同时存活、allocator 累计量分别记账。没有这些证据，不选工作集最小/性能最优配置，不承诺约4GB已达成。本次节点小时为0。
