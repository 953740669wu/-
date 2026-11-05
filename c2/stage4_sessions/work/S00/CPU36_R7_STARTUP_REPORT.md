# S00：R7 CPU36 单域完整启动小试

日期：2026-11-05（Asia/Shanghai）。状态：**READY_FOR_REVIEW / R7_BOUNDED_STARTUP_PASS / REMOTE_AND_OFFLINE_SUMMARY_PASS / FORMAL_ACCEPTANCE_PENDING**。

## 1. 结论

按CPU36_RUNNER_R7_REVIEW.md和用户本轮授权，原样使用R7新包、新目录、新作业，且仅提交一次。**job2034247 / cn21340 / SUCCEEDED / jobExitCode=0**，北京时间 **11:00:01–11:01:52**，实际111秒。分配38核、实际计算集合36核/预留末2核、24576MB及同值内存限制、900秒上限；16_adjacent pre/dec、B32、fp32/KML、HBM0/CKPT0、三轮REPS1均完整执行。

同job新鲜导入预检PASS_IMPORT_ONLY；三轮模型子进程全部exit0、无超时。实际Torch intra-op均36，close绑定下调用线程保留真实[0]；全部阶段及父监测TID记录在选中0–35内，没有越界或采集缺口。运行器最终summary=**PASS**，pre/dec短测三轮描述性波动分别 **2.95755% / 1.24131%**。

本地独立副本按真实远端mtime_ns恢复后，原样R7汇总同样返回PASS，三轮指标一致。**这完成本次有限启动/合同检查，仍待S01和总协调审核；不是生产部署、正式数值等价、性能/稳定性或模型效果验收。** 本轮没有S02或训练内存测试，没有扩大配置或重试。

## 2. 接受来源、包身份及提交门槛

接受版本S01_CPU36_MODEL_R7_20261104；已读总协调复核、R7接口、启动脚本、C组环境和SOURCE_MANIFEST。27项交付索引、本地ZIP内11文件及9项payload/source清单均核对。实投ZIP SHA256：

```text
288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c
```

实际入口interfaces/run_s01_startup36.sh SHA256：eae64b092b9a62525a6362f6ea93a96019266a79bb2070e36fb107eb8d91fde1。源码/环境/接口逐文件身份见回传SOURCE_MANIFEST.json，没有现场改代码、删除检查或更换阈值。

新远程目录：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/MODEL_CPU36_R7_20261105T025806Z/
```

本地和远端均仅写S00。库与两份legacy NPZ由已核实的S00来源远端就地只读复制；原数据、共享库、S01/S02目录、正式manifest均未修改。14个实际payload文件（含库/输入）全部冻结SHA，运行后14个仍一致。

提交前远端实际包/9项清单及全部文件SHA、3个shell/env字节无CR、真正Linux bash -n、4个Python文件在Python3.9编译检查全部通过。提交程序在调用dsub前再次核对14文件SHA和3项LF/bash -n，成功后才提交。submit_once.marker及R7的startup36_once.marker分别记录唯一提交/启动。

连接时SSH发现主机密钥变化，因此最初在认证前停止。用户明确回复已通过可信渠道核对新指纹一致后，才按确切指纹匹配并保存独立known_hosts记录，仍使用StrictHostKeyChecking=yes。新ED25519指纹为SHA256:DUcxv6m2GsdQszU1xemf9oRdmk+a8RCSAZJf7Sr9rjw，本次落点login02。旧known_hosts、旧作业包/报告/结果保留不变；没有关闭身份校验或记录密码。

## 3. 环境、资源、配置、命令与成本

账号dengqingtian，经10.44.9.4:22→login02提交；q_hpcai、exclusive=true、cn21340执行。解释器：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

实际Python3.9.9、torch2.7.1+cpu、numpy1.26.4。R7固定C组：OMP_NUM_THREADS=36、MKL_NUM_THREADS=36、OPENBLAS_NUM_THREADS=1、OMP_PLACES=cores、OMP_PROC_BIND=close；真实Torch intra-op=36，interop照实记录608，不把它当实际608个工作线程。KML/shim/OMP/BLAS实际模块/库路径和SHA来自本job新鲜预检，逐轮checkpoint与父监测/汇总继续核对，不复用旧job预检。

调度resAlloc cpu=38、mem=24576；resLimit.mem=24576、jobWallClockLimit=900。单NUMA域0的38个CPU各为独立物理核心，allocated=0–37，selected=0–35，reserved=[36,37]。父监督器收窄到选中集合；模型命令显式numactl --physcpubind=0,...,35 --membind=0。

实际dsub参数为cpu=38,mem=24576MB、-RL mem=24576MB、numa[count=1,distribution=pack]、-T900、--env none；实投入口：

```bash
env S01_RUN="$RUN/payload" bash "$RUN/payload/interfaces/run_s01_startup36.sh"
```

该入口执行同job新鲜--preflight，随后使用引用启动三轮；单轮180秒、barrier120秒、模型入口外层780秒TERM/15秒KILL，总job仍900秒。完整命令/stdout/stderr/UTC提交时间见submission.json。

模型架构/优化器/损失/原随机语义不变：encoder约37.995777M、decoder约29.416449M，seed0、默认初始化、AdamW lr1e-4；每轮完整pre/dec前向、反向和更新，预热各2次，正式各REPS1。输入s0322p0/p1各2帧，B32通过索引重复采样；标记LEGACY_TIMING_ONLY，已知16电极图像目标语义问题仍在，不能做科学效果结论。

本次调度开始结束差111秒≈**0.030833独占节点小时**。此前S00七作业266秒另计，累计八作业377秒≈0.104722节点小时，GPU小时0。失败作业仍计入，不按计算核心数/608缩小独占节点成本。最终调度PID字段为“-”，所有本轮子进程已退出。

## 4. 模型、线程及退出证据

| 检查 | 本轮结果 | 状态 |
|---|---|---|
| 同job导入预检 | PASS_IMPORT_ONLY；job/host/source/input/library/CPU/environment匹配，实际Torch36 | PASS，范围为导入 |
| 三轮结果/状态/身份/时效 | r1/r2/r3各1个域，3份模型JSON与3份状态齐全，源码身份一致 | PASS |
| 模型checkpoint | 每轮before_framework、after_framework、warmup后、pre后、dec后、publish共6项；总18项 | PASS |
| 实际Torch及TID边界 | 框架后各checkpoint intra-op=36；全部非空TID掩码属于selected36；调用线程[0]真实保留 | PASS，限保存证据 |
| 父监测 | 各轮571/547/565份快照，共1683；incomplete_samples=0、violations=[] | PASS，限采样范围 |
| 子进程/超时 | 三轮exit0，timed_out=false | PASS |
| 最终汇总/作业 | summary PASS；job SUCCEEDED、exit0 | PASS，有限启动合同 |
| 离线复核 | 独立副本恢复真实mtime_ns后原样汇总PASS；逐轮sum完全一致，spread差异≤1e-12 | PASS |
| 固定权重输出/loss/梯度/AdamW数值等价 | 本次不是参考/候选等价checker | 未运行 |

实际all-TID身份、mask历史、阶段时间/PID、库和模块身份、环境及父监测raw JSONL全部保留。当前检查不是对线程生命期每一瞬间或精确in-region team人数的证明，也不把总TID数/掩码并集/omp_max作为单独通过条件。

## 5. 三轮原始结果（启动短测，不是正式性能基线）

| 轮次 | pre step秒 | pre fps | dec step秒 | dec fps | legacy peak_mem_GB | 子进程退出 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 1.480991711 | 21.607143216 | 3.771682266 | 8.484277768 | 7.979972 | 0 |
| 2 | 1.467956881 | 21.799005416 | 3.748083028 | 8.537697741 | 7.898300 | 0 |
| 3 | 1.437914120 | 22.254458423 | 3.725152031 | 8.590253427 | 7.841360 | 0 |

原运行器按(max-min)/mean计算pre波动2.9575505%、dec波动1.2413093%，均低于其5%短测阈值。仅单域、同job三轮、REPS1且增加线程观测，有效范围是启动/数据完整性与旧A1描述性波动；不能单独接受正式速度、长期稳定性、第二主机、四域/整节点或DDP结论。没有与历史38核失败/旧4核配置计算同配置加速比。

peak_mem_GB沿用源码ru_maxrss/1e6的历史字段口径，未作规范GB/GiB换算，不是HBM测量，也不是S02参考/候选独立轻量训练内存配对；不能宣称内存优化收益。

## 6. 完整回传、离线时间属性与审核停止点

完整 **54文件**证据包已回传并逐项核对SHA/bytes/原始mtime_ns，包括job资源/终态、原样R7源码、源码清单、一次性marker、预检、manifest/summary、逐轮模型JSON/状态、全部thread checkpoint、父监测JSONL、命令、日志及本轮已有全部文件。运行后14文件SHA不变，历史2026356/2026450/R6报告和包SHA未变；原始NPZ/共享库二进制不回传。

received原件没有改写。离线验证仅在S00/tmp独立副本按COLLECTION_S00真实远端mtime_ns恢复时间；Windows文件系统最大舍入90ns，记录于review.json，远端原始ns值仍完整保留在元数据。原样R7 summarize返回PASS，轮次指标一致，避免对未恢复mtime的解包件制造stale/future误判。

本轮授权范围已完成，停止等待S01和总协调审核。即使启动PASS也不自动放开S02、训练内存、HBM、32电极、四域/整节点、正式性能或生产部署。旧38/4核包继续历史禁用；R7实投包保持原样，不擅自修改模型入口或生产默认。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/r7_cpu36_2034247/full_evidence.zip：完整54文件，SHA256 **cf5db0ce6ac812c719b5879e26c68955f26fbfa23154a6bea96f31962bcb9755**。
- evidence/r7_cpu36_2034247/received/job.log、djob_final.json、submission.json、pre_submit_checks.json、COLLECTION_S00.json：完整作业日志、实际资源/退出、提交门槛及时间/哈希清单。
- evidence/r7_cpu36_2034247/received/payload/evidence/CPU36_PREFLIGHT_1793847610939262653.json：同job新鲜导入/线程/模块/库预检原件。
- evidence/r7_cpu36_2034247/received/payload/output/reports/s01_cpu36_2034247/：manifest、summary、三轮模型JSON/状态及sync_r1/r2/r3全部thread/context/command/日志/状态。
- evidence/r7_cpu36_2034247/offline_summary.json、review.json：独立副本汇总与本地核验。
- evidence/r7_cpu36_startup_request.json：本次接受身份、资源/范围、新目录及旧证据冻结SHA、用户确认的主机指纹。
- execution_packages/S01_CPU36_MODEL_R7.zip：原样接受R7实投包。
- candidate/audit_r7_delivery.py、collect_cpu36_model_r7.py：可重复的本地完整性/独立时间副本汇总及本轮收集程序。
- evidence/known_hosts_10.44.9.4_20261105_confirmed：独立保存的用户已核实主机公钥，旧记录保留。
- ARTIFACT_SHA256.txt、evidence/source_integrity.json、delivery_validation.json：完整当前索引和108原始项目文件不变终检。
