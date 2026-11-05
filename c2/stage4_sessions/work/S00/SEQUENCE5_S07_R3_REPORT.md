# S00：五步严格对照通过，两域normal初始化失败

2026-11-05，Asia/Shanghai；轮次20261105T091410Z。

按COORDINATION/AFTER_SEQUENCE5_WRAPPER_REVIEW_NEXT.md的S00节和S00_RESUME_S02_SEQUENCE5_REVIEW.md执行，两项独立任务顺序各提交一次。S02 job2040203完成五步原阈值严格对照；其终态/PID清空后才提交S07 job2040233。S07在normal进程组初始化失败即停止，没有重试，没有运行五步内存、S06、正式训练或真实HBM。

## 作业及资源

| 项目 | S02 R7五步严格 | S07 R3两域小张量 |
|---|---|---|
| job / 节点 | 2040203 / cn21339 | 2040233 / cn21339 |
| 终态 / jobExitCode | SUCCEEDED / 0 | FAILED / 1 |
| 中国时间起止 | 17:17:17—17:18:29 | 17:19:03—17:20:03 |
| 实际起止节点秒 / 调度usage秒 | 72 / 71 | 60 / 59 |
| 分配及绑定 | 38分配0—37；计算选0—35；留36—37，NUMA0 | 76分配0—75；NUMA0选0—35留36—37；NUMA1选38—73留74—75 |
| 总DDR申请 / limit | 24576MB / 24576MB | 24576MB / 24576MB |
| 时限及启动 | 900秒；原严格780秒+15秒kill | 300秒、exclusive；已核消费者270秒预算及原监督清理 |
| 实际CPU36证据 | 同一checker PID，24个有序检查点，全过 | 两域选核/逐核拓扑已核；normal仅rank1到实际Torch36测量，rank0未到该记录 |
| 最终调度PID字段 | `-` | `-` |

本轮按UTC起止相差口径共132节点秒，约0.0366667节点小时；调度usage合计130秒另列。沿用上一轮17job/766秒，已知累计19job/898节点秒。任务执行无重叠；调度重试字段均0。结束无活动S00 job；账号中其它任务未操作，不能据此说整个账号队列为空。SSH/SCP连接均正常退出。

## 执行前核对及不可变包

先读S00短状态/增量、总表、固定交接和审核，再核最新源码/包及Git记录；开始时HEAD=e4a8645，收口只读查询为5a22dbe（其它Git窗口归档，本会话未操作暂存区）。远端查询当前账号队列，限定检查S02_SEQUENCE5_*、S07_R2_TWODOMAIN_R3_*目录及提交原件，确认本轮没有已有任务，证据为downloaded/REMOTE_DEDUP_BEFORE.json及各job的queue_before_submit.stdout。其它job不动。

| 已核原包 | bytes / 文件数 | SHA256 |
|---|---|---|
| S02_SEQUENCE5_R7_CODE.zip | 55378 / 24 | bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092 |
| S07_S00_WRAPPER_R3.zip | 71154 / 10文件+空目录条目 | 08e0c921e33631c9e98ac1465cf854a74c1a353a08ecbc13f480b42f296da821 |

新隔离目录为`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_SEQUENCE5_R7_20261105T091410Z`及`S07_R2_TWODOMAIN_R3_20261105T091410Z`。两包原样解压、逐文件SHA/LF/语法通过；S07原R2内包及34项候选/模板保持。S02只读引用原S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt，前后bytes=271979513、SHA=4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846、原mtime_ns一致。

新增S00执行层只做有限只读编译器查询、准备、单次提交/观察、收集和原件复核，不修改包内候选、比较器、数值门槛或共享环境。实际完整参数保存在各job的submission.command.json；使用`--env none`，S02运行新外层`run_s02_strict_once.sh`后exec原`payload/run_s00_seq5_job.sh strict`，保留原780+15秒内层。附带C++查询外层最多45+2秒，不进入模型或改变其环境，整体仍受900秒调度时限约束。

S07严格使用已核包装器和原启动方式，登录profile仅在login02使用。登录侧观察器预先就绪、每秒查询状态，RUNNING后立即单次调用原publisher，exit0；计算端原生CCS_JOB_ID、request/raw/ready、nonce/SHA/30秒新鲜度、主机/76核/内存/时限/exclusive及逐核sysfs全部核验。没有从JSON设置作业环境变量，没有临时修包或等待人工回复错过交接窗口。

## S02五步结果

实际结果为PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY，completed_steps=5、comparison_failures=0。每步1063项，共5315项全部通过：loss、输入梯度、原完整输出、参数梯度、更新后参数、相对各自上一步的增量、AdamW moments/step覆盖保持原判据。

原sequence_gate在集群exit0；下载后对同字节源和完整回执再执行原标准库gate，exit0。该复核不重跑Torch。两侧模型/AdamW隔离实例保持同一对象，初始来源相同，逐步摘要链及step=0→1→2→3→4→5连续、每步输入/参数梯度清理合格；24个有序同PID CPU36检查点完整，实际Torch intra-op=36、可见TID掩码均在选定36核。每步实际KML调用reference=149、candidate=197。

仍是固定16_adjacent/pre、完整B64/fp32、原mean/AdamW、同一冻结合成case重复五次，沿用R4/KML/OMP36/MKL36/OpenBLAS1/cores/close/HBM0。只接受这份固定case五步严格数值证据，待S02/协调专项审核；不代表新数据、收敛、稳态或生产接受。没有运行五步内存；严格checker保留两个模型及比较快照，其RSS不作为训练内存或收益。

原结果及CPU/lineage/全部5315指标位于`downloaded/S02/received/payload/evidence/sequence5_2040203_strict/checker/result.json`；command/stdout_stderr/exit_code、原source/case检查、集群gate及终态都在同一完整包中。

## S07实际到达范围与失败

新包装器实际授权交接成功；R2当前job身份检查6项及原probe检查16项在Linux全部通过，无跳过，包括原Linux组清理检查。环境导入检查exit0，实际Torch2.7.1+cpu、Gloo构建可用，路径及加载库SHA已记录，无LD_PRELOAD。该environment命令按原实现仅单线程导入，不等于通信/每域36计算通过。

随后执行原run_checks.py，在首个normal case失败：

- `checks.json`为FAIL、cases=[]、error=`normal communication failed`。
- normal监督器reason=`child_failed`，两个worker PID为2321423/2321424，exit_codes=[-15,1]、all_reaped=true；此非故障注入，不能把非零当预期通过。
- rank1实际Torch intra-op=36，最后阶段init_process_group，错误`RuntimeError: Wait timeout`，日志定位到dist.init_process_group/ProcessGroupGloo。尚未记录实际rank/world/backend完成值。
- rank0最后持久化阶段before_framework，未写出实际Torch36、backend或初始化完成记录，随后被监督器TERM清理，日志为空。没有足够证据判断其当时具体停在导入、库身份采集还是其它位置，不能断言它本身超时、Gloo不支持或rank1超时的根因。
- 两rank均未到all_gather_identity/broadcast/all_reduce；crash、collective-timeout、watchdog目录均未生成，全部NOT_RUN，不能称三项故障注入通过或“4项中通过0项后故障通过”。
- S00外层run_checks_receipt.json记录exit1、无外层超时、owned_sessions覆盖本次父/worker、remaining_live=[]；调度终态PID清空。其前三步正常退出/清理回执完整，失败步独立回执也保留，未因summary.steps只含成功项而丢弃失败步证据。

S07本轮没有通信接受，更没有同步训练/吞吐结论。停止后未增大超时、调参、修改候选或重提。下一步把normal双方启动记录及进程组初始化失败交S07原会话/总协调复核；如需任何修订或新job，另行核包安排。

## 有限C++定位

在既有S02 job内、严格入口之前执行只读查询。原生PATH未设置，按Python默认可执行搜索范围查询：g++、c++、clang++均无命中；C驱动gcc命中`/bin/gcc`。原gcc的`-print-prog-name=g++`和`-print-prog-name=cc1plus`每条5秒上限、均exit0，返回相对名字，未命中可读的绝对C++工具路径，因此没有C++ ELF/SHA/依赖身份可记录。

原stdout/stderr、精确命令及identity.json位于`downloaded/S02/received/cpp_readonly/`。没有全盘扫描、安装、编译、换环境或申请额外资源。这只保留该有限范围未定位可用C++的结论，不推断平台没有C++；没有可据以提出具体S06_CXX路径的证据，本轮不修改或重跑S06。

## 完整证据

本轮根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\sequence5_s07r3_20261105T091410Z`。

| 原始完整job包，位于downloaded/<任务>/ | bytes / 文件数 | SHA256 |
|---|---|---|
| S02/JOB_2040203_full_evidence.zip | 229688 / 66 | 19e54562b321f160099d8edc1c398a369b6dadb6cbc6ec389fc7c9fd0bea0259 |
| S07/JOB_2040233_full_evidence.zip | 249710 / 101 | 82a82866ad2572113d6b85f13995009d8948c8d3bca66b23e3b3d413546dbc7d |

外层ROUND_RESULTS.zip为483625bytes/7项，SHA=1c3734cefbd643ea83a4e31c132e665e19c58928acc0b8b1bbd04309959780a2，附ROUND_RESULTS_receipt.json。各内包全部ZIP项与received逐字节一致，COLLECTION_S00分别65/100项远端原mtime_ns/bytes/SHA核验；源/case前后身份及执行层身份一致。mtime作为元数据保存，不宣称Windows解压后文件时间等于远端原mtime。

机读复核为REVIEW.json；本地原gate日志为S02_sequence_gate_local.stdout/.stderr。ROUND_REQUEST.json、PROTECTED_BEFORE.json、ROUND_UPLOAD.zip、downloaded/ROUND_REMOTE_INDEX.json及REMOTE_DEDUP_BEFORE.json保留安排/提交顺序/去重依据。candidate/audit_sequence5_s07_delivery.py只核档案及原gate，不运行模型/通信。旧S06失败包、旧报告、两份原候选包保护哈希均未变。

收口：自己的SESSION_STATUS.md、ROUND_DELTA.md及本轮ARTIFACT_SHA256.txt。只交本轮变化和上述证据给总协调，不更新其它任务状态或共用暂存区。
