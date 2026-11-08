# B dtype 接口

QKV 权重梯度单点替换。旧 P1 的 FFN2 前向量化改变了向前传播的值，P1 的四个梯度 FAIL 在 linear1 和 norm2。B 保留全模型 FP32 前向、注意力、softmax、归一化、ReLU、残差和 dX/db。QKV dW 把已经成形的连续 FP32 G 和 X 各转成 BF16 一次。历史 C1 的 QKV dW 是唯一达到 ≥1.7× sgemm 的 dW 形状，2.4× 为旧算子测量。

输入形状为 [tokens,1536] 和 [tokens,512]。转置 G 作为 row-major A，X 作为 row-major B。输出 [1536,512] FP32，显式清零，sbgemm beta=1。BF16 操作数仅活到同一次 GEMM 结束。完整 Encoder 每步预期 12 个 BF16 dW 和 24 次单向转换，记录实际次数、转换元素、打包、清零及调用耗时。

先找目标安装的 kblas.h，核声明与冻结库 SHA，编译私有 wrapper，再用实际 C2 符号验证 BF16 操作数、FP32 C 和清零。目标安装目录缺头文件时，使用经官方校验且库文件字节与现场完全一致的同发行头文件。无匹配来源或 ABI 无法核实则停止模块数值。

模块 fp32 控制使用 S04 自定义分解 block，禁用整个参考 block 和 MHA forward。BF16 侧仅对原 QKV 参数选择新 dW。使用原 83 项比较器。既有 S04 Python 环境仅导出固定输入和初态并逐张量核旧 SHA，避免跨架构 RNG 差异。
