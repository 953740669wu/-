# S01 R9 PROFILE5：代码及新部署专项复核

日期：2026-11-06（Asia/Shanghai）。状态：**PASS_FOR_ENGINEERING_PROFILE5 / REVIEW_COMPLETE / ACTUAL_C2_PROFILING_PENDING**。

## 1. 结论

**本轮专项前置审核通过，无阻断问题。** 发布固定S01_REVIEW.json，decision=PASS_FOR_ENGINEERING_PROFILE5、review_complete=true，绑定下列具体代码/源码/contract/reference/descriptor/部署/索引/资源身份。S00在提交前再核一致身份、实际队列和独占唯一marker后，可按新R9任务卡直接执行本轮唯一有界作业，无需用户中转或再等协调在线。

本结论仅为工程剖析执行前技术复核；真实C2 profiler能力和5步结果尚未运行验收，非科学/稳态性能/生产接受。既有job2043445授权已消耗，本次依据新任务卡，旧PROFILE_READY中execution_authorized=false历史字段不改写。S01本轮0作业/0模型/0真实profiler执行。

## 2. 具体交付与最小范围

先读自身短状态、R9_PROFILE5_EXECUTION_NEXT_20261106.md的共同边界/S01节，再核PROFILE_READY及00新S00_DEPLOYMENT_READY。任务卡SHA256：`d194dd3a385d7f6e295ddf95e46d2b2e90fcc498470474735507a7d795038d18`。只写`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\round9_profile5_review_20261106`及自己的SESSION_STATUS/ROUND_DELTA，不改02/00源、旧冻结审核、正式门禁或Git暂存/提交。

S02包69674 bytes、25成员/24源，逐字节等于已发布源码并核CRC；16份复用文件与原工程包一致。S00新包125441 bytes、27成员（26文件及空evidence目录），源码索引24项逐一核对，CRC/内包一致；预读修改源码与首次冻结版相同，6个原资源/调度/唯一提交/所属后代清理模块逐字节沿用。不是重做旧R7/25步/5315审核。

| 精确binding | SHA256 |
|---|---|
| code_package_sha256 | `15621eaa3328e407059c352d86a0f49ee68bfea39f02a68503ded6f94099abe3` |
| code_source_manifest_sha256 | `2a86fd01cab96a85cb2f0f4c8ed998edb956ef81255dfd5ceb950d41264de741` |
| deployment_package_sha256 | `e73c3def84745ce62981c0f17f097d3d8bd3aa270423083e32e49700116c96ee` |
| deployment_source_manifest_sha256 | `0b632e9ebb238317346ac7f74682d8f7f66f9ac0ec78cd8c1a446a5d9a43abc9` |
| descriptor_sha256 | `b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6` |
| interface_sha256 | `8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669` |
| profile_contract_sha256 | `35878e1bfff4fab8f85ad84b540d927570fb09858e300ba664e605080fc8c978` |
| reference_first5_sha256 | `2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8` |

PROFILE_READY SHA=`0841d7fa67b5384007b087dba28f74a92018db4e9f176e1cdd637dde9d8eb5f9`；S00_DEPLOYMENT_READY SHA=`1884c810c45c9469d3cad548598e75643328ef00f1065452f7d25a10fa77b0ba`。其余具体就绪/检查/原件和72个输入绝对路径/bytes/SHA见FROZEN_INPUTS.json。

## 3. 算术、原first5与输出隔离

从绑定的job2043445原件仅核来源及前5步：初始权重SHA、完整Encoder37995777参数/原12层512维8头、原model/KML源、image scale/训练单位、前320帧顺序与ID哈希、5个mask、voltage/coarse/total loss及KML次数均与REFERENCE_FIRST5逐项一致；没有重跑旧25步数值或旧完整审核。原mean双loss、两次zero_grad顺序、backward/AdamW、fp32/CKPT0/native SDPA/KML及原比较器阈值不变；小型fixture对5步参数/AdamW/RNG精确一致仅是作者本地证据，不推广为C2已过。

同原16个16_adjacent单元/1600工程帧，seed0/B64，全部1600帧用于同一工程归一化统计（scale0.03546142578125）；只做原前5次连续更新，确认训练320帧，1—2预热、3—5采CPU事件。没有样本补尾、AdamW重置、旧checkpoint加载、额外epoch或正式val/test。

原descriptor完整字节SHA b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6；manifest仍为任务卡14300版工程源锚，不宣称正式split或受试者映射成立。当前新根`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_20261106T030149Z`，只允许S02_PROFILE5_*/payload且拒绝旧job2043445；新暴露账本写outputs/profile_JOB/EXPOSURE_LEDGER.json，descriptor里的旧账本路径仅来源元数据只读。初始暴露清单及旧运行账本/旧checkpoint不作为本轮输出，S00现场回传其运行前SHA未变，之后仍须保持。

checkpoint继续用原工程helper与PILOT标签，PROFILE_CONTRACT已明示；其identity绑定新源码/5步配置，应用result另用PROFILE5协议。保存后独立实例恢复参数/AdamW/RNG/cursor/identity，探针额外更新0；不是加载旧权重续训。

## 4. 采样限额、完整性及检查覆盖

采样只CPU，shapes/memory/stacks/FLOPs关闭；每步最多50000事件，在单次采集**结束后**、导出前检查，未声称采集中实时截断。每采样最多256个KML包裹；恰好3份完整trace（各<=8MiB）及3份events摘要（各<=1MiB），总<=28311552 bytes即27MiB。超限不写/不截断/不重试；独占创建文件拒绝覆盖。events top80是明确的聚合摘要，raw trace保留完整已接受事件。

KML包裹含Python/counter/分配/ctypes/native，不等于精确内核时间；嵌套inclusive total不能相加，跨线程CPU合计不能直接除wall称占比。setup/start/stop/后处理导出开销单列，内部标记扰动仍含在step中，不作稳态吞吐或加速结论。

S02已有6项native Torch36小夹具检查及3种CLI拒绝原件已核；未重跑。S00本地8项及Linux登录侧8项新协议检查原件通过，登录侧另有实际包/解包/源码SHA、LF/AST3.9/bash-n、工程metadata/hash门禁回传，没有在登录节点跑模型/profiler。

发现的覆盖细节：S00原“缺阶段”夹具同时破坏SHA，单靠该项无法证明阶段语义分支。S01仅补一个最小检查，在自己的冻结副本和合成JSON内移除backward事件、同时更新事件总数及trace/events两文件SHA/bytes。正例通过；负例明确被`required phase events missing`拒绝，非SHA/bytes错误。没有改作者源码、没有Torch或profiler。这补齐该疑点，无待作者修订项。

S01还用冻结的实际review_gate验证具体8项binding正例，以及旧PILOT决定、错误reference、错误部署索引拒绝；只做接口集成检查，不重复旧runner矩阵。独立证据independent_sampling_semantics.json/deployment_review.json。

## 5. 新部署与唯一执行合同

新review_gate只接受PASS_FOR_ENGINEERING_PROFILE5+review_complete=true及全部8项SHA/资源；旧PILOT PASS不放行。submit_once.marker排他创建，dsub只调用一次；超时/返回不明也保留标记，不重试。当前卡只授权本轮新根一次，不复用旧marker，也不能在脚本后再手工dsub。

资源固定单节点单NUMA38分配/前36实际物理核/末2预留，DDR24576MB且limit同值、exclusive、HBM0、900秒、retry0。新原生job/主机/CPU授权通过nonce/rawSHA/新鲜调度回传核验；拓扑/物理核心/DDR检查和同PID框架前selected36绑定保留，实际Torch36、全TID非空子集、KML/OMP/shim来源及GEMM继续检查，允许调用线程close单核，不用setter伪造现场配置。

整个外层入口START起共840秒（包括30秒门禁），不是训练子进程另得840秒；内部720秒后停止新更新。subreaper接管自有后代/另起session，按PID/start-ticks核身份，统一TERM15/KILL15总30秒、最晚870秒，留30秒收尾，硬限900秒。不取消/借用其它任务；自己排队超60分钟未启动才可按卡复核后取消，不重提。

新profile_outcome成功要求5步/320帧、连续AdamW/B64/cursor、每步3个原loss比较passed、19个无错误CPU checkpoint、实际KML/来源/恢复证据、2+3顺序及3trace/3events完整。逐采样核raw SHA/bytes、事件数<=50000、marker<=256及与KML次数相同、5个必要phase、raw事件数/summary数及摘要top上限；缺任意项不会成功。UNSUPPORTED_PROFILER/PROFILE_LIMIT_EXCEEDED/SOURCE_CHANGED/DATA_NOT_READY/ERROR_RUNTIME_OR_STATE/INCOMPLETE及非零退出保留，不降级为旧成功或fallback。

collect_evidence收新profile_JOB全目录，包含全部trace/events、result/steps/ledger、库/CPU/退出、调度/清理、source/contract/reference/descriptor及真实mtime_ns/bytes/SHA；checkpoint留远端，仅回传路径/大小/SHA/零更新恢复，不下载权重或加入Git。原始失败/缺失证据同样保留。

## 6. 未现场验收与停点

仍须由**唯一实际job**验证：C2 CPU profiler支持及2+3真实采样、原first5 loss门槛、实际CPU36/KML/TID、真实checkpoint/零更新恢复、调度终态/所属PID清空。Linux登录mock并不等于本轮原生信号故障清理实测；未触发的TERM/KILL分支须如实列未触发，不宣称已过。

异常/不支持/超限/来源或数值失败即停，无安装、backend回退、改阈值、重选样/扩预算或第二job。本报告不接受科学/泛化、正式split、稳态性能/优化收益或生产部署；热点排序仍待实际事件。本窗口不代00提交，也不承诺后台继续监控；S00依卡跟踪唯一job到终态。

## 7. 证据与待归档

本轮根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\round9_profile5_review_20261106`。

- S01_REVIEW.json：原子发布、具体SHA绑定的固定专项结论。
- code_review.json / audit_profile_package.py：包/16份原源/first5参照和6项作者检查。
- deployment_review.json / audit_profile_deployment.py：新部署身份/判据/检查及具体binding验证。
- independent_sampling_semantics.json：刷新SHA后的阶段语义正负例，明确LOCAL_FIXTURE。
- FROZEN_INPUTS.json：具体冻结输入；REVIEW_PROGRESS.json/WAIT_LOG.jsonl：本轮有限等待。
- REPORT.md、ARCHIVE_FILES.json、ARTIFACT_SHA256.txt：最终报告、精确元数据/代码归档范围和本地索引。

本轮仅新增上述专项工作，不改旧01审核、原02包或00部署；不会操作共享Git暂存/提交/推送。精确待归档范围排除工作用解包副本、合成fixture、ZIP、数据/权重/环境。
