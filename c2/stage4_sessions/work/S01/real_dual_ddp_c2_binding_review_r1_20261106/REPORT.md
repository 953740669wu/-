# S01 目标C2源码绑定独立静态审核R1

结论：**ACCEPT_FOR_LOCAL_PREPARATION**。新增实际C2前端源码与协调已批准的专用非叶输入边方法增补，足以解除B01的**设计证据**阻断，建议协调另派02进入新的本地准备。不是实际autograd、数值、内存、库加载或退出验证通过；本轮implementation/execution/training_authorized均false，不发布PREPARATION_READY。旧B01终态保留，不倒改历史结论。

包SOURCE_BINDING_PACKET SHA=`b0a0c1e11fb0ba26987f69cfc13b24eb15dc97820f141cfa835857af56edd93f`与任务卡一致，方法增补卡SHA=`528027e6e639a6f389357aafdda9179d22f2f9e3b4a288902d88ea11cfa0c04f`已核。59个唯一当地文件bytes/SHA一致；六源共432651bytes逐份等于原始NDJSON导出的base64字节。Python与torch/__init__冻结锚首尾一致，-S/PathFinder记录关联原R4解释器与实际包根；version.py静态版本2.7.1+cpu、git e2d141dbde55c2a4370fac5165b0561b6af4798b。

6份AArch64/ELF核心身份元数据与原始导出一致。这些是本次首次记录，S01没有取得或独立重哈希二进制，也没有证明旧job使用相同核心库。PathFinder关联不是框架实际导入/加载证明；后续运行仍须核实际module origin、库映射及SHA。详见 STATIC_BINDING_AUDIT.json。

**hook API与专用边**：[目标_tensor.py:652](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_c2_source_binding_r1_20261106/sources/torch/_tensor.py:652)约定hook(grad)返回Tensor或None、不得改参数，返回handle可remove；687–694只要求requires_grad，并为有grad_fn的Tensor注册hook字典，因此支持所需非叶输入/输出边，不需猜native Node槽位。必须在普通backward前安装，回调只读、返回None，在路径结束或finally移除。

[实际Linear.forward:124](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_c2_source_binding_r1_20261106/sources/torch/nn/modules/linear.py:124)原样调用F.linear(input,weight,bias)。冻结[Encoder.forward:101](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106/baseline/s4_models.py:101)把新建的v[...,None]仅交val；其数学输入边只被该Linear消费。原v还走voltage target，故不能用v.grad替代。冻结[losses:22](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106/engineering_training.py:22)把新建h.mean(1)仅交head_coarse；共享h还走head_v，故不能用h.grad替代。只在这两个**既有输入对象**上注册Tensor hook，可观察对应局部dX；在既有线性输出边注册hook可观察G。静态消费证明来自调用点和Linear前端，不来自Python引用计数、storage别名或二维shape。

**attention路径与布局**：原设定training=True/grad_enabled=True、batch_first=True、norm_first=True、dropout0/native SDPA/CKPT0/fp32不变。[activation.py:1257](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_c2_source_binding_r1_20261106/sources/torch/nn/modules/activation.py:1257)与[transformer.py:812](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_c2_source_binding_r1_20261106/sources/torch/nn/modules/transformer.py:812)已因training排除推理fused fastpath；不应为了装hook再改训练/grad/fastpath开关。Transformer的_sa_block在928–935将同一x作Q/K/V、need_weights=False；MHA在activation.py1335–1339把[B,T,E]转为[T,B,E]，保留三者同一性，进入functional packed QKV。

[functional.py:5614](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_c2_source_binding_r1_20261106/sources/torch/nn/functional.py:5614)对[T,B,512]执行packed linear；6410–6418经原SDPA后permute(2,0,1,3).contiguous().view(B*T,E)，out_proj的二维输入因此是token-major，行r=t*B+b。输出恢复[T,B,E]，activation.py1394–1395再转回[B,T,E]。这些是**目标源码与固定设置下的推导**，不是本轮已观察的实际调用。

|调用|逻辑线性输入|展平行r|B64/32行数|
|---|---|---|---:|
|val、pos、FFN linear1/linear2、head_v|[B,208,I]|b*208+t|13312/6656|
|每层packed QKV|[208,B,512]|t*B+b|13312/6656|
|每层attention out_proj|[208*B,512]，源证明来自[T,B,H,D]|t*B+b|13312/6656|
|池化head_coarse|[B,512]|b|64/32|

比较必须按原样本ID规范化为sample-major逻辑次序；B64的前32样本在token-major行中是每个t的b=0..31，绝不是前6656个连续行。实际shape/stride/调用身份或路径与表不符须拒绝，不按shape猜。packed QKV与out_proj走functional.linear；只给out_proj模块装forward hook会漏过调用，后续适配器必须覆盖实际F.linear分派边界。

**KML覆盖与观察设计**：在隔离的新观察适配层中关联canonical参数/调用ID/路径，调用原分派及原forward/backward各一次，返回原对象/原tuple，不替换autograd Function或改公式。所有线性X/Y在forward即做有界只读元数据/哈希；G来自对应输出边hook。native两处局部dX用上述专用输入边；自定义[_LinearFn.backward:179](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106/baseline/kml_ops.py:179)直接返回gx/gw/gb，允许被动返回观察，pos的gx=None因固定输入不需梯度必须如实记录。dW/db与参数映射不丢；完整153参数最终梯度及原输出/loss/v/image梯度仍用原compare。

不新增clone/detach代理输入、extra backward/autograd.grad/GEMM，不以叶合并梯度或未知Node槽位补空。观察缓存只能用于原比较/有界只读哈希，不回送计算图；回调不得把所有X/G对象留在闭包或调用retain_grad造成全层持久副本。优先Tensor hook与实际F.linear适配，避免module backward hook生成新view；任何module forward hook也只能在已经training关闭推理fastpath的相同前提下使用，不能把因插桩改变的路径当原路径。

PREPARATION_REQUIREMENTS.json已给接口、观察点/布局表、注册清理、身份关联、原153覆盖、被动性与失败拒绝要求。909.1553MiB仍只是条件预算；104MiB linear2输入不能整块复制进32MiB哈希工作区，必须流式按已证明逻辑行取字节。实际callback次数/真实dX捕获、峰值/allocator/serializer、KML加载与线程、Linux compute/后代退出均留后续实现与另行授权验证。

原完整B64原mean参考、顺序32+32全局分母/系数1/不额外除2、compare与阈值、原FAIL不变。无需再追native内部Node名称/槽位、C++指令或旧历史缺口来重复本轮设计阻断；若新实现无法满足已批准方法，应交新的具体问题。02尚未获本审核自动实现/执行授权，待协调另发准备任务后再交冻结新包/差异/源SHA/覆盖与保留量说明；不能沿用旧B01夹具标签或14项历史通过冒充新观察器已实现。

本轮只写S01新目录及短状态；0 Torch导入/源码执行/模型/autograd/夹具/DDP/SSH/补源/job/安装提权/Git操作。归档范围见ARCHIVE_SCOPE.json。原规格及方法增补两份分别绑定，原规格与旧FAIL文件均未覆盖；SOURCE_BINDING_REVIEW的静态通过只推荐后续本地准备。
