# 后续小试提案（未执行、不是job授权）

当前结论：单 block 本地量化工程门槛 FAIL；不能凭输出/loss通过安排性能实验。本轮集群job=0、节点小时=0。

## 先处理本地失败

保持 NUMERICAL_PLAN.md 的夹具、AdamW和门槛，先查 ReLU 零点附近量化导致的梯度变化及近零梯度经fresh AdamW放大。
这是待验证的假说，尚未作因果定位。不得调阈值/换随机输入追求通过；若要改稳定计算边界，另立候选diff并记录成本。
如果bf16跨block本身无法满足预定工程门槛，应由协调评审精度取舍，不能把本地FAIL称科学质量退化或擅自放宽。

## C2 单域算子前置（只在协调另行排期后）

- 一台独占计算节点，一个38核域，实际选域内0..35，保留36..37；36是域内编号，须换成实际Linux CPU IDs。
- OMP_NUM_THREADS=36、MKL_NUM_THREADS=36、OPENBLAS_NUM_THREADS=1、OMP_PLACES=cores、OMP_PROC_BIND=close、Torch intra-op=36。
- 继承S01已核runner、S02 cpu36_contract/guard；检查caller affinity及相关TID子集而不是要求caller同时含36核。
- DDR/原FP32分配策略，CKPT0；不改HBM分配器或共享库。核 torch/KML/OMP/shim 实际映射与SHA，直接KML调用计数；环境不符退出NOT_RUN，禁止torch fallback冒充KML。
- KML fp32 SGEMM 先对照torch fp32；dW长K分别13312(64*208)、59392(64*928)，M/N取4/8的小矩形限制成本。
- bgemm 同样K=512/2048/13312/59392，记录bf16 C累积与长K误差；这是诊断，候选不调用bgemm，不用其峰值判断收益。
- sbgemm 对 bf16输入/fp32 C，先以量化输入fp32 GEMM为oracle；测试out=None以及有限非零C，beta=0/0.5/1；直接原生beta=0哨兵C另测，区分历史库缺陷与wrapper零C/beta=1规避路径。
- 必须先依据实际安装kblas.h核签名，保留基线中历史ABI不是本轮验证结论。sbgemm真正fp32累积仍待长K误差及库核实。
- 后续新增算子验证建议逐tensor相对L2<=2e-5（SGEMM/sbgemm相对量化fp32 oracle）、bf16 bgemm<=2e-3；ref_norm<=1e-8时RMS_abs<=1e-7，记录max_abs。这是**尚未执行的验证提案**，正式运行前由协调冻结；不替换现有block/attention门槛。

## 一个block再小试

仅在本地失败已解决、上述前置及包身份通过后，准备**新的**actual-KML数值入口和CPU36身份收集器。当前check_block.py只支持torch_reference，不能直接用它声称C2实测。
用本包固定seed/张量SHA和原规格单block/原fp32 heads及loss，先B2/M17、一次fresh AdamW；FP32对照也须明确实际SGEMM路径而非混入未记账的fallback。
先按本轮原门槛逐tensor比较输出/输入和参数梯度/参数及增量/moments，全部过门再考虑B64/M208单block；不跑完整模型或200步。
正确性通过后另排同机A/B/A阶段计时；记录转换次数、转换耗时、forward/backward/AdamW/总步、RSS，时钟不得被比较快照污染。

## 资源与停止条件

提议最多1节点×300秒=0.0834节点小时，单域36实际核、内存limit 24576MB，沿用已核runner更严格的现有限制；登录节点只核身份，不做计算。
外层300秒为总预算，不与各case超时叠加；单个case建议60秒，内存超限、非finite、缺失梯度、身份/CPU违规或数值超阈立即停。到期结束整个候选进程树，保留完整失败和终态，不自动重试或扩资源。
下一轮若数值未通过，停止性能部分，不自动提交第二job。预算/实际节点小时、原始命令与每步时刻回传S00。
200步固定随机序列loss轨迹（逐步与聚合分母另行事先冻结）、整模型训练质量、至少四域/整节点三轮性能与第二主机，全部仍是后续门槛；历史50/5fps单列，当前零收益声明。
