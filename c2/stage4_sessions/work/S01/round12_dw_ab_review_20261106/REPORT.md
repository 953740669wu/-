# S01 R12 专项复核报告

结论：**PASS_FOR_ENGINEERING_R12_AB，review_complete=true，无前置阻断项。** S00可核对本轮固定审核原件和同SHA后直接执行唯一作业，无需用户中转。审核对象仅本轮冻结候选、实际target→strict5→两独立perf25门槛链和新部署；未重复R11完整审核或旧矩阵。

## 列块ABI、边界和实际导入

候选仅在fp32 CPU/实际KML、ta=True/tb=False、beta0/out=None/acc32False且(m,n,k)=(512,2048,13312)时命中。原连续性/同dtype断言保持；新增stride/element_size/4字节对齐/输出storage不alias输入断言。两个N=1024块均完整K=13312，A地址不变，B/C偏移分别0和4096bytes，lda512/ldb2048/ldc2048，alpha1/beta0。A/B/C最大float索引6815743/27262975/1048575在原buffer内；两块C列区间互斥、覆盖最终C，无K分块或部分梯度累加，无大输入复制。

独立AST删除唯一新增if后与原baseline完全一致；唯一diff逐字一致，其它函数/forward/dX/bias/gb与fallback保持原路径。实际target一次baseline/一次candidate，使用canary、输入前后相等、完整14参数指针/leading dimension与原比较器；拒绝Python替身_sgemm。candidate由明确路径importlib加载，baseline来源有精确路径检查；SOURCE_SHA256前后核验和输出import SHA绑定这两个实际模块，未加载R10候选。

run_job.sh使用env-i清除PYTHONOPTIMIZE，冻结环境不重新设置；外层拒绝sys.flags.optimize/PYTHONOPTIMIZE，子解释器仅-B，没有-O/-OO，因此已交断言在此启动链中启用。

## 实际数值门槛链和计数

冻结shell set-euo pipefail串行执行target→strict→perf_baseline→perf_candidate。target收据SHA/source/host/job/selected36进入strict；strict收据SHA/source/descriptor/host/job/CPU进入两个新性能进程。各阶段还比较实际KML/OpenMP/shim映射及SHA、Torch/NumPy文件版本和环境；原固定descriptor与SOURCE绑定的初始化/25步参照补齐数据身份。原descriptor/归一化、37995777参数初始权重SHA、seed0、每步frame/order/mask均拒绝漂移。target不读取语料，数据身份在strict/perf入口强制验证。

严格阶段两侧各连续5更新，比较h/voltage/coarse、三个loss、两个输入梯度、全部参数梯度/更新参数/相对初始delta、AdamW step/exp_avg/exp_avg_sq及buffers。冻结tests/check_equivalence.py字节未改：tensor max_abs<=2e-5，state<=2e-6；同时要求L2 relative<=2e-6（原reference norm<=1e-8例外保留），shape/dtype/finite与exact step检查保持；不是loss-only。每步并保留原job首5 loss门槛。strict的双模型/hook时间不作性能对照。

每次更新都强制核以下计数，candidate不能误用旧native149或删门禁。它们仅表示此KML路径的直接调用，不表示Torch全部BLAS。

| 侧别 | logical | target logical | native SGEMM | target full | target tiles | dispatch |
|---|---:|---:|---:|---:|---:|---:|
| baseline |149|12|149|12|0|0|
| candidate |149|12|161|0|24|12|

性能两侧各独立新进程25更新，前5预热、后20观察，无profiler/输出hook；两侧相同诊断、finite/状态/暴露检查，保留训练调用、诊断、加载、壁钟分项以及process-lifetime RSS/HWM。各侧必须保存checkpoint并完成0额外更新恢复；任一侧不足25或恢复失败均无完整A/B。最多60个完整模型更新、仅一对，不能缩步、换tile或追加试验。

## 新部署、预算、退出与收集

新目录 /home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z/payload；旧2043445/2048959/2049454及旧marker被拒绝。review_gate强制本轮PASS、review_complete、10项SHA、resources和workload；submit_once独占x创建新marker，一次dsub，模糊提交不重试。S00提交前须按COMMANDS重查实际队列/现有记录和同SHA，S01没有代做远端查询。

单节点单NUMA、38分配/实际36留末2、24576MB DDR且limit同值、exclusive/HBM0/retry0。原生调度身份/物理core/DDR门禁及CPU36合同保持；框架前绑定36，逐检查点采集全部TID边界和实际Torch intra-op=36，缺证据/越界/错线程数拒绝。OMP/MKL=36、OPENBLAS=1，调用线程较窄合法子集不误拒绝。

START从外层import开始，原生gate与整个应用共用绝对START+840；外层计时器和run_phase绝对截止优先于内层840/入口720后备，不能先前置再额外840或逐阶段重置。统一TERM15/KILL15，总清理<=30且最晚START+870，调度900留30收尾；PR_SET_CHILD_SUBREAPER及PID/start_ticks跟踪所属跨session后代并reap，不杀不相关进程。非零/数值失败立即停后续；超时/不足预算记INCOMPLETE，不续跑或缩短25。

r12_outcome核四阶段原协议/成功状态、60更新、两侧frame/mask/init、import/CPU/library/native计数、原metrics及恢复；inspect再核原步骤日志/账本/收据SHA。缺阶段、后续越过失败、错计数或任一不完整不判成功。收集保留原错误、target/strict/两侧perf/dw_ab、runner/调度/退出/清理和部分账本；含糊暴露不声称未使用。权重留远端，仅回传路径/bytes/SHA，收尾须确认所属PID清空。

## 本轮证据及限制

独立核02代码ZIP 27成员/26源、14复用、Python3.9 AST/LF/CRC、唯一diff；新25步参照与原job2043445步骤日志逐项一致，1600索引无重复。核作者5项数学/ABI加4项运行契约原件、30项差0比较及导入证明；它们仅本地假CBLAS/native Torch证据，没有重跑这套数学检查。

核00部署33 ZIP成员（32文件+1目录）/30索引、7原封复用helper、10项执行绑定；源码/包/索引逐字与冻结原件一致。核00本地9项、Linux登录9项fixture及元数据/旧9项身份/固定16单元36文件SHA收据。S01只对冻结副本导入stdlib review_gate并验证实际拟发布记录，未提交作业或运行矩阵/模型；77份冻结输入最终复核均无漂移。

本轮未现场触发Linux信号/超时故障清理，不能用fixture冒充已实测。实际KML局部门槛、完整Encoder严格对照、CPU/TID现场表现和两侧性能结果均待唯一作业。预算内可能INCOMPLETE，必须照原规则停止。正式split/subject UNKNOWN，无val/test；本审核不建立正式划分，不作效果、稳态收益或生产接受。

## 精确绑定与交接

| 执行绑定 | SHA256 |
|---|---|
| code_package_sha256 | 44232f7627cfbcf59fb721acd23af46aed8fa790b20fe743a3c9886717ec4de4 |
| code_source_manifest_sha256 | f61b8db309b8dad5853c7916d371b4484af609bd7610c096846bb21a7ac866bd |
| deployment_package_sha256 | a3f81b40e58e63bde612c95cd04fcb7a2d054746f5977371bc58310ca8beccc8 |
| descriptor_sha256 | b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6 |
| candidate_sha256 | 8955f1c0bdf8b2b5d233b3eafb321d30ae0dbd184ba595959680434aedafd6ea |
| r12_contract_sha256 | 16f19bab92e57e2730d801dab5fb012c32d53a37bf4011e516a5467fe5f378df |
| reference_epoch25_sha256 | 572ce966e3de8b54ff234755a6595a0a730dd0920fcd371a234cc7798f641444 |
| task_card_sha256 | bad48674eee0bfb41be0f5fbd2e2a0807e29dce31bc0e789263fc49665a5bec3 |
| reference_first5_sha256 | 2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8 |
| deployment_source_manifest_sha256 | e51c425815ad7f3ae0a48b27adbae389271f1b2b0201e031c44ee11ff41c0189 |

基线SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26。全部输入路径/bytes/SHA见FROZEN_INPUTS.json，逐项复核见code_review.json和deployment_review.json；固定S01_REVIEW.json发布后不热改。

只写本任务目录及自身SESSION_STATUS.md、六行ROUND_DELTA.md；原源/门槛/数据/历史审核不改，未操作共享Git暂存/提交/推送。精确可归档清单见ARCHIVE_FILES.json，排除ZIP、frozen副本、语料/权重/环境；S00直接读取固定审核执行并跟踪原job，失败停止无自动重试。S01本轮前置复核结束，不后台监控。
