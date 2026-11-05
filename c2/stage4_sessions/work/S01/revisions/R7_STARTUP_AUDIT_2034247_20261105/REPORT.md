# S01：R7 真实集群启动结果专项复核

日期：2026-11-05（Asia/Shanghai）。
状态：**READY_FOR_REVIEW / ACCEPTED_BOUNDED_CPU36_MODEL_STARTUP / NO_S01_BLOCKER_FOR_S02**。
审核对象：**job2034247 / cn21340**，接受候选`S01_CPU36_MODEL_R7_20261104`。

## 1. 结论

**接受本次有限36核完整启动，可推进S02数值对照。**

从运行器角度，未发现阻止S02继续的具体问题。原R7包、实际投递代码/接口、同job预检和三轮模型来源一致；实际Torch intra-op=36，全TID边界与证据完整性通过，三轮exit0且无超时。完整54文件、18个checkpoint、1683份原始父线程采样均复核；原样R7离线汇总PASS，与远端summary整个JSON结构/数值完全相同。没有靠删除检查或修改结果求PASS。

本结论关闭S01对这一次有限启动的专项复核门槛；按R7_PASS_NEXT_S02，S02新36核包仍须自身核验后，由S00执行既定的一组C2/KML严格数值对照。本结论不表示S02数值已经通过，也不解锁训练内存/HBM/多域性能或生产部署。

## 2. 前置条件、身份及审核范围

先读用户指定的三份现有材料；第一路径中`REVIEW\.md`按实际存在的`REVIEW.md`读取：

- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\CPU36_R7_STARTUP_RESULT_REVIEW.md`
  SHA256 `f150e3e88e55f31224ab7d25009a6ccde4cb9cfe22e4c62257d2d034e0aca1f5`。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\CPU36_R7_STARTUP_REPORT.md`
  SHA256 `f72e77d1fc07ee74a5fc0df3a931daa1d00c97f691e603d8e24570bdaaa3e7aa`。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\R7_PASS_NEXT_S02.md`
  SHA256 `9a6f232bf2bbb6abe4d21d33441f3bd03f69e7945e81f8a8e5f0a46891079ac6`。

只读完整证据根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247`。包SHA256 `cf5db0ce6ac812c719b5879e26c68955f26fbfa23154a6bea96f31962bcb9755`。ZIP共54文件，CRC通过、成员无重复，全部逐字节等于received；其中53项逐一匹配COLLECTION_S00的SHA/bytes及有效原mtime_ns，第54项为COLLECTION_S00自身。received无缺失或额外文件。

原S01 R7 ZIP SHA256 `288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c`；11成员全部与实际回传payload逐字节相同，9项SOURCE_MANIFEST逐项相符，原R7交付索引也重新核对通过。四个实际源码SHA与manifest和每轮结果一致：

| 源文件 | SHA256 |
|---|---|
| runner.py | `e04a703b7da429e3d85607f66b2c4d18cb3306b9a6320f92d7fd3be41539674a` |
| cpu36_contract.py | `3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d` |
| s4_models.py | `ebc31ca6f726df886e147da7ff4766b32142a6b83c7336f15e6c1a52e25e1461` |
| kml_ops.py | `e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26` |

pre_submit_checks保留真实Linux的3项LF/bash -n及4份Python语法通过记录，14项初始payload哈希收据有效，collection.changed_payload_files为空。两份NPZ、shim及KML实际身份与同job引用/manifest相符；NPZ/共享库二进制未回传，因此本复核依据原远端SHA收据及模型内已加载库SHA，未伪称在本机重新读取远端库或数据。

所有新写入仅在`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_STARTUP_AUDIT_2034247_20261105`。对S00该证据目录、原R7整个目录和上述三份材料，共88个既有文件记录并复核SHA、字节数、mtime_ns；审核后全部不变。未改R7包、S00证据、协调文件或模型代码。

## 3. 实际环境、授权边界与启动链

现有调度证据djob_final：SUCCEEDED、jobExitCode=0，cn21340；2026-11-05 03:00:01–03:01:52 UTC（北京时间11:00:01–11:01:52），111秒。单域分配38核、24576MB，resLimit.mem同为24576、jobWallClockLimit=900。原提交参数和一次性启动marker与job2034247匹配。

预检/manifest的拓扑receipt一致：allocated/domain=0–37，各为独立物理核；selected=0–35、reserved=36/37。同job新鲜CPU36_PREFLIGHT_1793847610939262653.json=PASS_IMPORT_ONLY，host/job/source/input/library/CPU及C组环境与正式manifest对应；其文件SHA也被正式manifest冻结。三轮命令均为确切selected36的`numactl --physcpubind=0,...,35 --membind=0`，使用原S00 R4 venv解释器和本job s4_models.py。

环境固定`OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 OMP_PLACES=cores OMP_PROC_BIND=close`。实际模块为torch2.7.1+cpu、numpy1.26.4；模块路径、已加载KML/shim/OMP/BLAS路径及SHA均在review.json和预检原件中，逐checkpoint与冻结引用一致，已加载OpenMP max API均36。

配置完整限定为单域、16_adjacent/pre+dec、B32/fp32、KML_LINEAR1、CKPT0/HBM0、三轮REPS1，原cases s0322p0/p1，LEGACY_TIMING_ONLY。没有改loss/模型/优化器/随机语义或数值阈值；这不是S02固定case严格等价检查。

本窗口没有SSH、提交作业、环境探测、框架导入预检或模型前后向。只在本地导入已核验的stdlib运行器/合同模块并重放summarize，不加载torch/numpy/KML。

## 4. 线程、退出及完整性专项结果

| 轮次 | PID | exit / timed_out | 监督窗口秒 | checkpoint | 父快照 | 独立TID / 同时观测最大TID | Torch intra / inter |
|---|---:|---|---:|---:|---:|---|---|
| 1 | 519622 | 0 / false | 33.212764 | 6 | 571 | 36 / 36 | 36 / 608 |
| 2 | 522759 | 0 / false | 31.752686 | 6 | 547 | 36 / 36 | 36 / 608 |
| 3 | 525865 | 0 / false | 32.864886 | 6 | 565 | 36 / 36 | 36 / 608 |

每轮6个checkpoint严格依次为before_framework、after_framework、16_adjacent_after_warmup、16_adjacent_after_pre、16_adjacent_after_dec、publish，共18项。结果run.cpu36与sync/thread_rank0.json一致，context与父上下文、manifest同run/job/host/rank/round；PID与父状态一致，checkpoint顺序及时间、结果mtime均属于该次进程窗口。三份模型结果/三份状态齐全，无缺域、缺轮、额外结果或ABORT；每轮公开status与sync/status完全相同，诊断错误匹配为0。

before_framework调用线程掩码是完整0–35；框架初始化后实际Torch intra-op全部为36。after_framework快照可只出现1个TID，预热后各checkpoint为36个TID；这与线程池延迟建立相符，不把初始化早期TID数误当实际线程配置。调用线程最终[0]是真实close绑定结果，符合子集合同，不应要求其等于全集。interop608按元数据原值记录，不能解释为608个活动工作线程。

逐行检查571/547/565、合计1683份原始JSONL：complete=true，threads非空，vanished/errors为空，TID唯一有效，全部非空affinity均为selected36子集；无预留核或未授权核。采样时间在对应父监督窗口内且递增，每份均包含主PID。直接由raw重建每TID的掩码历史，与status.thread_monitor逐项一致；样本数也完全一致，incomplete_samples=0、violations=[]。

三轮parent/worker始终时间有序，exit0、timed_out=false，均低于180秒单轮上限；作业exit0且111秒低于900秒。数值字段均完整、有限、正值，fps×step=B32；源码/配置/案例和torch版本一致。

本次是成功运行证据，没有触发真实TERM/KILL/超时故障；不据此新增“Linux所有失败恢复分支已实测”的结论。R7原检查代码和既有正负测试身份未变，本次不重复测试或故障注入。

## 5. 离线汇总与描述性短测

仅在本S01新目录的`replay_received`副本，用COLLECTION_S00记录的原始mtime_ns恢复文件时间；Windows最大舍入90ns。received原件时间未改。原样R7 summarize返回PASS、errors=[]，输出与远端summary及S00 offline_summary整个对象精确相等，不仅比较PASS字符串。

短测pre三轮21.607143216/21.799005416/22.254458423 fps，dec三轮8.484277768/8.537697741/8.590253427 fps；原规则spread分别2.9575505%/1.2413093%，都低于5%。只支持这一次REPS1单域启动及描述性波动检查，不接受正式速度/长期稳定性或加速收益。legacy peak_mem_GB字段不是规范配对内存测量，也不是HBM或训练内存收益。

## 6. 阻断判断与后续边界

**阻断问题清单：空。接受本次有限36核完整启动，可推进S02数值对照。** 不需为S01门槛再次提交相同启动作业、环境测试或修改R7版本。

S02按R7_PASS_NEXT_S02准备36核同PID守卫新包，保持固定case、B64与micro32×2、fresh AdamW、KML严格模式和原数值阈值；包核验后由S00执行一组16_adjacent/pre参考/候选对照。原Windows数值FAIL不会被本报告覆盖。旧4/38核包不能继续作新执行入口。

观测限于已保存checkpoint和约50ms采样，不能证明线程生命周期每一瞬间或精确in-region team成员。legacy demo已知16电极目标错配仍在；它不阻断启动合同，但不能作科学数值对照输入。S02必须继续使用既定固定case，严格数值门槛通过前训练内存/HBM验收继续等待。本报告未授权32电极、decoder数值扩展、多域/整节点/DDP或生产部署。

## 7. 证据索引

本专项审核产物绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_STARTUP_AUDIT_2034247_20261105`。

| 本目录文件 | 内容 |
|---|---|
| REPORT.md | 本专项审核结论 |
| review.json | 机器可读复核：身份、环境/实际库、逐轮PID/TID/退出及无阻断结论 |
| audit_existing.py | 现有证据逐项核对与原样汇总脚本；不调用main/preflight或模型 |
| offline_summary.json | S01副本重放结果，精确等于远端summary |
| inputs_before.json | 88项受保护输入的SHA/bytes/mtime_ns起点 |
| inputs_integrity.json | 受保护输入原字节/大小/时间未变 |
| ARTIFACT_SHA256.txt | 本目录文件哈希索引，含REPORT和副本（排除索引自身） |

关键原始证据绝对路径：

- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\COLLECTION_S00.json`：完整性及真实远端mtime_ns。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\djob_final.json`：调度终态、实际资源、退出。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\pre_submit_checks.json`：源码/载荷SHA与真实Linux提交门槛。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\payload\evidence\CPU36_PREFLIGHT_1793847610939262653.json`：同job预检。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\payload\output\reports\s01_cpu36_2034247\manifest.json`：正式合同/来源/配置。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\payload\output\reports\s01_cpu36_2034247\r1_d0.json`、`r2_d0.json`、`r3_d0.json`及对应`.status.json`：三轮结果与退出。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\payload\output\reports\s01_cpu36_2034247\sync_r1\rank0.threads.jsonl`、sync_r2/sync_r3同名文件：全部1683样本；各sync内thread_rank0.json/cpu36_d0.json/commands.json/marker亦核对。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\received\payload\output\reports\s01_cpu36_2034247\summary.json`：原远端PASS，与独立重放完全一致。

本次结论全部来自上述当前重新核验的回传文件；历史记忆只用于提醒隔离/合同边界，没有用旧状态替代本次实测。
