# S02 R11：原基线KML调用分解准备完成

2026-11-06（Asia/Shanghai）。S02仅准备接口、可撤销观测和冻结包；没有提交集群、读取真实NPZ或执行完整Encoder。按R11任务卡由S00新部署、S01精确SHA专项PASS后直接唯一执行，无需用户中转。S02不操作其它窗口目录或共享Git。

## R10处置

R10保留，CLOSED_NOT_SELECTED_LOW_BENEFIT；不是数值FAIL，不集成、不安排其20更新A/B。R10_READY及候选原件SHA未改，新处置记录R10_DISPOSITION.json。此包仅含未改原baseline，KML源码SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26，不包含R10候选实现。

只读核S08归因就绪文件及5个指定归因资产；用作本轮观测边界依据，不重跑解析/训练。R9复制归属不全在Linear，不能凭copy次数选优化；本轮只补实际GEMM元数据和调用边界证据，不作新性能收益结论。

## 接口先交与原数据门禁

INTERFACE_READY.json已先于代码发布，接口SHA=1477124f8b772226c76f8f50cee16c5d34ac34f7d8748d327c4402f82d074f76，保持不变。新协议ENGINEERING_REAL_CORPUS_GEMM5_V1；原输入协议/descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6、16单元/1600统计帧/seed0/原前320训练帧、初始化/scale/frame/mask及原15项loss门槛不变。

原engineering_data.py与其原INTERFACE.json字节一并存入data_gate/，入口显式从那里导入。原8b1b…接口继续约束旧descriptor；顶层1477…接口仅定义R11交接。这避免用新接口SHA替换旧描述或静默放宽数据门禁。本地已验证S00原descriptor元数据兼容；实际manifest/NPZ/sidecar与源前后核验仍由原门禁及S00执行。新账本在outputs/gemm_JOBID，旧运行清单/checkpoint不写。正式split/subject UNKNOWN，无val/test/科学接受。

## 最小观测及可解释范围

沿R9已跑通入口保留完整Encoder37995777/fp32/CKPT0/native SDPA/KML、原mean双loss/AdamW、实际CPU36/全部TID、源/库/有限性/暴露/保存及零更新恢复。共17份复用文件字节一致；R9/原工程源码及历史失败不改。新入口取消完整Torch profiler，只在训练第3—5更新用context manager临时包裹原counted gemm、_sgemm和Linear forward/backward两个调用点；前2更新不挂，保存/恢复/诊断不挂。

每个original GEMM与_sgemm函数恰调用一次、原对象/位置及关键字参数原样转发。raw14个SGEMM参数与原row-major/flags/m/n/k/alpha/beta/lda/ldb/ldc和A/B/C指针一致才允许调用。真实入口还要求_sgemm为ctypes._CFuncPtr，拒绝Python替身或错误模块来源。baseline和observer实际导入路径/SHA记入result，临时hook四处在finally恢复，成功/异常/限额/导出失败均覆盖。

记录每次A/B shape/stride/dtype/连续性、flags/beta、m/n/k、raw_sgemm标量参数、输出shape/storage alias布尔、线程/调用序号/父调用及monotonic ns起止。不复制或打印Tensor值，不改RNG。role仅由已核Linear上下文及flags确定forward/dX/dW，其余UNKNOWN。线程local栈和全步序号防串；嵌套保留parent，不相加父子inclusive或跨线程区间当程序wall。

gemm_wall包住原counted GEMM；ctypes_wall包住同次原_sgemm，含Python参数转换/库内部打包/调度/计算，**不是纯微内核时间**。outer_minus_ctypes含gemm内部准备/计数/分配及观测bookkeeping，metadata前后和_sgemm hook bookkeeping另记；仍不能精确扣除全部context/timer开销。A/B是已准备操作数，Linear前面的reshape/bias预填不在此边界内。观察只覆盖这149次直接kml_ops调用，不覆盖Torch内部所有BLAS。本轮不是A/B或正式吞吐验证。

最多3份详细文件gemm_step_3/4/5.json，各<=1MiB、每步<=256条且必须149条完整一一对应，不截断、不重试。失败也尽量写同一有界文件并标FAILED；超字节上限不写大文件，错误和计数留result。原first5 KML计数及15项loss门槛不改；缺配/多配/源/CPU/库/数值/能力/限额异常即停止。

## 实际本地检查

9项LOCAL_FAKE_CBLAS_ONLY检查通过：单次原调用/参数形式和对象/输出及输入权重bias梯度/RNG一致；连续5步AdamW最终参数与状态完全相同、仅3—5记录；异常恢复4处hook；双线程隔离、嵌套父关系；缺native/重复native/无外层native、计数和字节限额及能力拒绝。替身使用真实Tensor接口和原baseline Python GEMM函数，但没有实际KML或完整模型；不扩大成C2数值通过。

另3种CLI框架前拒绝（缺描述、正式协议混入、B32）、Python3.9 AST/LF/Git Bash -n、observer无Tensor值复制/转储代码、原data_gate兼容及来源/ZIP逐项SHA通过。旧5315/R10矩阵不重跑。证据evidence/local_validation.json及observer_final.log，原始检查/失败分支保留。

## 交付和停点

包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round11_gemm_breakdown_20261106\package\S02_R11_GEMM5_CODE.zip；74859bytes/27文件；SHA256=d9bd138890e56c5fc6c1dba538c0c78112441849689a82782fdc6856a203e142。
源码清单SHA256=bda3b37a35880c35bfcec65b80c53624e108de6387f4fa9fd377429b76afffa1；observer SHA256=14ee30f47adbb0ddfecc01bd8bc2acfe0048a1c1596a0e32664762193143e67a。
命令/资源/收集见E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round11_gemm_breakdown_20261106\C2_HANDOFF.md；契约GEMM_CONTRACT.json；差异E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round11_gemm_breakdown_20261106\diff\R9_TO_R11_OBSERVATION.patch；package/PACKAGE_MANIFEST.json逐文件索引；GEMM_READY.json固定就绪。

本轮S02真实KML观测0、完整Encoder0、新job0；旧原件和门槛不动。尚存实质验证为S01代码/部署专项审核及S00唯一C2采集中的真实调用一一对应、原loss/CPU/库/保存恢复和终态清理。按当前任务卡新授权，S01 PASS绑定相同SHA后S00直接执行单域38/实际36、DDR24576MB同limit/exclusive、900秒作业；全入口840+清理30+收尾30，内部720秒停新更新，达到5即结束。失败停、不重试、不扩资源、不跑R10 A/B。

发布后源码/包不热改。精确Git候选ARCHIVE_FILES.json排除ZIP/数据/权重/环境；没有暂存/提交/推送。S02可在有限等待内只读接收S01具体审核意见，运行与终态由S00负责。
