# S01 无候选提案审核与最小取证规格

结论：**ACCEPT 02 的 NO_JUSTIFIED_CANDIDATE**。Tiny 的相同操作数 fp32 权重梯度分组敏感性，不能直接指向完整 Encoder 的某个 KML 修改点；当前没有足够证据选择一个 fp32 候选。接受该判断不等于接受其所有缺证项都需补跑。本轮没有实现、实验或训练放行。

先核 PROPOSAL_READY SHA=`5204542f26294abbbe3a2fae40c6fbc93b0bb8133ca1e9796e4cf80cac79fb76`、PROPOSAL SHA=`b988cbfec4702e9799ed0a275e3bc8581eb7338d3c6390bc427dfa381c3a9cf4`及32项作者来源，再核必要参考/数据/运行时身份，共52个唯一文件无漂移。详见 STATIC_REVIEW_EVIDENCE.json；本轮只读文本/JSON及计算文件哈希，没有导入或执行作者代码/Torch、反序列化张量、运行测试或查询进程。

独立核对分派与反向：原[kml_linear](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106/baseline/kml_ops.py:194)在输入numel小于65536时调用原F.linear。Tiny最大线性输入为64×208×4=53248，tf只是Linear(4,4)，未走自定义KML backward，不能映射为真实12层Transformer中的某一tf权重。完整模型val输入13312/6656、池化head_coarse输入32768/16384（B64/32）也走原生；pos、12层QKV/out_proj/linear1/linear2及head_v均超过阈值。原生F.linear不等于已证明底层BLAS不经过shim/KML，149个直接调用不覆盖该间接路径。

[_LinearFn.backward](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106/baseline/kml_ops.py:179)中，设X=[L,I]、G=[L,O]：dX=GW，NT/NT，m=L/n=I/k=O；dW=GᵀX，T/NT，m=O/n=I/k=L；db=sum(G,0)由Torch归约。dX与dW的lda=O、ldb=I、ldc=I，alpha1/beta0；pos的固定位置特征不需输入梯度，故不执行该dX。fp32路径的acc32参数不会选择更高精度累加器，不能据其名称提出fp32修复。

独立从job2049454/cn21338的R11原始JSON重聚合step3–5共447条记录，每个B64样本forward50/dW50/dX49=149，ABI/转置/leading dimensions与02摘录一致。50来自pos1+12×4+head_v1，少一次dX对应pos。B64的L=64×208=13312是实际记录；rank32的L=6656、分派不跨阈值及相应计数仅是静态推导，没有实际rank32/完整DDP记录，也不能从R11调用元数据推出数值错误或具体内核。

|项目|审核分类与最小处理|
|---|---|
|M01_FULL_KML_FAILURE|**选择修改点必需的新证据**：先知道固定完整模型首批是否存在分片差异、首个失败参数及真实路径；不必为此先重试DDP。当前不能假定失败必在KML dW。|
|M02_OPERAND_PARITY|**必需的新完整模型证据**：X/G与前向/dX的逻辑分片身份、全部参数梯度/db及输入梯度。已有Tiny已回答Tiny一致性，不能转用为完整模型证明。先用规范化分片哈希定位，无需保存全层X/G。|
|M03_BACKEND_SCOPE|**拆分**：源码阈值、数学/ABI和实际B64直接调用已有证据可答；新配对路径的实际route/库身份和数值仍需取证，可与M01/M02合并。暂不需另跑孤立GEMM或追精确内核。|
|M04_FP32_DIRECTION|**提出具体修改后的条件性证据**：必须说明为何更接近原B64/fp32，而非只更接近float64；当前先取定位证据，不试tile/精度/候选矩阵。取证即使定位成功也不自动产生候选。|
|M05_DDP_AND_LIFECYCLE|**拆分**：默认缩放代码与PG失败事实已有证据；旧父子/15秒/初态/fp64线程缺口保留，不补跑。未来实际DDP验证是后续运行门槛，不是选择当前收缩修改点的先决实验；新取证仍须有前瞻性真实PID/清理协议。|

不采纳PROPOSAL.future_minimal_regression_if_separately_authorized中A_RETAIN_AND_REPRODUCE作为此次取证前提：原Tiny三项失败已保留并独立复核，无需再复现。02明确写了另行授权，故不将它误读为当前执行许可；该范围收窄由本审核明确，不覆盖02冻结原文。

交付**一份** MINIMAL_EVIDENCE_SPEC.json，状态 NEEDS_NEW_EXECUTION_AUTHORIZATION：只问“在原固定首批上，完整B64对顺序32+32的首个观测偏差/失败是否落在X/G一致的真实线性dW分组，还是已在前向、G、dX、原生分支或db出现”。仅一次B64 forward/backward、一次含两个32片的顺序forward/backward，0优化器更新/0DDP/0额外收缩/0Tiny重跑；不替代正式B64参考或五步训练门槛。

规格固定原descriptor/manifest、seed0初权重、原首64索引、post-init mask/hash和image_scale=0.03546142578125；B64用原losses函数的mean表达，不改参考为sum/denominator。顺序片用全局两个分母、系数1，不套DDP系数2；v/image既是模型输入或目标的原梯度路径不得detach。必须按实际逻辑batch轴规范化X/G/dX哈希，不能把展平矩阵前一半一律当rank0（注意力内部布局未必batch-major）。必要张量限完整输出/输入梯度及153个参数梯度；X/G/dX只做当前片观测/哈希，不持久化全层快照，不新增autograd.grad或矩阵重算。

拟议单域38分配/36实际留2、DDR总24GiB同limit/exclusive/HBM0；新job最多300秒，共同执行240+清理30+收尾30，两个模型路径各最多90秒且共同截止优先。附加诊断保留内存≤1GiB、远端原始诊断张量≤512MiB、文本≤64MiB；不能证明预算/映射/被动观察可行则提交前BLOCKED，OOM/超时/身份漂移/缺证据失败即停，不重试或扩资源。资源只是拟议，实际可用性和内存峰值未运行验证。

原小DDP数值门禁仍FAIL。新规格必须获得**独立诊断**的新授权、冻结实现和具体SHA审核，授权中明确允许在旧Tiny失败保留的情况下做零优化器更新的完整模型定位；不能改旧门禁或借用旧900秒许可，更不能复用旧训练入口的“通过”状态。首次差异/失败只标记原阈值结果并停止新增计算，收已有证据；若首批未出现失败则报告范围内未复现并结束，不增加批次/seed/路径。

原compare SHA=`e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`及tensor/state绝对阈值2e-5/2e-6、相对2e-6、近零/finite/exact规则不变；未运行的参数更新/AdamW/恢复门槛明确NOT_RUN，不以本诊断替代。原最终FAIL、DIAGNOSIS_REVIEW和EVIDENCE_CLOSEOUT_REVIEW的SHA均未变。仅写本S01新目录及两份短状态，按ARCHIVE_SCOPE.json供协调与唯一Git窗口另列新批次，不自动追加已完成99批、不暂存提交推送。
