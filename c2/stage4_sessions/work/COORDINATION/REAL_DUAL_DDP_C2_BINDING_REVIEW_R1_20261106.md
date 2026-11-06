# 目标C2补源后的API、专用输入边与布局独立静态审核R1

状态：交原01窗口；任务卡发布，不等于已接收/启动。00补源已完成，不重复采集；02仍待命。本卡仅授权本地文件/哈希/静态审核与审核文档，不授权实现或运行。

## 本轮目标

使用新增的实际C2源码，结合冻结模型/KML调用点及协调已明确的方法增补，回答B01的设计证据阻断是否可解除，是否足以让02进入新的本地观察器准备。不得只重复上一轮“缺六份源码”的结论，也不得将源码齐全等同真实autograd、数值、内存或退出验证通过。

## 参考文件

工作根：E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/。

1. 自己与S00的SESSION_STATUS.md、ROUND_DELTA.md。
2. S00/real_dual_ddp_c2_source_binding_r1_20261106/SOURCE_BINDING_PACKET.json；SHA256=b0a0c1e11fb0ba26987f69cfc13b24eb15dc97820f141cfa835857af56edd93f。关联SOURCE_SHA256.json、IDENTITY_MANIFEST.json、INPUT_BINDINGS.json、NOT_RUN.json及必要原始导出证据。
3. 同目录sources/torch/下六份原文字节：_tensor.py、nn/modules/linear.py、nn/modules/activation.py、nn/modules/transformer.py、nn/functional.py、version.py。
4. COORDINATION/S00_C2_SOURCE_BINDING_RECEIPT_20261106.json（协调核49文件、六源432651bytes及原始导出字节/冻结锚）。核心库仅导出身份元数据，本次首次记录，不回溯声称旧job核心库一致。
5. COORDINATION/REAL_DUAL_DDP_C2_SOURCE_BINDING_R1_20261106.md（SHA256=528027e6e639a6f389357aafdda9179d22f2f9e3b4a288902d88ea11cfa0c04f），其中方法增补已由协调明确接受，不再把“方法尚未批准”作为旧阻断机械重复。
6. S01/real_dual_ddp_preparation_blocker_review_20261106/BLOCKER_REVIEW.json、MISSING_BINDING_SPEC.json；原real_dual_ddp_proposal_review_20261106/MINIMAL_EVIDENCE_SPEC.json及其冻结模型/KML调用点引用；必要时读02准备契约与保留量设计。原规格与旧FAIL文件不改。

## 完成标准

- 先核包与必要依赖SHA/大小；目标前端来源、解释器/包根关联、冻结Python和__init__锚及新核心库身份分别记录。若缺证据或漂移，给精确路径/字段与影响，不刷新锚、不联网取源。
- 对目标Tensor.register_hook的非叶输入/输出边语义、被动return None、注册/移除方法给出处；结合实际nn.Linear.forward及冻结调用点，分别证明或否定val原有v[...,None]边、head_coarse原有h.mean(1)边仅由对应Linear消费。共享v/h叶梯度、Python引用计数/存储别名不能代替消费关系证明。
- 给出后续实现可用的被动观察设计，区分数学可观测性与实际代码尚未实现：G、局部dX、KML返回gx/gw/gb覆盖；不新增代理/clone/detach、不改变图/算子/梯度、不硬编码未知Node槽位、不额外收缩或反向。指出hook安装是否影响所需路径/fastpath条件；不能仅凭API存在判放行。
- 依据目标activation/transformer/functional源码与冻结训练/grad/batch_first等设置，明确attention实际应走路径、out_proj展平/转置的逻辑样本映射。提供源码路径/行号和必要形状推导；不能从二维shape直接猜首后32行，不能把静态推导标成已观察的运行路径。
- 原全153参数覆盖、完整B64原mean、顺序32+32全局分母/不额外除2、原阈值/FAIL仍保持。909.1553MiB只作条件预算；104MiB输入流式哈希与32MiB工作区约束、真实callback覆盖/峰值/退出仍留后续实现及实际验证，不在本轮声称通过。
- 给逐项结论：来源身份、hook API、val专用边、head_coarse专用边、attention布局、KML观察、待实现/待运行边界。结论选择ACCEPT_FOR_LOCAL_PREPARATION或BLOCKED_WITH_SPECIFIC_GAP；前者只表示静态证据允许协调另派02准备，不发布PREPARATION_READY，也不是数值或执行PASS。
- 若通过，给02一份具体接口/观察点/布局表和完成条件（PREPARATION_REQUIREMENTS.json），避免02重复探索已核问题；若阻断，给一个最小、具体的剩余缺项和获得方式/所需权限，不泛化索要整套环境，不自行补源或运行。

## 交付与停点

仅写S01/real_dual_ddp_c2_binding_review_r1_20261106/及自身短状态/六行摘要。交SOURCE_BINDING_REVIEW.json、PREPARATION_REQUIREMENTS.json（通过时）或REMAINING_GAP.json（阻断时）、简短REPORT.md、精确归档清单。审核JSON应绑定本次包SHA和方法增补SHA，区分review_complete、static_preparation_recommended与implementation/execution/training_authorized（后三项本轮均false）。返回六行摘要及SOURCE_BINDING_REVIEW.json绝对路径。

本轮不导入Torch、不执行目标源码/模型/autograd/夹具/DDP、不SSH/联网/新取源、不提交集群job、不安装提权、不改作者原件、不做共享Git操作。未决问题据已有静态材料明确化，不通过额外实验补证。

00/02/07/08及Git当前待命。协调收到01结论后决定02新的本地准备任务或最小缺项处理，并合并已闭合材料生成下一批精确Git清单；本卡不授权任何后续动作自动启动。
