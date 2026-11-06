# C2目标源码绑定包：只读定向补源R1

状态：总协调已发布，交原00窗口；未确认接收/启动。用户保持“不追加集群作业”，本卡不授权任何模型计算。原01已完成ACCEPT_BLOCKED，02不再重复缺源准备。

## 本轮目标与授权范围

由原00利用既有R4环境访问方式，交付01指定的六份已安装C2前端源码及身份清单。先检查自己是否已有确切目标离线原件；若没有，允许一次有界、只读SSH/文件导出。此次只读补源由总协调在既有推进职责内明确安排；01前轮“未获补源授权”的描述仅指其当时轮次，不能当成已经取源。不得启动计算节点、提交job、导入Torch/模型/autograd或运行训练/夹具。

## 参考文件

以 E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/ 为根：

- S00/SESSION_STATUS.md、ROUND_DELTA.md。
- S01/real_dual_ddp_preparation_blocker_review_20261106/BLOCKER_REVIEW.json（SHA256 a3cd69328af79dfb4d4e7cbc658455b5545d6024c1f870dcc9e7d3bdedd22d82）。
- 同目录MISSING_BINDING_SPEC.json（SHA256 d9457578a5a31a457fd65a87174f1066bbc77427f4d3469c05fe5be767d6cc9a）。
- S00/real_dual_ddp_20261106/RUNTIME_CONTRACT.json和evidence/SHARED_RUNTIME_IDENTITIES.json，严格复用目标解释器/包根及冻结SHA。
- COORDINATION/S01_PREPARATION_BLOCKER_ACCEPTANCE_20261106.json。

## 精确取源与约束

目标根：/home/share/songzhenlong/eitfm/sw/torch_kml/torch/。
仅取六份文本原字节：_tensor.py、nn/modules/linear.py、nn/modules/activation.py、nn/modules/transformer.py、nn/functional.py、version.py。

同时记录采集主机/时间、路径/realpath、bytes/SHA256、包根与原R4解释器的关联；复核已冻结__init__.py SHA256=9801e75447c7f585545f989f8a21940b60e0c4cc888effb2f08e739664b4b904。按01规格记录实际_C扩展及native CPU/autograd相关核心库的路径/realpath/bytes/SHA及现成ELF/build标识；只交元数据，不下载二进制，不运行库或导入框架。只在已知包根/_C*和lib目录做定向文件识别，不全盘扫描、不递归扩大环境查找、不取上游替代版；敏感登录信息不入交付。

六份源码文本合计最多2MiB；按01规格文件读取/哈希/导出共同截止60秒，不重置各文件期限。若远端需要临时导出脚本，仅写00自有临时目录；不改运行时、原部署包、配置或共享源码。缺文件、权限失败、身份漂移、超字节或超时即留部分清单并终止，不重试、安装、提权或更换环境。普通shell/标准库只读文件及哈希允许；不得为确定身份额外导入Torch。

## 方法澄清的协调决定

接受01提出的“现有专用非叶输入边”作为后续设计可审查方法，原MINIMAL_EVIDENCE_SPEC原字节不改，本卡作为显式增补：仅当目标源码与冻结调用点证明该实际输入边仅被一个Linear消费时，可用目标支持的被动hook观察其数学局部dX；仍完整保留dX覆盖和原比较阈值。val必须是既存v[...,None]边；head_coarse必须是既存h.mean(1)边；共享v/h叶梯度不能替代。

禁止新增clone/detach/代理输入、修改图/算子、猜Node槽位、额外反向/GEMM、修改hook梯度。G与KML返回观察、attention样本映射仍需证据。该方法不提供native内部Node名称/槽位或确切内核指令定位结论；不减少数学局部dX覆盖。独占消费或目标API不能证明就继续BLOCKED。

此澄清只确定未来审核可接受的方法，不授权00/02实现、模型执行或发布READY；源码包返回后再由01独立静态核目标/API/布局与调用点，协调据其结果决定是否给02新的本地实现任务。原规范包与旧FAIL永久保留。

## 完成标准与交付

仅写S00/real_dual_ddp_c2_source_binding_r1_20261106/及自己的短状态/六行摘要。交六份原文、SOURCE_BINDING_PACKET.json、SOURCE_SHA256.json、NOT_RUN.json、简短REPORT.md及精确ARCHIVE_FILES.json；首个JSON至少包含状态、目标/采集来源、逐文件身份、本地保存路径、冻结锚核对、缺项/超限原因和实际操作计数。所有原文字节与清单核SHA。完整记SOURCE_PACKET_COMPLETE_FOR_REVIEW，不记PREPARATION_READY；部分/漂移记BLOCKED_SOURCE_PACKET。

NOT_RUN应明确Torch导入、模型、autograd、DDP、夹具、计算job、训练更新均0；如使用SSH如实记录次数，不能记全零。返回六行摘要及SOURCE_BINDING_PACKET.json绝对路径。无共享Git操作、无自动部署和后续计算。

后续：用户将00交付转协调；达到完整且冻结身份吻合才给原01静态复核，缺项先据具体原因处理，不重复派02。02/07/08待命；01当前审核已完成。新接受阻断档案与本轮协调记录留下一批精确归档，Git当前待命，旧37/99/268批不改。
