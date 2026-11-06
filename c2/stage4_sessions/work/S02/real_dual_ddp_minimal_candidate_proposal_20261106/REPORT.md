# 完整 Encoder/KML 最小数值候选：静态结论

2026-11-06（Asia/Shanghai）。结论 **NO_JUSTIFIED_CANDIDATE**，候选0个。现有证据支持 Tiny 的同操作数 fp32 权重梯度对分组累计敏感，尚不足以选择完整 Encoder/KML 上一个具体修改点。本轮只做源码、JSON及SHA静态核查，0模型/收缩/测试/DDP/基准/SSH/job，无Torch导入或张量反序列化；未实现候选。

## 来源与原结论

先核32份来源SHA，再定向读冻结代码和诊断相关字段。SOURCE_INPUTS.json逐项列绑定；冻结baseline模型9ff6417b…、kml_ops e6c5c441…、compare e9b53136…及REFERENCE_READY 924a972e…保持。原S01最终审核FAIL，不放行真实模型DDP；本轮不重写原件。诊断接受范围为ACCEPT_PARTIAL_DIAGNOSIS_NOT_TRAINING_ACCEPTANCE；收尾ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS只允许有限证据归档，不是数值/历史清理或训练通过。

S01原诊断确认：当前Tiny完整B64与连续32+32前向/输入和输出伴随量相同，仍复现val.weight、pos.weight、tf.weight三个梯度FAIL及原13项标量误差。label `parameter.*`在诊断代码121—131行表示parameter_grads，不是AdamW更新后参数。最早非零是coarse loss约2.98e-8，仍过阈值；按反向依赖观察最早超阈值为Tiny tf.weight（abs3.7238001823e-5、rel1.1428691335e-4）。val/pos的abs1.9147992134e-5虽小于2e-5，但rel9.4101910881e-5超过2e-6，仍FAIL。不能只看绝差，也不能因较早loss舍入非零就宣称它导致dW差异。

原同操作数fp64原因对照将val/pos分组差降至0、tf约6.83e-14，支持累计精度敏感性；原两个fp32结果相对fp64均有误差。提高对fp64的准确度不保证更接近冻结fp32完整B64参考。原始内核/指令未知，fp64自身实际线程快照未记录；不是完整模型/KML修复或生产精度建议。

## 实际线性反向与归约路径

冻结kml_ops.py:194—202的门槛是 **输入x.numel()<65536就走原F.linear**，并非按权重大小、输出numel或函数名字选择。configure_backend只patch_linear，保留原native SDPA。设X=[L,I]、W=[O,I]、G=[L,O]，L在token线性处是B×208。

- `_LinearFn.forward`（166—176）保存本次调用的完整flatten X/W；fp32不降精度，有bias时先填Y再以beta1 GEMM。
- dX（182）：`gemm(g,wc)`，row-major NT/NT、(m,n,k)=(L,I,O)、alpha1/beta0；只在输入需要梯度时执行。逐行内归约长度O，batch仍改变GEMM形状/库选择，不能据此保证分片逐位相同。
- dW（184—186）：fp32实际为`gemm(g.float(),x2.float(),ta=True)`，T/NT、(O,I,L)、alpha1/beta0；lda=O、ldb=I、ldc=I，单次原_sgemm使用完整本地L。Python没有拆K或部分梯度累计。fp32保持描述的是ABI/张量类型，不证明KML内部累加细节。
- db（187）：`gy.reshape(-1,O).sum(0)`，Torch fp32跨L归约，不走这里的_sgemm。`acc32`分支只用于bf16，不能把它当作fp32更高精度累加开关。
- 原F.linear分支由Torch autograd形成dX=GW、dW=G^T X和bias归约；具体融合/addmm/mm及内核未经本轮追踪，不能把公式当实际内核证据。C2加载shim/KML后，原生Torch内部BLAS也可能间接用库；“原F.linear”仅表示不进该自定义反向，不能说完全不使用KML。

下表B64的L=13312、每rank32的L=6656；B32列是冻结源码的静态推导，**不是实际模型DDP采样**。KML行均沿上述dX/dW/db公式，dW列为(m,n,k)。

|完整模型位置|次数|I→O|B64/rank32输入numel|分派|dW形状B64 / rank32|dX及db|
|---|---:|---:|---|---|---|---|
|val|1|1→512|13312 / 6656|原F.linear|512×1，归约13312 / 6656|dX归约512；db跨L，原生autograd|
|pos|1|65→512|865280 / 432640|自定义KML|[512,65,13312] / [512,65,6656]|位置输入不需梯度，dX=None；db Torch sum|
|12层packed QKV|12|512→1536|6815744 / 3407872|自定义KML|[1536,512,13312] / [1536,512,6656]|dX归约1536；db Torch sum|
|12层out_proj|12|512→512|6815744 / 3407872|自定义KML|[512,512,13312] / [512,512,6656]|dX归约512；db Torch sum|
|12层linear1|12|512→2048|6815744 / 3407872|自定义KML|[2048,512,13312] / [2048,512,6656]|dX归约2048；db Torch sum|
|12层linear2|12|2048→512|27262976 / 13631488|自定义KML|[512,2048,13312] / [512,2048,6656]|dX输出2048、归约512；db Torch sum|
|head_v|1|512→1|6815744 / 3407872|自定义KML|[1,512,13312] / [1,512,6656]|dX归约1；db Torch sum|
|head_coarse|1|512→256|32768 / 16384|原F.linear|256×512，归约64 / 32|dX归约256；db跨B，mean池化反向另跨208 token|

为核“实际”而非仅按结构推断，额外只读核了已有R11 job2049454的绑定原件及相同模型/KML源码SHA：三份B64记录均forward50/dW50/dX49=149直接GEMM，fp32实际KML/Torch36；各dW组和dX组吻合上表，pos未做dX。见evidence/R11_EXISTING_CALL_METADATA.json。它们只能证明历史单域B64调用/ABI，不证明B32库内归约、两侧数值或修复；149不含原F.linear内部BLAS及Torch db归约，也不是全模型所有算子。

除线性外还包括native SDPA、LayerNorm（含其affine梯度）、mask_tok展开/where归约、h.mean(1)、图像池化和两loss归约/残差梯度。它们不由一个KML dW修改覆盖。完整训练使用原153个参数名；Tiny tf.weight不是实际tf.layers.*中任意一个参数的一一映射。

## Tiny可对应与不能外推

Tiny（原torch_checks_worker.py:30—42，诊断worker.py:44—64/166—215）是seed7、宽4、tf=单个Linear(4,4)，输入v/angles为1、image为0、全局仅4个masked元素；没有12层真实Transformer/真实语料seed0随机mask。诊断full/sequence两种模式仍运行这个Tiny；“full”不是完整Encoder。

其val/pos/tf的输入numel分别13312/53248/53248（B64），B32再减半，都低于65536；原Tiny/诊断也没有调用configure_backend去装配实际KML自定义反向。即使放进相同dispatcher，这几个Tiny调用仍fallback原F.linear。head_v同为53248，head_coarse为256。可对应的是dW=G^T X及对行归约分组这一数学问题；完整val也走原生autograd，但其O=512而非4、伴随量/样本不同。完整pos则是65→512且走自定义KML；真实tf含QKV/out/FFN、native SDPA与归一化，不能把同名Tiny失败当相同算子/操作数。

真实DDP另有本地world2反向系数、参数梯度reducer平均和日志分母collective；原源码保持2×本地sum/全局分母，输入grad比较除2、参数grad不再除2。Tiny sequence只排除当前样本中“必须有DDP才会失败”，不能排除实际DDP新增效应。新诊断在PG完成前权限错误停下，没有新增DDP梯度/分母/缩放/归约向量；原训练FAIL保持，完整模型DDP未运行。

## 为什么不选择修改点

缺少（1）完整Encoder实际KML中首个失败参数/调用；（2）对应B64/32两侧X/G身份和dX/dW/db局部归因；（3）实际KML形状分组对照及允许的fp32改动方向；（4）真实DDP分母/reducer路径验证。已有R11仅B64观测，没有这些数值配对。Tiny forward/adjoint相同这个前提未在完整模型成立。

因此本轮不选择任何dW分块、阈值例外、参数精度或归约替换。只改KML dW会漏过同样可能失败的原生val；只因Tiny tf失败就改实际某个FFN无一一对应；db在当前Tiny通过也不能推广为完整模型无关。原输出列分块R12仍按无收益结案，不复活搜索。float64若成为训练计算/参考替换会改变现有执行契约，超出约束；原fp64只保留为诊断对照。

将来若实际首个失败在原生val/head_coarse、前向/dX/db或reducer，KML dW单点解释即被证伪；若X/G已经不同，同操作数Tiny解释不足；若实际同操作数KML dW过原阈值，也没有据此修改其累计路径的依据。这些是可检查的缺项，不是“所有fp32方案都不可能”的结论。

## 仅拟定的后续最小验收

本轮无执行许可。若协调另发独立任务，先在新目录冻结并复现原Tiny 3/13失败作诊断对照（不能把Tiny或32+32作为正式参考），保留原失败；再定向补一个固定真实首批B64/32对照的实际调用/操作数/局部梯度身份，确认首个差异属于哪个算子，不搜索形状。若未出现实际KML dW失败，就停止该KML候选方向。

只有定位后能解释ONE允许的fp32修改，才另交具体单点提案/01审核、获准制作独立候选。届时要求原失败可复现、唯一改动的dW验证、dX/db/ABI/边界/alias/计数和全参数覆盖保持；任何不符停止，不转第二方案。最终仍是原完整B64/fp32参考、原compare类别/阈值下连续前5步：输出、loss、输入梯度、全部参数梯度/更新参数/init delta、AdamW step及一二矩/buffers，参数与优化器连续承接；前5任一FAIL就停止后续，保存/零额外更新恢复仍须核。新的总次数/资源/截止由新任务卡明确，不能把这些建议当授权命令。

原compare张量abs≤2e-5、state abs≤2e-6，且norm>1e-8时rel≤2e-6；exact仍逐值相等，NaN/Inf/缺项/shape/dtype拒绝。只在比较计算误差范数时使用float64，不改变生产fp32。seed/样本/顺序/mask/归一化/损失/AdamW、正式B64及原FAIL均不改。

## 收尾限制与交付

E01—E06限制照录PROPOSAL.json：新DDP未完成、精确内核未知、历史完整向量/初态/线程证据不足、fp64实际线程快照缺失、初始张量未留存；历史compute/后代身份与15秒清理亦未证实。归档接受不填补它们，也不要求本轮再查PID或恢复证据。

交付PROPOSAL.json、REPORT.md、PROPOSAL_READY.json、精确ARCHIVE_FILES.json和两个静态来源/调用元数据记录。无候选源码、补丁包或执行命令。本轮不操作其它目录/冻结源/原FAIL/共享Git；更新自身短状态/六行摘要，交协调判断后待命。
