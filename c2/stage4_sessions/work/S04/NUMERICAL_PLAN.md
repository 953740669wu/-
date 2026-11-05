# S04 R1 数值协议（实现前冻结）

2026-11-05；只验证一个原规格编码器 block。不是 S02 fp32 等价门槛的修改，不接受生产部署。

参考：S02/round7_seq5_20261105T082315Z/baseline/{s4_models.py,kml_ops.py}，SHA 分别为
9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2、
e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26。
使用其中 Encoder(depth=1) 只取得原始 512/8/2048、pre-norm、ReLU、dropout=0 的第一层和原 fp32 heads；不运行完整模型。
CKPT=0、无 AMP、无 attention patch、无 checkpoint、无卷积。

## 固定对象与语义

- 权重 seed=0；构造原 Encoder(depth=1) 后，输入使用独立 CPU Generator seed=20261105。
- 单 block 单元夹具 B=2、M=17、D=512；x/目标 v/y0 为独立标准正态 fp32；mask 为 rand<0.5，固定 mask[0,0]=True。
- x 是模拟的上游 block 输出，不是原始电压 embedding；这些输入不是 S02 固定 B64/M208 case，也不证明其数值通过。
- 两侧完全相同权重、x、v、y0、mask；候选唯一入口量化为 x.to(bf16)，输出在 fp32 heads 前恢复 float。
- loss 原式：MSE(head_v(h)[...,0][mask],v[mask]) + MSE(head_coarse(h.mean(1)),adaptive_avg_pool2d(y0,16).flatten(1))。
- 不拆批；每侧 fresh AdamW，只清梯度一次/backward 一次/step 一次；lr=1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0.01。
- 所有 block/head 参数、参数梯度、AdamW moments/step 均 fp32；state_dict 名称/shape/dtype 一致、step=1。
- 保存权重和各输入的 dtype/shape/payload SHA，禁止只拿 seed 冒充跨环境 bitwise 复现。

## 实现前固定的工程筛选门槛

误差逐 tensor 以 float64 算：rel=||got-ref||2/max(||ref||2,1e-12)，报告 max_abs、ref_norm、RMS_abs。
当 ref_norm<=1e-8 时，改用 RMS_abs<=1e-7；不删除近零梯度。否则必须满足下表 rel。
任何缺失/多余梯度、NaN/Inf、shape、参数/state dtype 或步数错误均 FAIL；输出 bf16 是唯一有意的接口 dtype 变化。

| 对象 | rel 上限 | 依据/用途 |
|---|---:|---|
| block 输出（恢复 float 后） | 1e-2 | bf16 量化跨多个算子的保守工程筛选；新增提案，不冒称原计划已批准 |
| 原 pre loss | 1e-2 | 原计划 ≤1% 目标，单次仅必要条件，不代替200步 |
| 输入梯度、每个 block/head 参数梯度 | 2e-2 | 新增工程筛选；逐参数保留，包括近零 bias |
| 更新后参数 | 1e-2 | 另查增量，防大初值掩盖错误 |
| 参数增量（after-initial） | 5e-2 | 新增工程筛选；fresh AdamW 对近零梯度敏感，不按结果放宽 |
| AdamW exp_avg / exp_avg_sq | 2e-2 / 4e-2 | 一阶/平方梯度量化的工程筛选 |
| 原 fp32 单 block 对照控制 | 2e-6 | 原 attention fp32 精度尺度；这里只验证 unchanged 路径的复现 |

S05 attention 的独立 bf16 输出及梯度 rel<=2e-3、fp32<=2e-6 保持；本轮不实现/验收 bf16 attention。
本轮 attention 输入恢复 fp32，调用原生 SDPA；对相同 q/k/v 单独核调用路径未改变。
本地 torch_reference 模式模拟 bf16 量化后的 fp32 累积，不运行 KML，不是 bf16 GEMM 性能证据。
实际 KML sbgemm forward/dX、fp32 SGEMM dW、长 K/beta/初始 C 行为全部另列 NOT_RUN。

## 先测再实现与后续门禁

先写测试，记录候选符号缺失的红灯，再实现；协议文件 SHA 在红灯前保存。数值 FAIL 不阻止交付准备材料，但禁止扩模型/性能实验。
先检查 comparator 的过阈值/近零/NaN/Inf/缺失/shape 负控；然后运行 linear 梯度 oracle、dtype/state/无全局 patch 拒绝检查与上述单 block 对照。
失败保存全部逐 tensor 指标，不中途只留下第一条；实现错误可修，门槛和夹具不可随结果改动。
无200步、无完整编码器/U-Net、无远程连接/集群job、无计时/HBM结论。
