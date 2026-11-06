# R10处置与R11：有界KML调用分解

2026-11-06，Asia/Shanghai。用户持续要求推进真实工程训练和优化。本轮先按02/08短状态调度，因收益决策定向核R10编码前选择/唯一diff/A-B提案及08真实归因；不重复模型或旧检查。

## 已作决定

- R10只复用一次反向flatten的view；原R9反向reshape无矩阵复制。原115项比较差0是本地native替身结果，真实KML/完整Encoder未运行。**保留候选，CLOSED_NOT_SELECTED_LOW_BENEFIT，不提交其20更新A/B、不默认集成**。这是收益依据不足的筛选结论，不是数值FAIL；不能把带profiler的约1.8ms视图事件当无profiler实际收益。
- 08真实归因已完成：每采样KML前向50/反向99；1003个copy分属optimizer765、ViewBackward96、Linear前向62、attention反向12、layernorm反向12、其它56。optimizer copy虽多，区间约3.6ms；ViewBackward约172—244ms；不能把全部copy归到Linear反向，不能按调用数代替耗时。
- 现有关键缺项是KML每次调用的实际m/n/k、A/B shape/stride/flags、以及外层准备与ctypes原生调用边界各花多少时间。下一步只补这一个定位证据，暂不再提交微小view候选或做第二个盲选优化。
- 协调核R10 10份就绪绑定及08 11份摘要资产SHA无漂移，未重跑7项本地检查或真实模型。证据R10_LOW_GAIN_AND_R9_ATTRIBUTION_REVIEW_20261106.json。源/候选/原证据保持。

## 本轮公共范围与条件执行

- 仅新诊断协议ENGINEERING_REAL_CORPUS_GEMM5_V1，原工程输入协议/descriptor保持；用**未改的原baseline**，不用R10 candidate。完整Encoder/fp32/CKPT0/native SDPA/KML、原mean/AdamW、seed0/B64和原1600统计帧/前320训练帧不变；无正式split/subject/val/test，暴露范围不扩。
- 仍连续5更新；1—2不记录详细调用、3—5记录实际GEMM标量元数据和计时。保留原first5初始化/scale/frame/mask/KML计数/loss门槛与保存/零额外更新恢复。不启用完整torch.profiler、不导出R9 trace，不把本轮计时当加速或同机A/B。
- 每条记录包含step/调用序号/线程与单调起止时间、A/B shape/stride/dtype/连续性、ta/tb/beta、m/n/k、输出shape/alias布尔、原GEMM包裹wall与实际_sgemm ctypes调用wall；只记录标量/元数据，不复制或打印tensor值。实际调用原函数一次、参数/输出/顺序不变，异常和所有退出路径恢复临时hook。
- ctypes调用wall包含Python参数转换、原生库内部打包/调度/计算，仍不是纯微内核时间；外层包裹也含计数/分配等。区间和差值同范围记录；并发/嵌套按线程/区间处理，不把跨线程耗时相加当程序wall。role仅按已核Linear调用点及转置参数归属forward/dX/dW，无法确认标UNKNOWN，不能猜。
- 最多3份详细调用文件，各1MiB、每采样最多256条；预期每采样149次，不截断、不重试。出现漏配/多配、对不上原KML149次/步、源身份/原loss/CPU或库错误、超限/能力不支持即停。实际调用旧_sgemm参数，不切backend或安装新库/工具链。
- 新的唯一有界安排：00新部署、01对新代码/数据/部署绑定SHA专项PASS后，00可直接执行一次；不等用户中转、不复用2043445/2048959/旧marker。单节点单NUMA38分配/实际36留2、DDR24576MB同limit/exclusive、HBM0、job最多900秒；全入口840+清理30+收尾30，内部720秒停新步。达到5步即结束，不自动重试/扩样/扩预算或续跑R10 A/B。
- 发布即冻结；任务只写自己的新目录和短状态。等待依赖每30—60秒只读查固定文件，总等待最多90分钟，不占计算节点等候、不装常驻服务。排队60分钟仍未启动可取消自己本轮排队job并留报，不重提。当前安排未提交任何job。

## S02：R10收尾与R11最小调用观测包

**本轮目标**：记录R10低收益不选用的处置；在原基线上准备最小GEMM元数据/调用边界观测包，交00/01衔接。

**参考文件**：自己的短状态、R10 DECISION/diff和冻结原baseline；本卡；S08/profile_r9_2048959_20261106/PROFILE_SUMMARY_READY.json及归因索引；R9冻结工程入口/first5参照/CPU36守卫。

**完成标准**：

1. 只写S02/round11_gemm_breakdown_20261106/及状态，R10_READY和旧候选不改。先交INTERFACE.json/INTERFACE_READY.json定义本卡最小结果/就绪字段，尽量复用R9收集接口，不另建通用profiling框架。
2. 实现最小可撤销观测；外层GEMM与同次实际_sgemm调用按线程/序号对应，记录合法实际shape/flags/alias及两个边界时间，不能改变matmul参数或用native替身混称KML。只在训练采样3—5启用，恢复/保存期间不采集；同时保留原所有门禁及暴露记录。
3. 只补新观测必要检查：调用一次/参数输出/RNG不变、异常恢复、线程上下文不串、原生与外层记录一一对应、限额与缺记录拒绝；可用本地替身验证接口，明确实际KML待C2。复用原数据/五步原loss门槛，不重跑无关矩阵或把新包称优化接受。
4. 交GEMM_READY.json锚定代码包/源码索引/接口/新契约/命令和实际检查SHA；25步/原profile/R10基线和历史失败不改。包无安装/提交逻辑；旧baseline源码身份须e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26，实际导入/临时观测身份明确。
5. 完成新包后可等待01具体意见，不热改冻结交付；新协议不是新正式划分。更新短状态/六行摘要和精确待归档清单。

## S00：新部署与唯一执行

**本轮目标**：按02早期接口准备新R11部署，01审核通过后直接唯一采集，收结果到终态。

**参考文件**：自己的短状态；本卡；02新INTERFACE_READY/GEMM_READY；R9实际部署/清理代码只读参考；原descriptor与环境。

**完成标准**：

1. 只写S00/round11_gemm_breakdown_20261106/，远端新S02_GEMM5_<唯一时间>/payload；先去重实际队列/marker，不借用其它任务。新工程数据沿用原descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6，原manifest/16NPZ/sidecar源前后重核；新账本/输出，不写旧ledger/checkpoint。
2. 新S00_DEPLOYMENT_READY.json锚定R11包/接口/契约/descriptor及部署包、索引、必要LF/bash-n/元数据检查和资源。适配新成功/缺记录/limit/unsupported/incomplete语义与3份调用文件收集，保留原生job/实际NUMA/CPU36/时限/所属后代清理，不拿旧PROFILE5三trace齐全作为新成功判据。
3. 固定等S01/round11_gemm_review_20261106/S01_REVIEW.json明确PASS_FOR_ENGINEERING_GEMM5、review_complete=true且绑定最新交付SHA；提交前重核全部SHA/队列及唯一marker，才按本卡一次dsub。未通过/缺项不执行、不重提，不等待用户另行中转。
4. 跟踪终态和所属PID清理；收完整steps/result/3份GEMM记录、原first5身份与15项loss、CPU/KML/库/资源/退出、账本、保存恢复及调度原件。checkpoint只留远端收路径/bytes/SHA，不下载权重。源不变、5步/320帧/3份149条一一对应、原门槛/恢复/清理齐才可完成，失败保留原样。
5. RUN_COMPLETE.json锚定本地证据索引、3份记录、完整性/终态供08直接读。有限等待或中断先更新停点及job ID，恢复先查原job，不另提。结束更新短状态/六行摘要与归档清单。

## S01：只审新观测与新部署

**本轮目标**：专项审核R11观测是否保持算术/调用次数、记录是否可信、新部署是否符合唯一有界安排。

**参考文件**：自己的最新短状态；本卡；02 GEMM_READY/源码差异和检查原件；00新S00_DEPLOYMENT_READY。旧审核只用于来源/预算参照，不重复完整R9审核。

**完成标准**：

1. 只写S01/round11_gemm_review_20261106/；先审02可撤销观察、线程/调用对应、元数据与两个计时边界、无tensor复制/参数/RNG改变、限额/原门槛，再接00部署的协议/资源/marker/全入口时限/清理/收集。
2. 作者检查够用则核原件，具体缺项才补最小正负例，不跑完整模型/旧5315；不能把mock算实际KML或故障清理通过。发现问题给定位，不代改作者源或自动换方案。
3. 固定S01_REVIEW.json写PASS_FOR_ENGINEERING_GEMM5或FAIL/BLOCKED，review_complete及代码/索引/接口/契约/参照/descriptor/部署和资源的精确SHA绑定；通过后00可按本卡唯一执行，无科学/加速/生产接受。结束更新短状态/六行摘要/精确归档范围。

## S08：现有尺寸目录；新结果到后归因（不阻断主线）

**本轮目标**：先从已有原件生成能确认的GEMM尺寸/flag/总次数目录供02/01交叉核；若新采集在有限等待内到达，再据真实调用记录指出最耗时形状和阶段。

**参考文件**：自己的最新归因摘要；本卡；R9原result.runtime.kml_shapes、已核Linear代码；02 R11早期接口、S00 R11 RUN_COMPLETE（尚未到时不伪造结果）。

**完成标准**：

1. 只写S08新gemm目录。已有runtime的计数包含训练和恢复等全进程调用；只能有证据地分开，未知就保留总数/UNKNOWN，不能把全进程shape计数都叫149训练调用。shape可算工作量粗估，但不能据FLOPs推断实际最快/最慢矩阵，不新增训练/NPZ/权重读取。
2. 先交尺寸目录及来源/未知项，工具保持最小。若R11结果在上述90分钟等待内到，核绑定SHA和记录数后按实际shape/flags/forward-dX-dW、外层准备/ctypes调用范围整理；处理线程/重叠，不把ctypes span叫纯内核或跨主机比速。未到就交已有目录及明确停点，不声称后台等待。
3. 新原件不改，不另交同一个微小view候选；给可直接支持下一项实质优化的排序/仍缺证据。仅工程观察，无科学/正式性能接受。结束更新短状态/六行摘要及精确归档清单。

## Git及其他任务

R10候选/本地通过和低收益不选用结论、08已完成归因均可下一批精确归档；不谎称数值失败、KML已通过或已提速。唯一Git窗口按新清单操作，旧257清单不改，活动R11不混入，真实数据/权重/环境/ZIP不入Git。03/04/05/06/07不扩，不安排其它新job或环境测试。
