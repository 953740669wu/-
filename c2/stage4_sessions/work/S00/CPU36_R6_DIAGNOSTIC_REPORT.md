# S00：S01 R6 CPU36 有限线程诊断回传

日期：2026-11-04（Asia/Shanghai）。状态：**READY_FOR_REVIEW / DIAGNOSTIC_DATA_COMPLETE / S01_ANALYSIS_PENDING / MODEL_RESTART_NOT_ACCEPTED**。

## 1. 结论

依据总协调CPU36_DIAGNOSTIC_REVIEW.md及本轮用户授权，原样执行且只执行一次S01_CPU36_THREAD_DIAG_V1。**job2026725 / cn21338 / SUCCEEDED / jobExitCode=0**，北京时间 **22:55:23–22:56:33**，70秒。五组小算子worker均退出0，无诊断停止原因；收齐五组数据，未在保存的全部阶段/采样中发现CPU越界。

分配38核，实际选择同域 **0–35共36个物理核心**，预留 **36、37**；24GiB预算（resAlloc.mem=24576、resLimit.mem=24576），job时限300秒，外层270秒TERM/5秒KILL，单case45秒。没有扩大资源或重试。

观察到A（MKL=1负控）的Torch intra-op为1；B移除MKL及C/D/E各组均为36。close组调用线程掩码[0]，D关闭绑定后调用线程掩码0–35；全部保存的线程掩码仍在selected36内。这些是本环境实测现象，**DIAGNOSTIC_DATA_COMPLETE不是完整36核模型/性能或生产配置验收**。最小环境/合同修订交S01分析，总协调审核。

本轮没有完整模型、NPZ、optimizer、HBM、S02或训练内存测试；2026356/2026450历史报告、包和结果保持不变。

## 2. 前置依据、源身份和提交门槛

读取CPU36_DIAGNOSTIC_REVIEW、CPU36_POLICY及S01 R6的REPORT、DIAGNOSTIC_PLAN_FOR_S00、driver、worker、CPU合同和冻结清单。接受包SHA256：

```text
1db8b1818a387a0c3dd404bf1efd40a3aba777bad7d7c4226379ef369ad9fd81
```

S01 R6报告SHA256为202ddee714b14af4c6dc12c24c04b1ce9142a765a81016836f6c8ffb270c58e3。21项交付索引、本地包的12个文件、6项SOURCE_MANIFEST均核对；没有修改R6代码、源报告、候选或阈值。

新远程目录：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/DIAG_CPU36_R6_20261104T145326Z/
```

仅写本地/远端S00目录。远端实际包和解包文件SHA、全部Python语法、两个shell/env字节LF和真正Linux bash -n通过，保存pre_submit_checks.json。提交程序在调用dsub之前再次核对12个文件SHA及LF/bash -n，使用独占submit_once.marker阻止同目录重复提交。

登录节点初次附加依赖检查不能stat计算节点的/opt/HPCKit KML路径，因此没有在login节点宣称库存在/加载成功。解释器、numpy/torch/shim的可见路径与SHA在pre_submit_checks记录；KML可用性最终由计算节点五个worker真实加载和调用证实。没有在login节点执行Torch或算子，也没有修改库路径来绕过检查。

## 3. 环境、命令、资源与成本

账号dengqingtian，经10.44.9.4到login10提交，计算节点cn21338，q_hpcai、exclusive=true。Python3.9.9解释器：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

实际torch2.7.1+cpu、numpy1.26.4；KML、shim和两组OpenBLAS、OpenMP库的真实映射、API及SHA逐阶段保留在worker.json。只通过RTLD_NOLOAD查询已加载库；真实KML gemm没有用torch.mm替代。

实际调度cpu=38,mem=24576MB，-RL mem=24576MB、numa[count=1,distribution=pack]、-T300、--env none。实投命令及stdout/stderr在submission.json，核心入口为：

```bash
timeout --signal=TERM --kill-after=5s 270s bash "$RUN/payload/diagnostic/run_thread_diagnostics.sh"
```

五组新进程串行，numactl --physcpubind=0,...,35 --membind=0，观察器也缩至36核。CPU receipt保存全部授权、域拓扑、physical siblings、选中和预留列表；该域38个CPU分别为独立物理核心。每组OMP_NUM_THREADS=36、OMP_PLACES=cores，不调用torch.set_num_threads。A与串行NumPy是显式诊断负控，不能作为正式36线程模型配置。

仅执行小型torch逐元素、512² NumPy dot、1024² KML GEMM，各活动阶段约0.5秒用于采样；不计算吞吐。此次调度开始结束差70秒≈**0.019444独占节点小时**；此前S00累计196秒另记，累计7作业266秒≈0.073889节点小时。GPU小时0，最终调度PID字段为“-”。

## 4. 五组完整结果和边界

下表的Torch intra-op及调用线程mask取最终阶段，导入后的其它阶段值相同。所有组Torch inter-op配置均报告608，这不是已经创建/使用608个计算线程的证明。

| case | MKL / OpenBLAS / bind | Torch intra-op | 调用线程mask | samples行数 | worker退出 |
|---|---|---:|---|---:|---:|
| A_mkl1_negative | 1 / 1 / close | 1 | [0] | 698 | 0 |
| B_mkl_unset | unset / 1 / close | 36 | [0] | 529 | 0 |
| C_mkl36 | 36 / 1 / close | 36 | [0] | 505 | 0 |
| D_bind_false | 36 / 1 / false | 36 | 0–35 | 485 | 0 |
| E_openblas36 | 36 / 36 / close | 36 | [0] | 520 | 0 |

独立核对全部 **2737行samples**、30个阶段快照：全部有完整线程读取标记，各记录的非空CPU mask均属于selected36，assessment的boundary_violations均为空。五个command显式使用同一36核列表，五个worker均记录OPERATORS_COMPLETED_NOT_MODEL_ACCEPTANCE及model_executed=false；退出原因均null，SUMMARY为DIAGNOSTIC_DATA_COMPLETE。

这是对保存证据的检查，不声称20ms采样覆盖线程生命周期的每个瞬间，也不把总TID数、mask并集、CPU tick推进或omp_max单独当精确in-region team人数证明。

## 5. 供S01分析的运行时差异与限制

- A/B/C仅按计划改变MKL设置，Torch默认intra-op从A的1变为B/C的36；该差异是本次真实C2数据，应据此提出环境修复，而不是只把OMP日志改成36。
- D相对C仅关闭OMP绑定，调用线程mask从[0]变为36核全集，而Torch intra-op仍36。close下单核TID mask在本轮仍留在授权36核内；不能沿用旧“每个TID等于全集”的检查，也不能据此直接接受正式模型。
- 两组OpenBLAS必须分清：末阶段NumPy自带libopenblas64_p-r0-17488984.3.23.dev.so API在**全部五组（含E）都报告1**；torch附带libopenblasp-r0-1a7698bc.3.29.so线程API报告36。E把OPENBLAS_NUM_THREADS设36并未让NumPy库API报告36，具体初始化/绑定原因待S01解释，不能写成E已修好NumPy线程数。
- 活动采样中某些阶段可见多个TID tick推进，但可能含其它线程池活动/自旋及phase切换影响；不能直接把某阶段active_tids归因于该算子的精确team。D部分短阶段的active_tids少于36也不足以单独判定线程配置失败。原始phase、API、线程状态和CPU tick全部回传。
- KML/OMP末阶段omp_get_max_threads在A为1、B–E为36；探针在parallel region之外读到omp_get_num_threads=1不是内核实际team的独立证据。A的KML阶段仍观察到多TID活动，需结合全部runtime身份解释，不能将MKL变量认定为所有运行时行为的唯一原因。

本次没有模型输出/loss/梯度/AdamW数值对照、模型启动验收、训练内存或性能比较，不报告加速比或生产环境选择。

## 6. 回传完整性、审核与停止状态

已回传完整 **54文件**，包括原样R6 payload、job分配/终态、完整job/worker日志、CPU receipt、五组command/worker/samples/assessment/phase、SUMMARY、原始COLLECTION及S00外层COLLECTION。R6 COLLECTION含39项原始记录，S00 COLLECTION同时保存各文件原始远端mtime_ns、bytes和SHA；逐项核对两层清单一致，运行后的12个源文件SHA均不变。

原始mtime_ns保留在元数据中，没有重写received副本时间、没有凭进程时间伪造mtime或重跑汇总取得PASS。后续离线复核若需恢复mtime，应在独立临时目录按真实元数据恢复；本次原件不改。

本轮授权执行完成，停止等待S01及总协调分析。尚无接受的36核正式模型运行器/生产线程配置，旧38核/4核模型包继续历史禁用；不因诊断数据收齐自动重启完整模型、S02或内存测试。只在S00回传证据，不代替S01/总协调写接受结论。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/cpu36_r6_2026725/full_evidence.zip：完整54文件，SHA256 **af5b01f9a7890d0bcaeb8c989e30a12ad64f65a6c40c5e7663d8d2f05d5b22b1**，与远端摘要及包内全部文件核对一致。
- evidence/cpu36_r6_2026725/received/job.log、djob_final.json、submission.json、pre_submit_checks.json、COLLECTION_S00.json：完整作业日志、退出/资源、实投及远端门槛/时间属性。
- evidence/cpu36_r6_2026725/received/payload/diagnostic/results_20261104T145524411199Z/：完整五组结果目录，含cpu_receipt.json、SUMMARY.json、COLLECTION.json及每组command/worker/samples/assessment/phase/log。
- evidence/cpu36_r6_2026725/review.json：本地独立核对、case观测表和停止状态。
- evidence/cpu36_r6_diagnostic_request.json：本轮授权范围、时限、资源、源包/逐文件SHA及旧证据冻结SHA。
- execution_packages/S01_R6_CPU36_diagnostic.zip：本次实投的原样接受诊断包。
- candidate/collect_cpu36_diagnostic.py：仅收集本轮终态证据及原始mtime_ns，不执行算子。
- ARTIFACT_SHA256.txt、evidence/source_integrity.json、delivery_validation.json：当前交付物索引及108原始文件不变检查。
