# 总协调交接：首次真实双域模型训练

快照：2026-11-06 16:56，Asia/Shanghai。工作区：`E:\eitfm_c2_stages2-4_2026-11-03`，PowerShell。本文件是新总协调的入口，后续变化以作者最新状态和必要原件为准，不要求搬运聊天历史。

## 先做什么

你接替总协调，继续推进既有阶段四独立任务，不重新规划整项目，不直接接管作者实现。用户最近要求：已推送Git，开始真实双域模型训练；保留00/01/02/07/08独立会话，按固定状态文件衔接。

依次读取本文件、同目录`SESSION_STATUS.md`/`ROUND_DELTA.md`/`STATUS.md`、`REAL_DUAL_DOMAIN_DDP_START_20261106.md`。再读本轮00/01/02/07/08的最新短状态/变化摘要。日常不通读完整报告；验收、状态矛盾或具体疑点才打开相关代码/证据。

当前第一动作：核本轮02参考、07训练包、00部署与01审核进度，继续下述依赖链，不重新分派相同任务或重提作业。只有用户要求启动新聊天时才创建聊天；本次用户自行新开总协调会话，现有任务会话保留。

## 截至快照的实际状态

| 项目 | 已核到什么 | 不能据此推断什么 |
|---|---|---|
| 总协调 | 新任务卡已写好、已给用户五窗口通用提示词 | 不能据此认为用户已全部转发、各任务全部开工 |
| S01 | 新目录`real_dual_ddp_review_20261106/REVIEW_PROGRESS.json`已出现，decision=BLOCKED、review_complete=false，等待02/07/00 | 不是最终S01_REVIEW，不可放行job；作者根状态仍是上一轮，不当作01未开工 |
| S02/S07/S00/S08 | 快照检查各自本轮新目录尚未出现，根摘要仍为上轮完成 | 不能声称已有本轮READY或实际训练；接班时可能已更新，必须刷新 |
| 集群 | S00上一轮摘要记2051116终态、所属PID回收、无活动S00 job | 本窗口未查实时远端队列，不证明此刻没有新job；提交前由00核队列/marker |
| 本协调进程 | 本轮只有已结束的本地读写/核验，没有启动SSH、训练、后台监视或作业 | 不代替其它会话的进程状态 |
| Git | 本地HEAD与origin/main均`cb342a1f3f9fc0b2bea66f342138f68acc2950e6`，暂存空；Git窗口报告1423文件普通推送GitHub成功并实时核远端 | 本协调未另联网核远端；本轮新卡/交接/状态更新尚未提交，接班须核实际Git状态 |

01预审记录的依赖等待期限为2026-11-06 18:26:05+08:00；这是作者本轮有界等待期限，过期不代表许可或作业失败，也不能据此假定后台一直监控。接班看最新记录，不无条件重置等待。

## 当前任务与固定交接路径

所有下述相对路径以`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\`为根。

| 窗口 | 本轮目标/目录 | 关键交接 |
|---|---|---|
| 02 | 数据分片、mask/RNG、原完整B64参考；`S02/real_dual_ddp_reference_20261106/` | 先`INTERFACE_READY.json`，后`REFERENCE_READY.json`与冻结包 |
| 07 | 完整Encoder真实两rank DDP；`S07/real_dual_ddp_20261106/` | 先`INTERFACE_READY.json`，后`TRAINING_READY.json`绑定02冻结参考 |
| 00 | 新部署/唯一实际job；`S00/real_dual_ddp_20261106/` | `S00_DEPLOYMENT_READY.json`；最终`RUN_COMPLETE.json`及精确`analysis_inputs`，失败也完整交接 |
| 01 | 数学/代码/参考/部署独立审核；`S01/real_dual_ddp_review_20261106/` | 最终`S01_REVIEW.json`必须`PASS_FOR_REAL_DUAL_DDP`、`review_complete=true`且具体SHA相符；运行后还须复核结果 |
| 08 | 结果统计；`S08/real_dual_ddp_summary_20261106/` | 先准备，实际结果到后摘要，不阻塞部署前置 |

依赖：02参考→07冻结包→00新部署与01最终审核→00唯一job；接口可先发布供下游并行准备，08并行准备。00满足最终同SHA审核后可以直接执行，无需让用户再次中转放行。旧R7审核不能作为本轮审核。

本轮任务卡：`COORDINATION/REAL_DUAL_DOMAIN_DDP_START_20261106.md`，本快照SHA256=`ebabda929df06e0c1366563af0d16ac360c0fdf3cc16b330f3bf2804a088a1ec`。细节以该卡为准，不仅凭本摘要实现。已发布READY绑定该卡后，不静默改契约；需要改则新版本并重核依赖。

## 本轮训练约定，不能丢失

- **模型/数据**：完整Encoder及两个head的预训练，原37995777参数；fp32/KML/native SDPA/CKPT0，原AdamW/学习率/mean损失。仍用2043445原16个16_adjacent unit、1600帧、25个原全局批、原顺序/mask/归一化。不是Encoder+解码器完整任务。
- **批量**：每域32、全局64，保持已有B64有效批量。原计划第2节/Phase G的最终目标是16域全局256—1024并验证学习率，32电极建议每域32；原文没有规定双域64还是128。本轮B64是协调给出的工程选择，已向用户解释，不把它说成原文硬性要求，不静默扩大到128/512。
- **实际DDP**：两个rank处理不相交的32帧，共同一次全局更新，不能把两个独立进程训练计时相加。DDP forward覆盖Encoder与两个head；masked loss按全局元素数加权，考虑DDP梯度平均。输入梯度与参数梯度的缩放不同，细节见任务卡。
- **先5后25**：rank0同job保留完整B64参考，前5步比较原覆盖的输出/loss/输入梯度/全部参数梯度、参数/delta及AdamW状态；全部通过才在同一DDP/AdamW状态接续至25步。最多DDP全局25、参考5、物理rank更新55。参考额外320观察帧单列，不算新增训练独特帧。
- **数值风险**：历史B64与B32分块确有严格失败，DDP改变GEMM/归约路径也可能失败。原compare/类别/阈值保持，不能换B32x2参考/放宽门槛来通过。数值失败停后续训练/性能接受，不自动重试或追加矩阵。
- **资源**：同节点2NUMA域，每域38分配/36实际/末2预留，总76/72/4；DDR总24576MB且limit同值，exclusive/HBM0。单job900秒共享起点，应用至840/清理30/收尾30；训练PG120秒属于新协议，不套旧R7 pg5/case30。
- **结论**：工程训练无正式val/test、subject/split UNKNOWN，case不是已证明subject。不称科学效果、泛化或生产接受。本轮无同job同负载完整单域性能对照，提速/扩展效率=NOT_MEASURED，不能拿旧不同主机秒数算提速。

## 数据与来源入口

- 原语料：`/home/share/songzhenlong/eitfm/corpus_shape_20261102/`；manifest SHA=`bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032`，14300 unit/143万pairs/143 case。旧11900版本不能当当前冻结版本；不再以“找不到正式划分”为本工程路径的阻断，因为用户已明确同意暂时没有正式划分推进。
- 原descriptor：`/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json`，SHA=`b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6`。选中s0285/s0593各8unit共1600帧；不要扩样。运行前由00核当前文件与NPZ/sidecar身份。
- 原loader/数学：`S02/overnight_engineering_20261105/`；原模型/比较器：`S02/round12_dw_output_tiles_20261106/baseline/`与`tests/check_equivalence.py`、两REFERENCE文件。只加载baseline，不加载R12 candidate。全部必要hash及RNG/规范细节见本轮卡。
- 已验证R4运行环境由00保持；Torch2.7.1+cpu/NumPy1.26.4，KML/OpenMP/shim实际身份与调用、Linux CPU36证据必须现场核，不能以Windows测试替代。不要为接班重复环境矩阵或安装依赖。

## 只保留这些历史结论

| 路线/作业 | 结论 | 必要证据入口（有疑点才读） |
|---|---|---|
| 单域真实训练2043445 | 1600帧/25步和零额外更新恢复通过；工程执行证据 | `S00/overnight_engineering_20261105/`及对应RUN_COMPLETE |
| R10 | view复用未省实际copy，低收益关闭 | S02最新状态引用的原R10记录 |
| R11/2049454 | 447真实KML调用诊断，dW主导；不是稳态加速 | 需要重新选优化点才按S02/08原摘要进入 |
| R12/2049894 | strict3895差0，但后20步中位4.510239/4.628061秒，候选本次慢2.6123%；CLOSED_NO_TRAINING_GAIN，不集成/换tile | `COORDINATION/JOB2049894_R12_NO_GAIN_REVIEW_20261106.json`；`S02/round12_closeout_20261106/` |
| S07 R6/2050433 | crash时rank0空JSON导致失败，后两case未跑；失败原件保留 | 原R6 RUN_COMPLETE，必要时沿analysis_inputs |
| S07 R7/2051116 | 原子rank发布修复；88 Linux零skip、同job原normal/crash/collective-timeout/watchdog协议通过；进程已清理 | `S00/s07_r7_atomic_20261106/RUN_COMPLETE.json`；`COORDINATION/JOB2051116_S07_R7_PROTOCOL_REVIEW_20261106.json` |

R7完整取栈仍false：Python计时合法提前取消，kernel stack两字段权限拒绝；不能称原初始化卡住永久修复或已验证模型DDP。S03缺libubsan、S04 P1_REJECTED_CLOSED、S05本地C ABI准备、S06默认g++不可用保持原处置；当前主线不自动重启这些任务。

## 协调工作方式与权限

1. 用户偏好中文、简短固定交接。每轮分派写清**本轮目标、参考文件、完成标准**；结束只收六行变化摘要，作者维护自己的SESSION_STATUS（建议40行内）/ROUND_DELTA。总协调只维护COORDINATION总表/自身状态与必要任务卡/验收记录，不代作者改状态。
2. 日常按摘要调度，写清“依据作者摘要”与“已独立复核”；关键验收才核具体代码/SHA/原件。改代码前查最新相关文件，暴露歧义与取舍，先针对性检查再最小修改，不顺便重构。遵守workspace用户给出的AGENTS四项原则。
3. 独立work/Sxx目录、冻结来源/旧失败不可覆盖；默认不动原始核心文件。实际36核，allocation/selected/reserved分别记；calling-thread单核mask可以合法，不能据此误判绑核失败，核相关TID及Torch线程数。
4. 实时集群/SSH由00处理；接续前先看真实队列和marker，再跟原job直到终态/所属PID清理，不因状态旧或本地无记录就重复提交。不安装依赖、扩大预算、放松阈值、无界等候或操作其它任务PID。等待到期保存缺项，不当作授权。
5. **唯一Git窗口操作共享暂存/commit/push**。核验通过的成套更改主动提醒用户交Git窗口精确归档；不各自提交，不切共享分支、不reset/clean/强推。当前origin实际为GitHub（用户仍习惯称GitCode）：`https://github.com/953740669wu/-.git`。数据/权重/环境不入Git。
6. Git上一批1423文件已完成，旧`GIT_SUBMIT_R9_R12_S07R7_20261106.md/.tsv`是冻结历史，不能追加覆盖。本轮新卡/交接/状态及之后作者成果另列清单。保留工作区范围外历史文件，不把未提交文件全部纳入下一批。

## 新协调收到结果后怎么推进

- 作者准备完成：按READY依赖核缺项，01最终完整版本通过才让00唯一执行，不把INTERFACE_READY/REVIEW_PROGRESS当最终就绪。
- 实际数值/运行失败：核最早失败点和原证据，标后续NOT_RUN、清理与实际暴露范围；只为已定位原因另规划最小修复，不能把同一job自动重试或把门槛改松。
- 实际25步通过：01复核数值、同步、恢复/资源/终态，08给绑定原件的摘要；总协调分别记工程完成和未测项，提醒Git归档。是否安排同节点同负载单域对照以测提速，是下一轮新任务，不预支本轮预算，也不自动扩到4/16域或正式收敛训练。
- 用户只问状态时简短回答后继续当前主线；新会话不搬运全聊天、不重复已做的大检查。若用户说若干窗口完成，先读对应最新状态/变化摘要，必要时再验收。

本轮交接只写COORDINATION文档及自身状态，不运行模型、不连接集群、不改变任务卡或作者文件；交接前总协调三状态存`history/PRE_COORDINATOR_HANDOFF_20261106/`。新协调按最新文件继续即可。

## 接班增量：2026-11-06 17:01+08:00

新总协调已完成入口与五窗口短状态刷新。02已发布`INTERFACE_READY_IMPLEMENTATION_PENDING`，07已发布`INTERFACE_READY_REFERENCE_BINDING_PENDING`，00新轮`PROGRESS.json`记录部署准备/new_jobs=0及`REAL_DUAL_DDP_20261106T085703Z`，08已`PREPARED_NOT_EXECUTED`。01状态已换本轮，仍缺02/07/00最终READY，`review_complete=false`。这些新记录替代上文16:56“新目录尚未出现”的旧快照；00/02/07根摘要仍旧不代表未开工。

本轮卡SHA实核不变。本地HEAD/origin-main仍同cb342a1，暂存空，未另联网核远端。协调未启动SSH/job或后台服务；远端队列由00现场核。当前工具未暴露现有聊天通信入口，按固定文件继续，不创建替代会话。原作者等待期限沿用，未重置。最新总表/自身状态已更新；下一步等冻结依赖再作具体SHA验收，保持原卡全部执行与失败边界。

17:05补充：00根摘要已更新新轮。据其09:03Z现场核查，旧2051116终态，本系列远端无提交marker/job_id、无活动本轮job；36固定数据项SHA及7本地部署检查通过。登录端缺HPCKit如实记录，计算端实际库门禁保留。协调据作者摘要用于调度，未独立重查远端，不把这些准备检查当DDP训练接受。

17:09补充：02于17:07发布REFERENCE_READY，包62170bytes/SHA=df7275b06d8ee59cd88c0d17c04b0b64f63605ffa1c4410d3d02307ce848eec5。协调独立核16绑定、17来源、ZIP18文件身份全通过，记录REAL_DUAL_DDP_S02_DELIVERY_REVIEW_20261106.json；仅交付身份验收，无作业放行。02本地Windows初始化权重SHA被原C2门槛拒绝（原mask匹配），实际C2完整B64/KML/DDP未运行；原门槛保留。07现在可绑定冻结参考继续，仍待07/00最终READY和01最终具体SHA审核。

## 五窗口交付后的终态：2026-11-06 17:52:07 +08:00

本轮已结束，不能继续采用上方17:09的等待状态。07本地小B64/双rank13项中3项梯度超原阈值，01最终FAIL且execution_authorized=false；00 RUN_COMPLETE为NOT_RUN_S01_REVIEW_FAIL_NO_JOB，0提交/0更新/0节点秒，08完成未执行终态摘要。协调独立核42文件身份、24版本绑定及13指标，见REAL_DUAL_DDP_NO_RUN_REVIEW_20261106.json。00队列证据为09:42:41Z快照，本协调未另查询实时远端。

下一轮仅REAL_DUAL_DDP_NUMERIC_DIAG_R1_20261106.md：原07本地定位差异、原01复核，02按疑点支持，00/08待命；卡已发布但无会话通信工具，未确认已接收/启动。原训练卡和所有冻结包/FAIL保留，新卡无SSH/job授权，不能把float64原因对照或顺序分片替换正式fp32/B64参考。唯一Git窗口按五窗口本轮精确清单归档准备及拒绝证据；无科学/性能/训练接受。本协调没有后台监视或活动job。

## 用户可执行的接续与固定汇报格式（2026-11-06 17:56:43 +08:00）

已刷新07/01/02短状态与变化摘要；07 DIAGNOSIS_READY、01 DIAGNOSIS_REVIEW尚未出现。当前未确认原窗口接收或启动。
用户现在可同时把本轮提示词发给原07和01：07按REAL_DUAL_DDP_NUMERIC_DIAG_R1_20261106.md开始限定本地诊断；01先准备审核要点，07 READY未到则保存WAITING并结束，不新增90分钟等待或后台监视。07就绪后若01已结束，由用户在原01窗口发“07的DIAGNOSIS_READY已发布，请按本轮卡继续独立复核”。02无具体疑点保持待命，00/08待命。
用户回传07六行摘要及DIAGNOSIS_READY路径、01六行摘要及DIAGNOSIS_REVIEW路径即可；不搬运完整日志。07遇预算/权限/通信阻断或具体02疑点则先回传失败点/原件路径。协调按原件决定：明确实现缺陷则安排最小新修订与回归；归约差异仅获解释仍不能豁免阈值；证据不足则只定一个有判别力的下一检查。所有分支均无自动集群授权。
以后每轮汇报末尾固定附：①用户现在需要做什么；②发给哪个原窗口的具体可复制提示词；③若只需等待，明确交付与推进条件。没有新窗口动作时明确无需发送，不能只说“继续推进”，不能把卡已发布记作已启动。

## Git暂缓决定（2026-11-06，优先于上文归档建议）

用户明确要求：本轮真实双域相关准备、拒绝证据及后续诊断/训练材料暂不提交Git。后续每轮协调汇报保留待归档提醒；等用户明确要求提交后，再交唯一Git窗口按精确清单归档。当前不暂存、不commit、不push；此要求不表示真实训练已经完成。

## Git决定更正（2026-11-06，覆盖上文暂缓决定）

用户最新更正：撤销本轮Git暂缓，恢复原计划；材料核验完成并具备精确归档清单时，总协调主动通知用户并给唯一Git窗口可复制提交安排。无需因旧暂缓要求另等重新授权；共享暂存/commit/push仍仅由唯一Git窗口操作。

## 补漏归档合并（2026-11-06）

S01本地诊断复核已完成，有限接受但新DDP/清理时序未闭合；07/01诊断R1完整目录单列暂缓。本轮闭合准备/拒绝/未运行证据合并新GIT_SUBMIT_DUAL_DDP_NO_RUN_20261106.md/.tsv，作者清单自身/协调六份历史状态/Git结束状态/补漏报告纳入。历史余项逐路径处置，8条旧快照记录为被合并新版替代、原SHA未保留；12条原字节迁移有据。唯一Git窗口核精确路径/bytes/SHA后分scope提交并普通推送，差异停对应批。协调无Git写操作；当前清单冻结后状态若变化，须另交接，不能静默更新批准SHA。

## 268份Git批验收与接续（2026-11-06 20:05:53 +08:00）

本批268份/3835490bytes、7scope提交范围与原始Git对象SHA全过；HEAD/origin-main及协调实时ls-remote均f84281cb27be72fd9a4b8fb7ddb7654a338be1f5。8旧替代/12迁移记录保留，1001余项仍在，55诊断目录未混入；核验前新增仅Git两份结束状态。见GIT_DUAL_DDP_268_POST_PUSH_REVIEW_20261106.json。本次协调新增记录也是下一批余项，不追加旧批。

下一步REAL_DUAL_DDP_EVIDENCE_CLOSEOUT_R1_20261106.md：用户复制给原07只读现存原件补证或声明无法恢复，原01复核；卡发布未确认启动。不得新跑模型/DDP/训练或集群来补造历史清理证据；当前PID不存在不等于历史15秒清理通过。两交付后决定55份诊断是否可按有限结论/保留缺口归档，再另定最小数值候选。02/00/08/Git待命，原FAIL/门槛不变。

## 01/07只读收尾完成后的接续（2026-11-06）

01已ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS；历史证据补齐0、compute/后代15秒清理仍UNKNOWN，旧3/13数值FAIL/最终FAIL保持。原55份诊断加本次收尾可按有限档案新批归档，GIT_SUBMIT_DIAG_CLOSEOUT_20261106.md/.tsv，旧268批不改；524历史待核/422排除继续保留。

用户可同时发唯一Git窗口归档和原02静态提案：REAL_DUAL_DDP_MINIMAL_CANDIDATE_PROPOSAL_20261106.md，仅核Tiny与完整Encoder/KML路径对应及唯一最小候选或无依据结论，不实现、不运行。01/07/00/08待命，02交PROPOSAL_READY后协调决定方案审核/实现范围。两任务未确认接收启动，协调无Git写操作或后台运行。

## 99批验收与02无候选提案（2026-11-06 21:10:10 +08:00）

99份/773873bytes、4scope提交范围及Git对象SHA全过，协调实时ls-remote同HEAD/origin-main为05ded1bfd2b9339dcb5cd0c6708ec0b29dfa44a5；55诊断归档完成、946历史/排除余项仍在，02提案未混入99批。见GIT_DIAG_99_POST_PUSH_REVIEW_20261106.json。

02静态提案NO_JUSTIFIED_CANDIDATE，协调核36唯一来源SHA及kml_ops关键分派/反向，未运行数值。下一任务只交原01：REAL_DUAL_DDP_PROPOSAL_REVIEW_AND_EVIDENCE_SPEC_20261106.md，独立核不选候选结论、区分必需新证据与历史限制；必要时拟一个最小取证规格，不执行、不继承旧job许可、不改阈值/原FAIL。02/07/00/08/Git待命。新卡发布未确认启动；收01六行摘要/PROPOSAL_REVIEW及必要MINIMAL_EVIDENCE_SPEC后协调决定候选或具体取证授权条件。新文档留下一批精确归档，届时主动提醒。

## 01规格审核完成：本地准备阶段（2026-11-06 21:52:17 +08:00）

01接受NO_JUSTIFIED_CANDIDATE并交固定首批B64/顺序32+32零更新定位规格，协调核55绑定SHA。规格仍NEEDS_NEW_EXECUTION_AUTHORIZATION，原FAIL/阈值不变；300秒/CPU36/24GiB仅未来拟议上限。

新卡REAL_DUAL_DDP_LOCALIZATION_PREPARE_R1_20261106.md只给原02，授权独立目录取证代码/标准库夹具准备，不运行Torch/模型/DDP/SSH/集群。先判被动VJP/逻辑样本轴/保留上界/实际compute身份可行；不行交具体BLOCKED，不降规格。卡已发布未确认启动，01/00/07/08/Git待命。准备包具体齐后再做01审核/00本地部署准备；如需实际取证job，届时向用户呈具体可审核请求，当前不追加集群。02提案/01审核及协调增量留下一Git精确批并主动提醒。

## 02准备阻断与静态材料归档（2026-11-06）

用户确认上次99份Git指令之后无其它Git动作；HEAD仍05ded1b，后续提案/审核/协调增量未提交。02已完成本地支持包但B01_UNBOUND_INSTALLED_NATIVE_VJP阻断，未发PREPARATION_READY；14夹具/2CLI及909.1553MiB条件性估算非实际C2验证。原模型/阈值/FAIL保持。

新GIT_SUBMIT_STATIC_SPEC_20261106.md/.tsv仅纳入已闭合02静态提案/01审核规格和协调记录，02定位准备完整目录单列暂缓；946历史余项保留。本批冻结01当前状态，用户先发唯一Git完成提交，再发原01按REAL_DUAL_DDP_PREPARATION_BLOCKER_REVIEW_20261106.md核B01，给具体离线依据或最小缺源/操作规格，不重复旧提案或盲目重做。未确认接收/启动；02/07/00/08待命，不追加模型/集群作业。
