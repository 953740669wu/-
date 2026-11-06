# S02首次真实双域：固定分片与完整B64参考交付

2026-11-06；S02本轮准备完成，REFERENCE_READY冻结供S07/01/00直接读取。只有S02新目录及自己的短状态可写，未SSH、提交job或操作Git。R10/R12已关闭不集成，未重新优化KML。

先发布INTERFACE_READY.json（SHA=974c7c1f2fd1cd21b2a1e94be3a72fd21686e61575450cdf608249e92f313544），再发布REFERENCE_READY.json。接口明确函数/参数/返回、canonical名字及单一共享baseline路径；完整用法和本地命令见CONSUMER_GUIDE.md。S07负责真实DDP graph/全局分母/PG/CPU/共享截止/所属进程清理及保存恢复，S00仍须等S01具体版本最终审核。

## 实现及原数学

12份冻结复用文件（原baseline两文件、compare、loader/独立旧engineering接口、训练数学、诊断/CPU契约及两reference等）字节不变；原模型37995777参数/153个名字、两个head、native SDPA/CKPT0/fp32、AdamW lr1e-4/betas(.9,.999)/eps1e-8/wd.01和原compare阈值不改。仅新dual_reference.py及针对性tests，最小新增diff见diff/NEW_REFERENCE_ADAPTER.patch。源码来源/SHA见evidence/FROZEN_SOURCES.json和SOURCE_SHA256.json。

plan固定原25x64 shuffle，每批前32/后32无交集不补齐；shard为v/image建立独立叶子，保留角度/belt及mask次序。原train-only absmax loader和原descriptor/manifest/interface锚点不变，新分rank账本必须为新绝对路径且拒绝旧两账本。实际数组/归一化读取验证留C2，未用合成数据冒充实际统计。

initialize保留原seed0/完整Encoder/权重SHA门禁；DDP构造前捕获原post-init Torch状态，用私有Generator.set_state产生全部25个原mask并逐批核原SHA。额外参考构造及其步骤保存/恢复调用者Torch/Python/NumPy RNG；不重seed生成另一套mask。私有stream状态含next_step/post_init/generator，恢复核其对应关系，不消耗process RNG。

B64Reference只在rank0保留原完整B64模型/AdamW及一份原init快照，最多一个pending step；严格1..5连续更新，不改成B32x2。原训练mean算术、原historical loss门禁和compare函数原样调用；比较h/v/coarse、全部loss、两类输入梯度、153个原名字的grad/param/自init delta/AdamW step及一二矩/buffers，严格核优化器覆盖与超参数。DDP参数梯度已经平均，不再除2；raw拼接输入梯度只在适配器除2。每步成功后释放pending/参考grad，第5步close立即释放参考模型/opt/init，不留五份模型副本。真实forward必须经S07 ddp(...)包括双head；ddp.module.encoder只供读取/对照。

## 本轮实际本地证据与失败边界

7项最终helper检查通过：25批并集/次序及错误分片拒绝；原完整初始化153名字/优化器覆盖和双head、25个原mask与外部RNG隔离/恢复；leaf分片；原compare字节身份及负例；tiny模型连续5步原AdamW/原比较190项max_abs=relative=0；错误输入grad缩放/多余参数拒绝；数据锚点/旧ledger拒绝。另核25份原steps元数据SHA/帧mask身份、Python3.9 AST/LF、框架导入前可导入、ZIP内容和所有冻结来源。没有完整Encoder forward/真实训练或旧数值矩阵重跑。

首次本地检查在Windows原seed0权重SHA守卫拒绝而停止（reference_tests_first.log）；只读原始模型诊断证实37995777参数但SHA=411aa36f4d120512d7de6e6646733ea898a99531144cac84688a9ef1c2a567dd，不同于冻结C2 2543d05f25883b654141cbc5dc1bb093906e3b360f11ec9f5e87cb4f8bad76b5，第一mask却相同。未给差异做未经验证的原因归因。最终tests把该Windows差异明确作为拒绝负例，并独立验证原mask/其它helper；没有改初始化守卫、阈值或参考权重锚点。evidence/WINDOWS_INITIALIZATION_DIAGNOSTIC.json保留原expected/actual。actual C2/R4初始化必须仍匹配原SHA，漂移就停止，不能拿本地helper通过放行真实训练。此处是C2待核前置，不伪称Windows权重门槛通过。

已有本地环境为E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe（Torch2.7.1+cpu/NumPy2.2.6，local2线程），无新安装；S07若需检查可复用。首次拒绝日志、最终7项日志和tiny190指标均保留。真实NPZ/归一化、C2 init、实际KML、完整B64五步及DDP门槛均NOT_RUN_BY_S02，历史B64/B32严格失败风险保留。数据subject/split UNKNOWN、无val/test；小模型数学不能替代实际DDP/科学或性能接受。

## 交付与上下游

包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\real_dual_ddp_reference_20261106\package\S02_REAL_DUAL_DDP_REFERENCE.zip，62170bytes/18文件；SHA256=df7275b06d8ee59cd88c0d17c04b0b64f63605ffa1c4410d3d02307ce848eec5。
SOURCE_SHA256.json包含17源条目，SHA256=6b9cd186d27a5130f22cd2e58a2c6cb231be31c70d5df98dce4c40e92008b757。REFERENCE_READY绑定接口/源/包/契约卡/比较器/数据锚点/检查/报告/导入方式。所有源码/包在READY后冻结，阶段证据追加不改冻结源。ARCHIVE_FILES.json为本轮精确待归档范围，排除ZIP/真实数据/权重/环境；无暂存/commit/push。

S07直接按固定REFERENCE_READY消费；02无等待依赖。资源/工作量仍按本卡：各32/全局64、两域各实际36，总76分配72实际/留4，DDR总24GiB/exclusive/HBM0，总900秒共享840+30+30，PG120；前5原数值门槛全过才同一DDP/AdamW接续至25，最多55物理更新，不缩步/放宽或重提。02不代做提交/最终审核。
