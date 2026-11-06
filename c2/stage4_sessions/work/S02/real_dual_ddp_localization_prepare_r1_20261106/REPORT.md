# S02 固定首批零更新定位：准备阻断交付

2026-11-06（Asia/Shanghai）。状态 **BLOCKED_PREPARATION_WITH_REASON**，主阻断 **B01_UNBOUND_INSTALLED_NATIVE_VJP**。本轮已交可审核标准库元数据支持包，未交实际取证入口、未发PREPARATION_READY、无数值修复候选。接口先于实现发布，源码/包在本阻断交付后冻结。

## 可行性判断与唯一主阻断

原MINIMAL_EVIDENCE_SPEC SHA=d1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2逐字节保持，29份来源先核SHA；原参考/模型/KML/mean损失/compare/旧FAIL未改。任务卡授权本地代码与标准库夹具，原规格发布时的implementation_authorized=false不被当作本轮本地准备禁令；其执行/训练未授权仍保持，未申请额外权限。

规格要求包括原生分支在内的**实际逐算子dX**。冻结_LinearFn.backward179—188确实返回gx/gw/gb；可设计只读返回/Node post-hook捕获原VJP，返回None不替换梯度，但尚未在C2绑定API。完整val/head_coarse由原F.linear/autograd处理，输出grad_fn可能含view/flatten/native节点，不能仅按名字或假定grad_inputs[1]当该线性输入梯度。

已保存C2 SHARED_RUNTIME_IDENTITIES/FILES只列torch/__init__.py、nn/parallel/distributed.py、NumPy/__init__.py，源正文只留DDP，SHA480213c6…；RUNTIME_CONTRACT绑定Torch2.7.1/R4库，未绑定autograd/graph.py、原生Linear backward图/槽位或MHA前端。只在这些枚举记录内认定缺项，不声称全盘不可恢复。Windows2.7.1的Node.register_hook文档83—107行说明grad_inputs/grad_outputs和returnNone机制；它没有提供C2原生F.linear图/槽位的一一对应。这里只读源码，未导入Torch或在线查验。

尤其v还直接作为电压loss target，共享叶v.grad含target与val两条贡献；不能用它冒充val的局部VJP。仅Tensor.register_hook在共享输入上观察也不足。额外backward/autograd.grad/GEMM、猜AddmmBackward0/slot1或为观察插入改变图/dispatch的新view都未实现。不降低native分支覆盖，因此整体准备阻断；这不宣称被动Node观察普遍不可行。

## 样本轴与算子身份

夹具验证batch-major row=b*208+t与attention token-major row=t*B+b；[13312,512]二维out_proj输入可能已经从token-major flatten，不能取前6656行当首32样本。只有明确layout、实际样本ID次序、shape及来源绑定齐全才允许元数据行映射，缺/重/乱序/未知布局均拒绝。局部Windowsfunctional.py5614及6414—6418支持QKV/out投影token-major机制的设计判断；它不是C2同SHA证明。实际canonical参数/storage-view映射、实际Tensor哈希与dX未实现，相关C2布局证据仍随B01待审核，不能由元数据夹具填平。

## 原数学与零更新契约

未来参考必须直接用冻结engineering_training.losses的两段F.mse_loss mean原式，仅一次backward；training.train_step和B64Reference.advance均会step，禁止调用。本支持代码根本不导入这些模块、不创建optimizer/第二model。顺序32+32以同原64mask的全局电压计数、coarse16384为分母，各本地coarse8192，本地系数/参数grad除数/输入grad除数均1，不套DDP2/2。局部零mask元数据可接受，实际可微零仍待autograd验证。

路径计数夹具只允许A一次forward/backward与B一次顺序路径的两次forward/backward；禁止step/额外收缩/DDP/重复路径，数值停点锁住新计算。真实实现仍须在任何原门槛FAIL后只整理既有值，后续未执行记NOT_RUN。本轮没有任何上述模型路径，不能把夹具计数当真实447原生调用或模型取证。

## 保留量与输出边界

RETENTION_PROOF.json为条件性整数上界：参数151983108bytes，保守计初态、B64参考梯度、顺序累计梯度各一份；两份h/v/coarse与输入梯度/loss、256MiB比较工作区、32MiB流式hash、64MiB输入、64MiB文本/索引、4MiB buffers。合计**953318436bytes（909.1553MiB）**，相对extra1GiB余120423388bytes。最大h的4份float64临时计218103808bytes，小于256MiB设计额度；原compare源码没有改。

证明以逐项串行比较、有限chunk哈希、原64x1x64x64图像及限定buffers/副本为前提。hash chunk/实际Tensor复制与序列化未实现，任何额外保留须重新计账并超限即停。基础模型/原autograd图/库工作区、allocator缓存和真实24GiB峰值未验证，不能把live-byte额度称RSS/HWM保证。远端raw512MiB及text64MiB分别拒绝超额；初始权重/all-layerXG不序列化，原始数据/权重/raw/环境不进返回包。

## 实际compute身份和有界退出设计

DECISIONS_BEFORE_CODE.md先列未来Linux直接已核解释器Popen/start_new_session，无shell；compute在Torch前自行记录PID/PPID/proc start_ticks/boot_id/pgid/session/nativejob/run nonce/exeSHA，监督器核握手PID=直接句柄PID、PPID及parent start身份，并对每个所属后代绑定创建身份/父链。不会按某个Popen句柄回收或之后PID不存在自动推出真实compute退出。

共同起点执行240/清理270/收尾300秒，每路径90服从共同240；只对当前身份仍匹配的所属组/后代TERM后有界KILL/reap。缺actual exit/reap、未知后代/时间/身份不一致均不能PASS。支持包只解析合成proc stat和验证合成身份/事件，**没有进程启动/扫描/信号/回收执行器**；未来实际Linux时序/权限、全部所属后代覆盖及CPU36/TID/库仍NOT_RUN。300秒/CPU36/24GiB没有成为当前作业许可。

## 本轮实际检查

先写14项针对性标准库夹具，再实现最小contracts.py。隔离解释器命令python -I -S -B tests/test_contracts.py完成**14/14通过**；两种CLI夹具（合法LOCAL_FIXTURE/伪ACTUAL拒绝）分别exit0/2。覆盖显式样本轴、重缺样/歧义拒绝、1/1/1与分母、单次计数/禁step、预算、共同deadline/数值停点、proc括号解析/start身份、launcher/job/exe漂移、Popen/迟到PID缺席不能代替exit、残/空/旧SHA/重复key报告拒绝，以及缺C2observer覆盖的B01拒绝。

另核Python3.9 AST/LF与标准库imports、29来源和ZIP逐项SHA。所有结果仅LOCAL_FIXTURE；实际autograd/KML/Linux/数值/完整模型/原64数据均未验证。没有Tiny重跑、张量反序列化、训练/收缩/DDP/SSH/部署/集群/安装/提权或共享Git操作。NOT_RUN.json逐项列未测；各夹具报告禁止冒称实际autograd/KML/Linux通过。

## 阻断后续与冻结交付

最小后续动作先给协调/01审核B01：若有已保存离线的准确C2 Node hook/原生Linear backward节点与槽位/样本布局来源，补其SHA和语义绑定，再设计完整被动observer；如果没有这些记录，明确所需材料和新的窄范围，当前不获取/不导入/不运行验证。具备可审核observer后才可能制作实际取证入口、完成新准备审核；任何实际计算需具体版本/资源/风险交用户另行决定。不能借本支持包或原900秒权限开始作业。

包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\real_dual_ddp_localization_prepare_r1_20261106\package\S02_LOCALIZATION_R1_LOCAL_FIXTURE_BLOCKED.zip；24701bytes/11文件，SHA256=cede0eedc7699b7c94ca4dc97e9adbcbaaf0b4ec51940acf53890c09702c07d4；内容仅LOCAL_FIXTURE支持与规格快照，**不是部署/取证执行包**。SOURCE_SHA256.json为10项新源/契约清单；diff/LOCAL_FIXTURE_SUPPORT.diff只新增helper/tests，不改冻结源。PREPARATION_BLOCKED.json绑定本包/规格/源/检查/报告/能力判断；INTERFACE_READY提供元数据CLI/退出码/收集项，future_compute_cli=null且PREPARATION_READY未发布。

ARCHIVE_FILES.json只列本准备目录和自身两短状态，排除ZIP/原作者原件/环境/数据/权重/raw及其它归档批次；不暂存/提交/推送。S02交明确阻断后待命，不用夹具通过降低规格。
