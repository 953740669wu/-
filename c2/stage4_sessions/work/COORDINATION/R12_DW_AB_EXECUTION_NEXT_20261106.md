# R12：固定dW分块候选的唯一同节点严格门槛与A/B

2026-11-06，Asia/Shanghai。02/08交付已收；00新部署和01专项复核并行，满足同SHA条件后00直接唯一执行，不需用户再次转发放行。本卡不代表已提交作业或已获加速。

## 已核交付与新执行范围

- 02候选仅对fp32 CPU/实际KML dW(m,n,k)=(512,2048,13312)，ta=True/tb=False/beta0/out=None/acc32False，固定两个1024输出列块，每块完整K。单最终C，原A/B，B/C列偏移0/4096bytes，lda512/ldb2048/ldc2048；其它形状/forward/dX/bias/gb保持原路径。R10 view候选不加载。
- 固定包：work/S02/round12_dw_output_tiles_20261106/package/S02_R12_DW_TWO_COLUMN_TILES.zip，81080bytes/27成员，SHA=44232f7627cfbcf59fb721acd23af46aed8fa790b20fe743a3c9886717ec4de4；源清单f61b8db309b8dad5853c7916d371b4484af609bd7610c096846bb21a7ac866bd；candidate SHA=8955f1c0bdf8b2b5d233b3eafb321d30ae0dbd184ba595959680434aedafd6ea；baseline SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26。
- 协调核13就绪绑定、26源/ZIP字节、CRC及Python3.9 AST，定向读候选diff、ABI/计数、target gate、strict/perf核心和串行包装；未见阻断部署复核的问题。作者9本地检查/30项比较差0仅假CBLAS/native Torch；实际KML/完整模型/收益仍未验证。记录R12_CANDIDATE_AND_R11_SUMMARY_REVIEW_20261106.json。
- 08 R11真实447调用/17参数组摘要已完成，协调核14份资产SHA无漂移，目标最大组与前次独立核对一致；本轮没有剩余08执行。ctypes不是纯内核，R11诊断不能作正式性能对照。
- **本卡安排一个新的有界R12作业**：必须01对具体代码+00新部署+原数据描述/资源给最终SHA绑定PASS后00才执行；不复用2043445/2048959/2049454/旧marker，不改R12_READY发布时未授权的历史字段。root无SSH/提交。
- 原固定16unit/1600统计帧/工程descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6、seed0/B64/fp32/CKPT0/完整Encoder/native SDPA/KML/原mean与AdamW保持。正式subject/split UNKNOWN，无val/test；新各阶段账本/输出，旧ledger/checkpoint/源不改。
- 单节点同job单NUMA38分配/实际36留2、DDR24576MB且limit同值、exclusive/HBM0；一个job总900秒。所有前置和应用执行共用截止，执行最大840秒、清理30/收尾30；不是各阶段单独840或先花前置时间再额外840。每入口720秒只作后备，外层剩余总预算优先。预算不足INCOMPLETE，不缩步/扩资源/续跑/重提。

## 严格执行次序（某阶段失败后后续全部不跑）

1. **实际KML局部目标门槛**：固定seed2026/randn*0.01，一次原目标、一次候选，核完整K/两块指针与leading dimension、canary/输入不变及原输出比较器。必须实际ctypes KML，不能替身/native回退。首次数值或ABI错误即FAIL关闭这个固定候选，不换tile/数值/精度重试。
2. **完整Encoder严格5步配对**：baseline/candidate各连续5更新，同初始化/原1600统计帧/前320训练帧/原mask；比较h、voltage、coarse、loss分量/total、输入梯度、全部参数梯度/参数/delta、AdamW step/一二矩/buffers，原比较器和阈值保持。target receipt/source/descriptor/node/job/CPU/库一致才启动，strict未PASS不得转性能。
3. **独立性能baseline 25步**：新进程，单epoch1600帧/25更新，前5预热、后20观察；无profiler/输出hook，原CPU/库/有限性/状态/暴露/日志/保存和0额外更新恢复保持。
4. **独立性能candidate 25步**：同节点/同job/库/env/数据/init/顺序/mask、同样诊断；新进程同25更新。strict receipt SHA及全部身份一致才启动。任一25步未完成都不能比较为完整A/B。

最多完整模型60更新（strict两侧各5+perf两侧各25），仅一对，不做ABBA、多seed/多belt/tile扫描。baseline逻辑149/native149/目标full12；candidate逻辑149/native161/目标tiles24/dispatch12，必须每步验证，不能用旧149当全部原生调用或删计数门禁。计数仅本路径，不代表Torch所有BLAS。

## S00：新部署及审核通过后的唯一执行

**本轮目标**：为R12四阶段链准备新部署，供01审核；通过后直接唯一执行并完整取证到终态。

**参考文件**：自己的最新短状态；本卡；02/round12_dw_output_tiles_20261106/{R12_READY.json,R12_CONTRACT.json,AB_PROPOSAL.md,SOURCE_SHA256.json,package}；旧原生job/资源/清理包装仅作只读参考；01本轮固定审核。

**完成标准**：

- 只写S00/round12_dw_ab_20261106/及自身状态，远端新/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_<唯一时间>/payload。先实际队列/已有marker/提交记录去重，不操作其他任务；原descriptor/manifest/16NPZ与sidecar/库/源前后身份重核，不扩样或寻找正式split作阻断。
- 适配新的target/strict/perf两个role收集及各退出/timeout/incomplete/数值失败判据，保留原生job/实际NUMA物理核/DDR/exclusive/全部TID和所属后代清理。调用02原冻结串行入口不热改；外层全链截止优先，可用剩余预算包住整个入口，不能每阶段重置总时限。使用非优化Python模式使已交assert边界检查保持可执行。
- 发布S00_DEPLOYMENT_READY.json，绑定实际代码包/索引/candidate/contract/reference/原descriptor、新部署包/索引/命令、资源与必要源SHA/LF/Linux bash-n/元数据检查；发布即冻结，供01读取，不等用户转发。登录节点不跑矩阵或完整模型。
- 等S01/round12_dw_ab_review_20261106/S01_REVIEW.json明确PASS_FOR_ENGINEERING_R12_AB、review_complete=true，绑定所有具体SHA及本卡资源/阶段数。提交前再核同SHA、实际队列及独占唯一提交标记，才一次dsub；不复用旧审核或旧marker。
- 全阶段共享900秒，某门槛FAIL不执行后续；保留真实失败位置/原metrics。超时/资源不足/源变更/库CPU异常停止，不能缩短perf25或通过少做更新补PASS。最后两个性能进程需各完成25步及保存/0额外更新恢复；本次未现场触发的故障清理分支仍如实未测。
- 收target/strict/perf_baseline/perf_candidate和整链runner全部原件/原阈值metrics、CPU/库/实际导入、logical/native/dispatch计数、25步耗时及全部分项、RSS/HWM与暴露、调度/退出/清理及权重路径/bytes/SHA。checkpoint仅远端，不下载；失败未确认的暴露范围保守留证，不自动重提。
- 发布RUN_COMPLETE.json或明确失败交接，绑定各阶段结果及索引SHA。若完整A/B完成，报告两侧后20步中位/范围和原25步，训练调用/诊断/壁钟分列；仅一对探索，不称稳态/生产加速接受。所属PID清理完更新短状态/六行摘要/精确归档范围。

## S01：候选、阶段门槛及新部署专项复核

**本轮目标**：独立核R12低层列块ABI与严格门槛链，结合00实际新部署给唯一执行的具体SHA结论。

**参考文件**：自己的最新短状态；本卡；02 R12_READY/唯一diff/契约/target与strict/perf核心/计数/原比较器/本地证据；00新S00_DEPLOYMENT_READY及具体包。只按改动需要读旧资料，不重复R11整个审核或旧5315。

**完成标准**：

- 只写S01/round12_dw_ab_review_20261106/及自身状态。先核候选仅指定shape/模式/输入条件，两个N块完整K、指针/lda-ldb-ldc/offset/bounds/canary/input/output alias，Python断言实际启用；其它路径不变，原包/数据/门槛/精度不改。验证增加12个原生调用在契约/计数上显式出现，实际candidate导入不会仍跑baseline。
- 核实际target receipt→strict5→两独立perf25的同SHA/host/job/CPU/库/数据/init/frame/mask绑定及fail-stop；完整模型参数/梯度/AdamW门槛没有被loss-only替代。严格阶段hook/双模型只作数值，不用其耗时评性能；测时两侧诊断同样执行。
- 接00部署后核总60完整更新/单对/无profiler、900秒全链共享、38/36核24GiB同limit/exclusive、唯一marker/旧job拒绝/自然或异常清理/全部阶段结果收集。没现场触发的Linux/信号分支不能用mock冒充已过。
- 作者9检查够覆盖时核原件，不额外重复全模型或旧矩阵；具体疑点才做最小独立检查。问题给定位，不代改作者源/已有候选或放宽门槛。
- 固定S01_REVIEW.json给PASS_FOR_ENGINEERING_R12_AB或FAIL/BLOCKED，review_complete及代码包/源/candidate/契约/epoch参照/descriptor/部署包/索引/本卡和资源精确绑定。通过后00可直接执行本卡唯一job，无需再用户中转；不是KML数值已过/加速接受。
- 结束更新短状态、六行摘要和精确归档范围，已发布审核原件不热改。

## 等待与后续

- 00可先准备部署，01可先审代码；固定文件直接衔接。依赖每30—60秒只读查一次、累计等候最多90分钟，不占节点等候、不常驻服务，超时留明确停点。提交后00跟踪原job；排队超过60分钟且尚未运行可取消自己本轮排队job，不重提、不取消别人作业。断线恢复先查原job/marker，禁止重复提交。
- 02冻结待01具体意见及00首次数值结果；08本轮真实摘要完成待归档，不增加其它新任务。实际target或strict失败就闭合本固定候选；完整A/B无清楚同机训练收益也可关闭，不换块宽/精度继续搜索。
- 本地包/摘要/部署审核可精确归档但不得叫KML/性能通过；R12运行返回后再核结论。唯一Git窗口按新明确清单操作，旧257清单不改，数据/权重/ZIP/环境不进Git，不混入正在写的新部署或候选修订。03—07不扩。
