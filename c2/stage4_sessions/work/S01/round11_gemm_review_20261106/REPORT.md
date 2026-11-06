# S01 R11：原基线KML调用分解专项复核

日期：2026-11-06（Asia/Shanghai）。状态：**PASS_FOR_ENGINEERING_GEMM5 / REVIEW_COMPLETE / ACTUAL_C2_GEMM_CAPTURE_PENDING**。

## 1. 结论

**本轮前置专项核验通过，无阻断问题。** 固定S01_REVIEW.json的decision=PASS_FOR_ENGINEERING_GEMM5、review_complete=true，绑定以下8项交付SHA及资源。S00提交前再核同一包/源码/审核原件/descriptor等全部身份、实际队列及新独占marker后，可按R11新任务卡直接执行唯一5步采集，无需用户中转。

R10候选保留为CLOSED_NOT_SELECTED_LOW_BENEFIT，不是数值FAIL；本轮不集成它、不执行其20更新A/B。R11使用未改原baseline，仅增加可撤销标量观测；实际C2的KML调用/数值/记录/终态仍须唯一job验收。无科学、加速、稳态性能或生产接受。S01本轮0提交/0模型/0实际KML/0Torch profiler。

## 2. 来源身份与审核范围

先读自身最新短状态及本卡S01节，再核02早期接口、GEMM_READY、具体源码/差异/原件和00新S00_DEPLOYMENT_READY。任务卡`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\R11_GEMM_BREAKDOWN_NEXT_20261106.md`，SHA `b1828392f6824b7c9158f2ff6d6e81c1536123dc8f93f1345cce3532b167a91e`。仅写`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\round11_gemm_review_20261106`及自身状态，不改作者源/旧01审核/旧原件/共享Git。

代码ZIP74859 bytes，27成员/26源；全部逐字节等于发布源码、清单与CRC通过。17份复用文件与R9原件一致，原baseline/kml_ops.py SHA仍`e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26`，没有R10候选实现。observer SHA `14ee30f47adbb0ddfecc01bd8bc2acfe0048a1c1596a0e32664762193143e67a`；预读代码与首次冻结版相同。

00部署ZIP132033 bytes，29成员（28文件及空evidence目录）/26项源码索引；外包、内包、解包、SOURCE_SHA及实际就绪记录一致。6个原生资源/CPU36/调度/唯一提交/所属后代清理模块字节不变，prepare函数AST仅模块常量的根前缀/包名/资源配置改变。新协议run_job/gemm_outcome/collect/review_gate已定向复核；不重复完整R9审核或旧5315。

| 精确binding | SHA256 |
|---|---|
| code_package_sha256 | `d9bd138890e56c5fc6c1dba538c0c78112441849689a82782fdc6856a203e142` |
| code_source_manifest_sha256 | `bda3b37a35880c35bfcec65b80c53624e108de6387f4fa9fd377429b76afffa1` |
| deployment_package_sha256 | `64a45ae7444506984ebb65d7cb3a39930d088be4f1ac1f3fdcc2d89eeb095d3b` |
| deployment_source_manifest_sha256 | `2e825fb7663689aee5cf664b8fdcd4bd9a4809c41707352e1a8c8fd1f33075d9` |
| descriptor_sha256 | `b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6` |
| gemm_contract_sha256 | `a4876ab4a6b6a3c517fb95bc18183bc89015617cdb49a4f6eb5b3380967edeab` |
| interface_sha256 | `1477124f8b772226c76f8f50cee16c5d34ac34f7d8748d327c4402f82d074f76` |
| reference_first5_sha256 | `2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8` |

GEMM_READY SHA `800df62a563aeb9f211a46ed516b985670e182da20485f1d491f46cf550c05e0`；S00_DEPLOYMENT_READY SHA `b84f89f1968411faf4e72f92102c0e8d72813c7b08a0074aaca283c2ef26ebc6`。共72项具体就绪/源码/检查/旧审核输入路径、bytes及SHA见FROZEN_INPUTS.json，发布前再次核一致。

## 3. 观测不改计算及原门槛

完整Encoder37995777/fp32/CKPT0/native SDPA/KML、原mean双loss/AdamW参数与操作顺序、seed0/B64、原first5初始化/scale/frame/mask/KML149及15个loss比较门槛、源/有限性/CPU/暴露/保存和0额外更新恢复均保留。原训练helper/比较器及REFERENCE_FIRST5与R9原件逐字节一致；没有更换数据、重置AdamW、补帧或调阈值。

原descriptor完整SHA b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6，原16单元/1600帧仍用于统计，只训练原前320帧/5次连续更新。data_gate/engineering_data.py和邻接旧INTERFACE（8b1b…）保持原门禁；顶层1477124f…INTERFACE只定义R11交接，不覆盖旧描述接口。正式split/subject仍UNKNOWN，无val/test或泛化结论。

运行端先核baseline原SHA、实际baseline导入路径/SHA、真实_sgemm是ctypes._CFuncPtr及observer路径/SHA，禁止Python替身/错误来源冒充KML。外层包裹原counted GEMM，原位置/关键字参数对象原样调用一次；native hook核原row-major14个参数、A/B/C指针、m/n/k及leading dimensions、alpha/beta/flags，再调用同一个原_sgemm一次。没有更改派发、输入、返回Tensor或输出顺序。

仅3—5训练步安装hook；1—2、保存、恢复不安装。线程local栈+加锁序号对应同线程/同调用，记录parent索引；原生缺配/多配/无外层即失败。Linear forward/backward上下文与flags联合确认forward/dX/dW，其余UNKNOWN，不按尺寸猜角色。

metadata仅shape/stride/dtype/contiguous、SGEMM标量、输出shape/storage-alias布尔及时间/线程/序号；观察器无Tensor值clone/copy/dump或RNG操作。暂时Tensor引用仅存在当前调用上下文，退出弹栈，记录中不留Tensor。四处hook（gemm/_sgemm/forward/backward原staticmethod描述符）在Python可展开退出的finally恢复，且恢复发生在导出前。强制进程终止不声称finally执行，但不修改源文件，进程终态/清理由外层负责。

## 4. 时间边界、限额与检查原件

每条记录带外层及ctypes TID、原始单调ns区间、实际SGEMM标量/矩阵元数据，保证外层包含同次原生边界并保存差值。gemm_wall覆盖原counted GEMM内计数/分配/参数准备/调用及native-hook开销；ctypes_wall覆盖原_sgemm的Python转换、库内部打包/调度/计算，**不是纯微内核时间**。outer-minus-ctypes也不是扣净观测开销的纯准备时间；metadata前后及native-hook bookkeeping另记，Linear进入GEMM之前的reshape/bias预填不在该包裹内。嵌套父子/跨线程区间不能简单相加当程序wall。

只观察直接kml_ops.gemm/_sgemm路径，不覆盖Torch/native SDPA内部全部BLAS。3份gemm_step_3/4/5.json，每份<=1MiB、每采样<=256条且成功必须149条（共447条）一一配对；超限不截断/不重试，无R9完整profiler/trace。

作者02的9项LOCAL_FAKE_CBLAS_ONLY检查及3种CLI框架前拒绝原件已核；覆盖真实Tensor接口下的单次委托/参数形式和对象/输出/梯度/RNG一致、连续5步AdamW状态一致、仅3—5记录、4处hook恢复、并发/嵌套上下文、缺配/多配/无外层、数量/字节限额及能力拒绝。它们不证明实际KML/C2或完整Encoder已过，本窗口未重跑。

00本地9项及Linux登录fixture9项原件通过。语义负例刷新文件SHA和汇总后核矩阵维度、native次数/参数、TID、区间及role上下文拒绝；覆盖已够用，没有具体未补缺项，本窗口不额外生成矩阵或替身套件。实际8项绑定的review_gate已消费具体候选记录通过，核新决定/新资源/契约/索引字段。

## 5. 部署、源核对、清理与唯一执行

新根`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_20261106T041202Z`/payload，新gemm_JOB输出/暴露账本，旧2043445/2048959和旧marker禁用。原descriptor不改旧ledger路径，它只是来源元数据，本次不写旧ledger/checkpoint。源/16NPZ/sidecar在读取前后原门禁核SHA；00有36份固定源文件纯SHA收据（descriptor/manifest/cases/初始ledger+32个NPZ/sidecar），无数组导入/训练。

远端部署日志有实际外/内包SHA、LF、AST3.9、Linux bash-n、metadata hash gate和fixture9通过。终端原件含ANSI换行，原件不改，本审核只去escape核关键状态token，不重构/伪造JSON。较早一次可选旧helper元数据SSH中断没有结果，OPTIONAL_METADATA_ATTEMPT如实保留；其独立40秒有界纯SHA替代检查和后续部署metadata门禁均通过，不能把那次中断说成模型或现场KML失败/通过。

单节点单NUMA38分配、同域前36实际物理核/末2预留，DDR24576MB请求与limit相同、exclusive、HBM0、retry0，job最多900秒。外层START起整体840秒包含30秒门禁；内部720秒后停新步，统一所属后代TERM15/KILL15清理30秒、最晚870秒，留30秒收尾，不按子进程重置时限。subreaper接管另起session/reparenting，发信号前核PID/start-ticks，不操作其它作业。

原生job/host/授权/实际资源与新鲜nonce/rawSHA调度交接、物理核/NUMA/DDR及同PID框架前收窄selected36保留；阶段及每步保存恢复检查实际Torch36/非空全TID子集/KML/OMP/shim来源和GEMM。调用线程close单核合法，不靠setter虚报36。

新review_gate只认PASS_FOR_ENGINEERING_GEMM5+complete+8项SHA/资源；新submit_once.marker排他，失败/超时/ID不明也不重提。00提交前重核队列/原提交记录，才一次dsub；若自己本轮排队60分钟仍未运行，可按卡复核后取消、不重提。

GEMM5成功判据要求5更新/320帧、15个loss比较passed、19个CPU checkpoint无错误、实际库/KML/源/恢复，前2无详细记录，后3各149完整记录；不接受旧PROFILE5成功/trace替代。逐行核唯一序号、原生一对一、shape/stride/dtype、flags/beta与m/n/k/output、实际native参数/TID、role上下文、时间嵌套/差值及parent同线程区间；三份SHA/bytes及上限齐全。不支持/限额/缺记录/来源/数值/运行错误/INCOMPLETE保留原状态和非零退出，不自动换backend或重试。

收集原steps/result/3明细、source/contract/reference/descriptor、CPU/库/分配/调度/命令/退出/清理、暴露账本及真实mtime_ns/bytes/SHA；checkpoint留远端收路径/大小/SHA和零更新恢复，不下载权重。失败保留已有同样证据，不缺项即PASS。

## 6. 尚待现场与结束停点

本次完成的是**前置专项核验**。实际_sgemm ctypes/KML三份149一一配对、原first5 loss/CPU36/库/TID、保存恢复及最终job/PID清空，仍由唯一作业验证；本地/登录fixture不是真实信号故障清理实测。异常即停，不安装/回退/扩样/扩资源/第二job，更不续跑R10 A/B。

S01没有查询远端队列或提交/监视job，不推断00此刻活动job。发布固定审核后由00直接执行并跟踪终态，08据原件分析；本会话完成前置任务，不声称后台继续。旧冻结审核/原件未改，未做科学/加速/生产接受。

## 7. 本轮证据与归档

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\round11_gemm_review_20261106`。

- S01_REVIEW.json：原子发布、绑定具体SHA/资源的固定专项记录。
- code_review.json / audit_gemm_package.py：冻结代码/17复用源/接口/测试原件。
- deployment_review.json / audit_gemm_deployment.py：新部署/26索引/纯SHA/登录原件/资源门禁。
- interface_review.json / INTERFACE_FROZEN_COPY.json：早期稳定接口；preliminary_code_review*.json保留预读阶段。
- FROZEN_INPUTS.json：72项冻结输入绝对路径及身份；REVIEW_PROGRESS.json/WAIT_LOG.jsonl为有限等待。
- ARCHIVE_FILES.json、ARTIFACT_SHA256.txt：精确待归档范围和本地完整索引，排除工作解包副本、ZIP、数据/权重/环境。
