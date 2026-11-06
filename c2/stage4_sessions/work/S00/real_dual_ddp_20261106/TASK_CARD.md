# 首次真实双域模型同步训练

2026-11-06。用户要求Git归档后开始真实双域模型训练。本卡安排02/07准备、01审核、00满足具体版本门槛后直接唯一执行、08整理结果；无需用户逐个转发就绪文件。本卡只发布任务，尚未提交新job。

## 起点与本轮选择

- Git窗口报告1423文件已普通推送；本协调核本地HEAD与origin/main同为cb342a1f3f9fc0b2bea66f342138f68acc2950e6，实时远端核验依据Git窗口报告，不冒称本协调另做网络核验。
- 原计划STAGE4_C2_PLAN.md第2节/Phase G：最终16域，选全局256—1024并验证学习率/短程收敛；32电极场景建议每域32或checkpoint。原文未规定双域必须64还是128。
- 本轮选择每域32、全局64，保持已有B64工程训练有效批量、原学习率/损失。这是本轮工程约定，不能说成原文指定的双域参数，不静默扩大批量或学习率。
- 已有单域真实Encoder训练和R7固定张量/故障通信结果；没有实际模型DDP结果。R7/2051116的88项Linux与四case通过不替代本轮训练验证，原初始化故障未永久归因。
- 历史B64对B32分块曾严格数值失败，DDP同样会改变GEMM/归约路径。本轮不承诺原门槛能过；失败即停止，不放宽阈值、不换成分块参考来得到PASS。
- 原fp32/KML/native SDPA/CKPT0基线不变。R10/R12不集成，bf16/P1否决保留，compile/HBM不复活。本轮是完整Encoder及两个head的预训练，不宣称Encoder+解码器全任务已训练。

## 冻结训练约定

1. 数据沿用2043445原工程descriptor、16个16_adjacent unit/1600帧、原归一化/seed0初始权重/25批顺序和mask。subject/split UNKNOWN，无val/test，不换case或造正式划分。旧descriptor/暴露账本不改；本轮新建分rank与参考暴露记录。
2. 原manifest SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032；descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6；原工程INTERFACE SHA=8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669。漂移即阻断，不刷新锚点。
3. 原loader/数学见S02/overnight_engineering_20261105/。模型/比较器/原后端参考见S02/round12_dw_output_tiles_20261106/{baseline/,tests/check_equivalence.py,diagnostic_common.py,engineering_training.py,REFERENCE_FIRST5.json,REFERENCE_EPOCH25.json}，只用baseline，不加载candidate。baseline/s4_models.py SHA=9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2，baseline/kml_ops.py SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26；两reference SHA分别2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8、572ce966e3de8b54ff234755a6595a0a730dd0920fcd371a234cc7798f641444。发布前实际重核，不只抄本文。
4. 每个原全局64批按原顺序前32给rank0、后32给rank1，并集恰为原64，无交集/补齐/重复。全局frame IDs和mask/hash对齐原参考。保留原模型初始化后的mask RNG流，隔离DDP构造、额外参考初始化、恢复探针对它的影响；不能只重新seed产生另一套mask。
5. 原37995777参数Encoder，原注意力/head，原电压masked MSE + coarse MSE；AdamW lr1e-4/betas(.9,.999)/eps1e-8/weight_decay .01。无累积/scheduler/混合精度。两个rank共同更新一个模型，不把独立进程吞吐相加。
6. 使用真实torch.distributed/Gloo/DDP，完整预训练forward包含Encoder、head_v/head_coarse及loss所需计算。不得经ddp.module绕过训练forward，不遗漏参数。按当前已装Torch2.7.1实现核reducer语义和一套固定bucket配置，不搜索调参。
7. 分别跨rank统计两个loss分量的元素数。默认DDP梯度取平均时，本地反向loss为world_size×(本地电压误差平方和/全局masked数 + 本地coarse误差平方和/全局coarse元素数)。归约脱离梯度的分母/日志量，不错误依赖非autograd collective传播loss梯度，不无权平均本地mean。全局零分母失败，本地零mask保持可微零项，不重采样/加epsilon。日志用全局sum/全局分母，不把乘2的局部反向loss当全局loss。
8. 前5个全局批在rank0保留原完整B64参考模型/AdamW，与真实分片DDP连续配对。原compare函数/类别/阈值逐字节保留，比较原覆盖的输出、loss分量/total、输入梯度、全部参数梯度/更新后参数/delta、AdamW step/一二矩和buffers；wrapper名字映射回原键，不丢参数。DDP参数梯度已平均不能再除2；输入梯度未被DDP平均，按上述反向缩放除world_size后对照全局目标。参考不能改成B32x2。
9. 单一job内执行：前5步任一门槛失败立即停止后续；全过才在同一DDP模型/AdamW状态接着完成第6—25步，参考做5步后释放。上限25次全局更新、5次B64参考，物理rank更新最多2×25+5=55次。1600训练独特帧和参考额外320观察帧分开记，后者不算吞吐新增样本。早停只报实际完成/可能暴露范围。
10. 每步核两rank参数/AdamW状态一致（原名/张量字节hash，不能比较含rank元数据的整个checkpoint文件），step/cursor与梯度有限性正确。最终保存原Encoder/AdamW、各rank RNG及独立mask RNG、游标/归一化/源身份，零额外optimizer更新做恢复验证。只有实际检查过才称通过。checkpoint留远端，仅回路径/bytes/SHA。

## 资源、退出与结论范围

- 同节点两个真实NUMA域，各38物理核分配/36实际/该域末2核预留，总76/72/4。actual IDs来自当前分配。DDR总24576MB且limit同值、exclusive、HBM0。不够则停，不扩申请/缩批/改模型。
- 单job总900秒，从job同一起点计算，所有前置与应用到840秒截止，清理30/收尾30；不能逐阶段重置预算。新训练PG timeout固定120秒，原R7固定探针pg5/case30不改、不套用到真实训练。剩余外层预算优先；超时如实FAIL/INCOMPLETE，不少做步后报PASS。
- parent/两worker导入Torch前核当前job身份与绑定，双方就绪后初始化PG。实际Torch intra-op36，相关TID非空mask属于本域selected36；OMP36/MKL36/OpenBLAS1/cores/close。复用已核R4环境，核真实Torch/NumPy、KML/OpenMP/shim身份与实际调用，无native静默回退。训练/参考计数分列，不直接套旧B64的149预期到所有新路径。
- 00提交前核实时队列/本系列唯一提交marker，旧job终态或本地无记录不能证明远端无活动。任一rank失败监督器及时停止/回收本任务双方及后代，收调度终态/PID/清理证据。禁止无界barrier/join或操作其它任务job/PID。
- 不新增故障注入、重复旧四case、安装依赖、提权取栈或增加实验矩阵。必要本地检查只覆盖本轮新数学/分片/退出，平台skip与真实Linux/C2结果分开。
- 前5步含参考诊断时间和后20步分别记；记录训练调用内同步/等待、最慢rank、诊断/壁钟和RSS/HWM范围。参考共存阶段HWM单列，不称纯DDP训练峰值。无profiler或为计时另跑大矩阵，无同job同负载单域25步性能对照，本轮不算提速/扩展效率/稳态收益，不额外增加此对照。
- READY/审核/完成绑定具体源/包/数据/config/本卡SHA，发布后冻结。复用R7原子rank报告方式，缺/空/残/旧身份拒绝。发布前可最小修正准备问题；实际job失败不重提、不扩预算/放宽门槛。

## S02：分片与完整B64参考

**本轮目标**：交固定数据/掩码分片接口，原完整B64五步参考及比较器适配，不重新优化KML。

**参考文件**：自己的短状态/摘要、本卡、overnight_engineering_20261105/{INTERFACE.json,engineering_data.py,engineering_training.py,train_engineering.py}、R12 baseline/原比较器/两reference。旧失败只按疑点展开。

**完成标准**：仅写work/S02/real_dual_ddp_reference_20261106/及自身状态。先发布INTERFACE_READY.json明确供07使用的函数/参数/返回/名字映射/共享baseline路径/RNG规则，再交REFERENCE_READY.json及冻结包/来源清单/最小diff/实际本地证据/归档清单。复用原loader和数学，旧engineering INTERFACE独立保留作data_gate。核25批并集/不重样、归一化、mask/原参考、原compare与全部参数覆盖；无本地Torch/数据则明确NOT_RUN。及时释放参考快照，不保留所有步全模型副本。无SSH/job/共享Git操作。

## S07：真实两rank训练入口

**本轮目标**：实现本卡完整Encoder DDP训练，接02只读参考，前5门槛通过后接着25步，交冻结新包。

**参考文件**：自己的短状态/摘要、本卡、S07_DDP.md、当前已装Torch DDP实现/官方接口、02新READY；round7_atomic_reports_20261106仅复用原子发布/job-CPU/进程所有权小组件。

**完成标准**：仅写work/S07/real_dual_ddp_20261106/及自身状态，不改R7。先发INTERFACE_READY.json供00准备；02冻结且必要检查完成后发TRAINING_READY.json绑定唯一参考包/数据/契约、训练包/源清单/命令/退出码/收集项。单一baseline导入路径，不出现不同kml_ops实例或R12 candidate。先写针对性检查再实现：不等masked数的全局分母与错误local mean反例、分片重/缺样拒绝、RNG隔离、DDP图/head/参数覆盖、输入梯度缩放、单rank失败有界退出。已有环境能跑真实小DDP则跑，否则如实NOT_RUN；不装依赖，不把替身/Windows当C2结果。检查实际API不符则发布前阻断，不代提交job。

## S00：新部署与唯一条件执行

**本轮目标**：按07接口并行准备；01最终同SHA通过后直接唯一执行到终态，不等用户另转放行。

**参考文件**：自己的短状态/摘要、本卡、02/07本轮READY、原R4环境/2043445数据、R7资源/所属进程清理仅参考；01本轮S01_REVIEW.json。

**完成标准**：仅写work/S00/real_dual_ddp_20261106/及自身状态，远端新REAL_DUAL_DDP_<唯一时间>/。核实际队列/资源/descriptor/16NPZ-sidecar/库与新接口env连线，LF/Linux bash-n及必要无训练检查后发布S00_DEPLOYMENT_READY.json绑定新外包、02/07实包、本卡/资源/阶段/清理。等S01/real_dual_ddp_review_20261106/S01_REVIEW.json为PASS_FOR_REAL_DUAL_DDP、review_complete=true且全部SHA相符，提交前再去重，才唯一dsub。现场核环境/CPU→前5门槛→同状态接着25步→保存/零额外更新恢复。收两rank原结果/metrics/失败项/事件/帧mask与暴露/同步/CPU库/调度/退出/清理和远端权重索引，发RUN_COMPLETE.json（含精确analysis_inputs）或失败交接。失败不补跑/重试，旧R7 PASS不作本轮放行。

## S01：独立数学与版本审核

**本轮目标**：核新DDP/参考/部署，给唯一job具体版本结论；随后复核实际结果，不代改候选。

**参考文件**：自己的短状态/摘要、本卡、S07_DDP.md、02/07新READY/diff/必要实现与检查、00新S00_DEPLOYMENT_READY；原比较器/数据协议只核相关不变项。

**完成标准**：仅写work/S01/real_dual_ddp_review_20261106/及自身状态。重点核完整DDP图、真实各32/全局64、全局分母/DDP平均系数/输入梯度、全部参数与AdamW映射、原compare不变、完整B64参考、mask/归一化/真实库与共享截止。不能只看总loss或豁免历史数值风险。最终S01_REVIEW.json给PASS_FOR_REAL_DUAL_DDP或FAIL/BLOCKED、review_complete及原因，逐项绑定代码/参考/外包/数据/config/本卡/资源与更新上限；含糊“原则通过”不能放行。只为具体疑点补针对性检查，不重跑旧大矩阵。收到实际RUN_COMPLETE后依analysis_inputs核真实步数/门槛/同步/恢复/清理，不把exit0当全部通过。

## S08：训练摘要

**本轮目标**：按新接口准备结果核对；00结束后整理实际训练/门槛/时间，不阻塞部署前置。

**参考文件**：自己的短状态/摘要、本卡、07新结果接口、00本轮RUN_COMPLETE.analysis_inputs、01本轮实际复核。

**完成标准**：仅写work/S08/real_dual_ddp_summary_20261106/及自身状态。优先复用现有工具，只补必要字段，不建通用平台。区分全局25/物理rank50/参考5更新，独特训练帧/累计曝光/分片/实际loss与门槛/同步/恢复/耗时与清理。失败后阶段记NOT_RUN；无同job单域对照则提速字段NOT_MEASURED，不拿旧节点单域秒数算加速比。最终绑定00实际结果；等待中只称准备完成，夹具不当真实结果。

## 固定交接与等待

各窗口改代码前核自己最新文件/来源SHA。本卡不代更新作者状态来冒充启动。各自新轮目录与自身短状态可写，冻结历史不覆盖，不碰共享Git暂存。02/07先发接口让下游并行，固定READY直连；缺依赖先做独立准备，可有界等候最多90分钟、单次不超60秒，到期记WAITING/缺项，不假称已执行。已提交job由00追踪原job到终态或明确交接活动ID，不因等候到期重提。

结束更新SESSION_STATUS.md（建议40行内）和ROUND_DELTA.md（六行），只向协调汇报本轮变化/证据。核验通过后提醒唯一Git窗口精确归档，各任务不自动commit/push。03/04/05/06保持原处置，本轮不占集群排期。
