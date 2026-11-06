# S01 本地数值诊断 R1 独立复核

结论：**接受有边界的部分诊断，不接受“根因全部查明”或训练放行**。当前本地 B64 与顺序32+32的梯度差异，已有充分证据定位到相同操作数的 fp32 线性权重梯度收缩/累计行为；具体 native 内核/指令与新增 DDP 额外影响仍未知。原训练 S01_REVIEW 最终 FAIL、原阈值与全部冻结来源不变，本轮不发布训练 PASS。

先核07固定 DIAGNOSIS_READY SHA=`de9c6e26ea7d2f280b835e1de44dbc4697d0fee2c0cc69fe66b4fa986bf07dde`，11项直接绑定无误；再沿17项来源、39项证据及解释器身份核验，共60个唯一文件 bytes/SHA一致，包含原始 raw/full.pt 与 raw/sequence.pt。DIAGNOSIS SHA=`b24834c500da2cb595ad9baf548fad6f922d7c51a773ac27daec1e665202a3e4`。完整核验与指标见 [EVIDENCE_REVIEW.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_numeric_diagnosis_r1_20261106/EVIDENCE_REVIEW.json)。

S01 只反序列化这两份已保存的小张量，用原 compare 函数复算34项既有指标，逐项与07结果一致；没有重跑 forward/backward、矩阵收缩、float64原因对照、DDP或优化器。34项包括18份前向/adjoint观测、3项loss、11项参数梯度、2项输入梯度。原13项梯度的四个标量字段（max_abs/relative/reference_norm/passed）全部与原失败原件相同，未丢失败项。使用的原比较器 SHA=`e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`。

一致性核对：

- 原 TinyEncoder 类由冻结源码 AST 提取，图与 loss 复用原文件；seed7、1337参数、0 optimizer更新。full/sequence/两rank pre-PG准备的初始化SHA均为 `38a200103f7ca459effccbc4c70f17549ae1573ee08bf1d346f00883c6da17d3`，post-init RNG SHA也一致。没有保存初始权重张量供再次逐张量比较，但同一构造源码、seed与运行时采集摘要支持本轮初值一致。
- 完整B64的两个32片输入/mask摘要逐项等于顺序路径，分片范围为[0,32)、[32,64)，新rank准备的输入摘要也等于对应片。原mask位置[0,6656,6657,6658]，局部masked数1/3、coarse数8192/8192，全局分母4/16384；原全1/全0样本不变。新DDP未到执行mask/计数阶段，不能补称其运行时分母已验证。
- full/sequence采用同一全局目标，每片反向均为 `Sv_r/4+Sc_r/16384`；只在开始清一次梯度，不额外平均。DDP源码采用2倍本地目标、默认reducer平均，参数梯度不再除2，输入及adjoint诊断归一化除2；该数学/代码路径正确，新增DDP未完成，运行证明仍缺。
- full/sequence/两rank准备的解释器、Torch2.7.1+cpu、NumPy2.2.6及环境记录一致，实际intra/inter-op均8/8，OMP/MKL/OPENBLAS等所列变量均未设置。没有线程搜索或设置变更；这不是C2 Torch36证明。旧失败未保存实际线程/初值张量摘要，不能宣称与历史环境完全可比；float64单独进程没有采集实际线程快照，也不能把四个准备记录当成包含该进程。

在已采集的观测点，18份前向/反向中间梯度的张量字节全部相同。最早观察到的非零标量差为 coarse loss 归约：最大绝对差 `2.9802322387695312e-8`，total loss差 `5.960464477539063e-8`，均通过原门槛。这是计算图层次上的定位，不是指令时间线；loss字段也有汇总重建过程，不能据此声称取得了实际指令级“第一处差异”。相同adjoint说明这项标量差不能直接当作已证实的梯度偏差传播原因。

按反向依赖顺序，最早越门槛的是 tf.weight 的权重梯度收缩，val.weight/pos.weight也失败：

|参数梯度|最大绝对差|相对L2|原门槛结果|
|---|---:|---:|---|
|tf.weight|3.723800182342529e-5|1.142869133502608e-4|FAIL|
|pos.weight|1.9147992134094238e-5|9.410191088070238e-5|FAIL|
|val.weight|1.9147992134094238e-5|9.410191088070238e-5|FAIL|

这里的“最早”指首个越阈值位置；head_coarse等参数也有未越阈值的非零差异，不能说其它参数梯度全部逐位一致。输入梯度和其余原项通过，不能覆盖三项失败。

支持的原因：full与sequence的val/pos/tf线性层输入及输出adjoint逐字节一致，而三份权重梯度不同；不使用DDP的顺序路径已复现旧13项标量误差，因此这种失败无需DDP也会出现。已有float64控制只对相同记录操作数做 `G.T @ X` 全归约与两半求和；用途文件先于RUN_fp64标记，且在DDP尝试前完成。其分组差在val/pos为0、tf为绝对 `6.827871601444713e-14` / 相对 `2.2052381555180308e-13`，支持形状/分组相关的fp32权重收缩累计精度解释。两种原fp32梯度相对该float64值仍各有误差，这不是已提出的fp32修复。S01核了该代码/操作数/回执和SHA，没有再执行一次float64收缩。

限当前full/sequence样本可排除：输入/mask/新初值摘要不同、前向或已采集adjoint差异作为该三项失败的起点，以及错误地平均两个local mean/重复除2。不能全局排除DDP缩放/运行时缺陷：旧误差标量完全相同并不证明未保存的DDP梯度向量相同；也不能由float64改善证明某个特定系统库存在bug。

新增DDP在before_pg后出现10013及10049，未见after_pg、无ddp raw张量或合并结果。停止后没有新数值路径；full/sequence/fp64/ddp各一次，路径耗时约3.484/2.719/2.672/2.719秒，总READY壁钟11.797秒，均在60秒/清理15秒/总300秒内。禁止把本轮通信停点写成DDP数值通过。

清理存在证据不足：监督记录的Popen PID与实际worker自报PID不同，例如DDP监督116596/111740、worker自报118980/123980。代码中all_reaped只检查直接Popen句柄，未提供这两组PID的父子归属和实际worker退出/后代回收时间，不能确认“全部后代在15秒内回收”。S01于2026-11-06T10:42:27Z只读查询四个已知计算PID，均返回NoProcessFound；这能证明当时这些PID已不在运行，不能补出停点时序或证明没有其它后代。见 [CURRENT_PID_CHECK.json](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S01/real_dual_ddp_numeric_diagnosis_r1_20261106/CURRENT_PID_CHECK.json)。没有发送信号、提权、重试或启动监视。

最小下一动作：07若已有PID归属/实际worker退出原件，可只读补交；没有就保留清理时限证据缺口，不为补证重跑。协调可基于已支持的权重收缩位置决定是否另立最小候选任务；本轮不实施修复，也不授权重新通信、训练或集群作业。新DDP向量/缩放、具体native内核、历史完整可比性及float64进程实际线程仍未知。顺序分片和float64只作原因对照，原完整fp32/B64验收及原FAIL不变。

本次review_complete=true仅表示这次独立复核完成，数值验收仍FAIL；当前交付DIAGNOSIS_REVIEW.json明确列出支持、排除范围、未知与不足。只写S01本R1目录及短状态，不改07交付/源码/旧包/协调文件，不操作共享Git。归档范围见ARCHIVE_SCOPE.json。
