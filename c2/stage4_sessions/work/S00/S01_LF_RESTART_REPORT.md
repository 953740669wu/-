# S00：S01 LF 修正版完整启动小试复测

日期：2026-11-04（Asia/Shanghai）。状态：**READY_FOR_REVIEW / FULL_MODEL_ROUND_COMPLETED / RUN_REJECTED_CPU_AFFINITY / STOPPED_AFTER_ONE_JOB**。

## 1. 结论

按用户本轮明确授权，用已核验的LF修正版在新目录提交了且只提交了一次 **job2026450**。作业在 **cn21340** 于 **22:03:41–22:06:22 +08** 实际运行161秒。分配为 **38 CPU、24576MB（24GiB预算）、显式同值内存限制、900秒时限、单NUMA域、独占节点**。

实际S01导入/源码/输入/库预检PASS；第1轮完整模型执行了16_adjacent/pre和dec的预热、前向、反向及AdamW更新，产出模型JSON，模型子进程退出 **0**、未超时。随后原样运行器按既有合同拒绝该结果：

```text
summary.status = FAIL
errors = ["r1_d0: actual CPU affinity mismatch"]
jobExitCode = 1
```

期望集合为CPU **0–37**，模型发布结果时记录的**调用线程**affinity为 **[0]**。环境OMP_NUM_THREADS记录38，但模型描述torch.get_num_threads()为 **1 threads**。因此本轮启动链/绑定验收**不通过**，不采纳计时为38核性能基线；子进程退出0不能覆盖汇总FAIL。

严格遵守失败即停止：只完成第1轮，未启动第2/3轮，没有新作业重试、四域/整节点、S02或训练内存测试。后续交S01分析绑定和线程证据，由总协调审核，不在S00改运行器或弱化检查。

## 2. 前置范围、源码与远端提交门槛

使用原样LF包SHA256：`747f9c36354136afa3383a3d836c7e3db7568a043d1712fb2f03765068b4ec5e`。其中实际入口pilot_s01_startup.sh SHA256：`72ba04253bc4b68446d642a70bcc0571ee926b71bc81e553c1a385d91dc1709f`。

新远程根：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S01_20261104T140206Z_LF_RESTART/
```

本地仅写work/S00。没有覆盖S01/S02目录、共享项目、NPZ或冻结manifest。S01的8个接受源码文件SHA未变；库及两份legacy输入在远端只读来源复制至本次payload，18个实际payload文件全部哈希冻结，运行结束仍全部相同。

提交前在**实际远端文件**上完成：包SHA、逐文件SHA、4项sh/env的CR字节数=0及真正Linux bash -n exit0。4项为实际入口、candidate/run_node16.sh、runtime_preflight.sh和cluster_runtime.env。结果先保存pre_submit_checks.json；提交程序再次逐字节核对所有18个payload文件，并再次执行无CR与bash -n检查，全部成功之后才调用dsub。submit_once.marker用独占创建阻止该目录重复提交。

2026356原失败包、日志、清单和PILOT_EXECUTION_REPORT.md均按本轮开始前的SHA重新核实不变；其远端原包也未改。本次目录、作业和证据与旧失败独立。

## 3. 实际环境、配置、命令与成本

账号dengqingtian，SSH入口10.44.9.4:22→login10，仅在计算节点运行模型。解释器：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

Python3.9.9、torch2.7.1+cpu、numpy1.26.4；共享torch_kml和KML只读路径、实际加载库SHA均在本次预检RESULT.json。OMP_PLACES=cores、OMP_PROC_BIND=close；初始环境OPENBLAS_NUM_THREADS=1、MKL_NUM_THREADS=1。模型子进程OMP_NUM_THREADS=38，numactl实际命令指定--physcpubind=0,...,37 --membind=0；原样记录在sync_r1/commands.json。

完整原架构encoder 37.995777M、decoder 29.416449M；fp32、B32、累积1、KML_LINEAR1、LINEAR_DTYPEfp32、CKPT0、HBM0、GN0、SAMPLING0、REPS1。每轮两次pre和两次dec预热，再各1次计时更新；计划3轮但第1轮汇总失败后停止。原seed0、默认初始化、原损失/优化器语义；legacy s0322p0/p1各2帧，只是历史计时兼容输入，已知16电极目标语义限制未解决。

调度请求固定cpu=38,mem=24576MB，-RL mem=24576MB、-T900、numa[count=1,distribution=pack]；实际resAlloc和resLimit与请求相符。子进程约147.636秒；job开始/结束壁时161秒≈**0.044722节点小时**。此前S00五作业35秒另计，本任务累计196秒≈0.054444独占节点小时；GPU小时0。djob另记wallclockDuration160秒，是调度统计口径，与开始结束差161秒并列保留，不互相覆盖。作业最终PID字段为“-”。

本次提交命令、UTC时间、stdout/stderr原样保存在submission.json。没有自动重试。

## 4. 正确性与绑定核查

| 检查 | 本轮结果 | 状态 |
|---|---|---|
| 远端18文件SHA及4项LF/bash语法 | 提交前通过、提交时复核通过，运行后无改动 | PASS |
| 原样S01实际导入/输入/库预检 | torch/numpy/kml_ops/model模块及legacy身份通过；预检记录CPU0–37 | PASS |
| 真实完整模型pre/dec及AdamW运行 | 产出第1轮JSON；child exit0、timed_out=false | 已执行；不是数值等价验收 |
| 运行器绑定合同 | manifest期望0–37；发布结果时调用线程affinity=[0] | FAIL，job exit1 |
| 后续轮次/规模停止 | 只有r1_d0.json，sync_r2/r3均不存在 | 已停止，无自动扩大 |
| 固定输出/loss/梯度/一步参数数值对照 | 本小试不是等价checker，没有参考/候选数值对照 | 未运行，不填零误差 |

S01审核需区分：os.sched_getaffinity(0)在Linux读取的是调用线程CPU集合，OMP_PROC_BIND=close时不能仅据[0]断言整个线程池/作业只用了1核；本轮也未采集模型全部线程的affinity，不能直接反向宣称绑定已经正确。torch描述1线程与OMP环境38也不是同一个指标。原始djob保留CPU时间和CPU利用率，不把它们改写成线程数。

建议S01核对实际计算进程中Torch intra/inter-op线程数、所有相关TID的CPU集合、OpenMP运行时与OMP/MKL/OPENBLAS变量优先关系，并界定“进程授权集合”与“线程绑定集合”的验收合同。**这些是定位方向，当前没有因果隔离结果**。S00不删除affinity检查、改环境取PASS或另起作业验证假设。

## 5. 原始计时与内存（无效配置的诊断记录）

| 配置 | 完成轮/计划轮 | pre step秒 / fps | dec step秒 / fps | 原peak_mem_GB | 退出/结论 |
|---|---|---|---|---|---|
| cn21340，单域16_adjacent，B32/fp32/KML，CKPT0/HBM0 | 1/3 | 7.777790465 / 4.114279003 | 35.513466248 / 0.901066648 | 7.651592 | child0；runner/job1，affinity合同失败 |

这些数值仅供诊断，不与历史38线程成绩计算加速比，也不作为三轮稳定性或新性能基线。模型字段peak_mem_GB来自ru_maxrss/1e6（历史换算口径，十进制GB），不是GiB；无HBM。本次没有同主机参考/候选内存配对，不是S02训练内存测试，不能声称优化收益。djob memMax=7771原字段及单位语义保留在回执，不与模型RSS或24GiB额度混称。

## 6. 接受条件、审核交接与停止点

本轮完成了用户授权的一次恢复和完整证据回传，结论为**启动验收FAIL，停止等待S01/总协调审核**。LF/语法问题已越过，实际模型训练可运行，但38核绑定/线程合同尚未通过。完整数值等价、三有效轮、四域/整节点、新性能基线及第二主机仍未验收。

本次没有提交S02，也没有执行训练内存测试；S02此前Windows严格数值失败保持有效。按用户本轮限制，即使有可运行的S02包也不在本轮提交。

审核入口为本报告、机器可读review.json与完整证据zip。本轮只在S00准备交接文件，不修改S01/总协调工作目录或代替其写接受结论。

## 7. 完整证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/s01_lf_restart_2026450/full_evidence.zip：完整19文件，SHA256 `1403bb4c5ba5032eb16df5aab4b3acd7836b6edd692db4ccc2b5626df0cbe87d`，已与远端摘要及包内每个文件SHA核对。
- evidence/s01_lf_restart_2026450/received/job.log：完整作业stdout/stderr。
- evidence/s01_lf_restart_2026450/received/payload/output/reports/s01_startup_2026450/sync_r1/rank0.log：完整模型stdout/stderr。
- 同一reports/s01_startup_2026450目录的manifest.json、r1_d0.json、r1_d0.status.json、summary.json及sync_r1全部marker/commands/status：原始结果、退出与barrier证据，未删改。
- evidence/s01_lf_restart_2026450/received/djob_final.json：完整调度终态、请求/分配/限制、时间和jobExitCode。
- evidence/s01_lf_restart_2026450/received/pre_submit_checks.json、submission.json、submit_once.marker：提交门槛、实投命令及唯一提交。
- evidence/s01_lf_restart_2026450/received/payload/evidence/RUNTIME_PREFLIGHT_20261104T140342308313Z/RESULT.json：本次实际导入/输入/库预检。
- evidence/s01_lf_restart_2026450/received/collection_status.json：全回传文件大小/SHA清单及运行后代码不变核查。
- evidence/s01_lf_restart_2026450/review.json：本地独立复核与停止状态。
- evidence/s01_lf_restart_request.json：本轮资源、唯一提交范围及旧失败证据冻结SHA。
- evidence/executed_packages/S01_job_2026356.zip和s01_pilot_job_2026356.json：旧失败原件，保持不变。

当前全部交付物SHA另见ARTIFACT_SHA256.txt；完整日志未截断，原始NPZ与共享源码未作为日志包回传。
