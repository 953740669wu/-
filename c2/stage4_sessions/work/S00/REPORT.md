# S00：阶段四基线与限定集群执行回传

日期：2026-11-05（Asia/Shanghai；历史冻结/作业时点保留）。
状态：**READY_FOR_REVIEW / S02_R5_NUMERICAL_FAIL / S03_C_SAFETY_PASS / BOTH_TERMINAL**。
首次交接证据范围：REMOTE_VERIFIED / HISTORICAL_RECOMPUTED / NEW_CLUSTER_BENCHMARK_NOT_RUN。该标记只描述首次交接，不覆盖后续实际执行。

本轮按S00_NEXT_S02_R5_S03_C_20261105顺序完成两项，均使用新目录/新job、分配38核/实际36留2核、24576MB及同值限制：

- S02 job2034953/cn21338，11:50:49–11:51:18+08，900秒上限，checker/job exit1，FAIL_ORIGINAL_CRITERIA；1063项指标中95项失败，7同PID checkpoint及447次真实KML GEMM证据完整，未改阈值/重试。
- S03 job2034987/cn21338，11:54:58–11:55:00+08，300秒上限，job exit0；冻结源25项15通过/10预期失败、runner exit1，候选25/25及独立.so/ELF/依赖构建通过。清除S02预加载，未启用真实HBM或模型。

完整证据分别41/54文件，SHA/bytes/原始mtime_ns已核对，两项终态PID均为空，无重试。报告入口S02_R5_C2_STRICT_REPORT.md、S03_C_SAFETY_REPORT.md。本轮共31节点秒（含数值失败），累计S00十作业408秒。历史R7/R6/2026356证据未变。S02数值门槛和训练内存/HBM仍未通过；S03有限C通过不替代它们。

R7完整启动此前已由S01及总协调接受，无S01阻塞；本轮没有重复R7或Windows模型实验，没有生产部署或共享改动。下方原始baseline和过往测试保留各时点，最新状态以本段及新报告为准。

## 1. 结论

S00初始源码/远程/输入/历史结果交接已被总协调接受；R7三轮36核完整启动证据已被总协调及S01复核通过。本轮继续获准的一次S02严格数值和一次独立S03 C安全检查，结论分别为**数值FAIL**与**限定C检查/独立构建PASS**，不能互相替代。未修改生产默认、阶段二/三、冻结输入或数值阈值。

S02与S03完整结果、范围、资源和退出见各自新报告；CASE固定文件未重新生成或本地复制，源包原样。原始108个项目文件终态SHA复核不变。

关键结论（初始基线历史证据，不冒充本轮新性能）：

- 成功登录dengqingtian@10.44.9.4，落点login10；共享项目可读不可写。当前账号的既有作业不能当作S00分配资源。项目拥有者作业查询返回Permission denied，不能声明服务器无作业。
- 远程模型/KML/HBM/shim源码、生产冻结s2/s3/s6与本地归档SHA256一致；s1在指定远程位置缺失或不可读。manifest核实为11,900单元、1,190,000对、119个case，全部记录同一代码/配置标识；未独立遍历所有样本，真实subject split仍缺。
- 共享启动器在核查期间发生变化。17:00快照为ea27…，17:09快照为0da6…；后者新增faulthandler和故障关键词。两个快照的Python汇总段都与归档相同，缺域、过期文件、退出状态及barrier风险仍在。以本任务带时间戳副本及SHA为版本依据，不把共享路径当作不可变基线。
- 取回135份历史逐域JSON并重算540条域/工作负载记录、48条轮次/工作负载记录。B64/preferred第2轮仅15/16份JSON，**四项工作负载该轮均无效**；原报告的三轮PASS不能保留。DDR B32虽48/48份JSON齐全，16-dec波动5.607%失败；HBM B32只有两轮，16-pre波动9.387%，均不能作为正式稳定性通过。
- 总吞吐掩盖慢域：DDR B32的32-pre第2/3轮合计20.863/20.885 fps，但16×最慢域仅2.394/2.266 fps，最慢单步213.904/225.991秒。这个参考仍不包含DDP通信。
- 实际demo为两个文件各2帧，总共4帧。已用payload哈希证实：**两处demo的images均等于32电极源单元，且不同于16电极源单元**。16电极目标对齐有实际证据问题，不能作为科学训练正确性基线。保留它只为复现历史计时，S00不修改数据。
- GPU只有历史B64/bf16参考，CPU为fp32。32-pre完整域历史DDR B64约31–33 fps对应GPU约1/7；HBM B32约21–22对应约1/10，必须分开，不能称同配置公平加速比。

## 2. 前置条件与执行范围

读取阶段四sessions README、S00任务卡、REPORT_TEMPLATE、根README、STAGE4_HANDOVER、STAGE4_C2_PLAN、C2_OPTIMIZATION_REPORT及相关生产/源码文件。仅写本任务work/S00；原始108个本地文件终态SHA复核不变。初次冻结时无Git仓库，使用25个逐字节副本和显式哈希清单；本轮共享目录外部新增Git及5个快照说明，已单独登记，S00未操作Git。共享源码、生产数据、manifest、其他任务目录未改；首次证据交接没有创建远程文件；本次补充仅在当前账号S00/ENV_*及PILOT_*独立目录落探针、隔离NumPy/venv、S01原样预检包与本轮恢复包，未覆盖共享部署或S01/S02目录。

本地任务根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00`。

基线定义：

1. **模型/运算源码参考**：S00_LOCAL_ARCHIVE_20261104，baseline/s4_models.py和baseline/kml_ops.py与远程现有源码同哈希；不是已经接受的完整训练运行。
2. **历史计时兼容输入**：共享opt/s4下已哈希的两个demo文件；保留原来的图像语义以对照历史，不能据此做科学效果结论。
3. **运行器证据**：归档a21a…、17:00远程ea27…、17:09远程0da6…分别保存/记账。candidate/run_node16_isolated.sh是归档版仅改路径的准备入口，尚未执行训练，不能替代S01接受运行器。
4. **正式后续比较**：固定上述模型/输入/精度/批量，并使用S01接受的可靠运行器；输入图像语义调整应另记数据协议版本，不能静默沿用旧计时或准确率结论。

| 文件/版本 | SHA256 |
|---|---|
| s4_models.py | 9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2 |
| kml_ops.py | e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26 |
| HBM源码 | edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15 |
| shim源码 | f9e28e0ce2a3bdeca53eebc27fdd941c3235b4bee5ace250766875708e727388 |
| 归档run_node16.sh | a21aafcd1a3384f4ab07b146f24f5ebcf0b2a1b25eb35b725e8d26db9c655979 |
| 远程17:00启动器 | ea27c594dd61865dfbbd67e3bdda216fc8a63df4acb2cb363807be52d8f9ccaf |
| 远程17:09启动器 | 0da6c46de4e4f7ac9694ba966af9ee23a4b63227137fea72f9c99b7e62f73e41 |
| 远程sample_foreign.py，仅依赖哈希 | 0a42121514a547c6195b0f2ac336849eea5e073b8b32bd29c5a535c900cc2242 |

生产s2/s3/s6、s1本地、共享库、输入和配置等完整SHA详见source_sha256.txt、baseline_manifest.json及remote_source_manifest.json。共享库只核查二进制哈希，未重新构建，不能证明历史运行使用的就是当前二进制。

最小修改：模型和allocator零改动。candidate/launcher_paths.diff仅改变源码/输出/preload路径；build_isolated.sh只在当前账号自己的S00目录构建，不覆盖共享sw。未来远程目录为`/home/share/dengqingtian/opt/stage4_sessions/S00/<unique_run_id>/`，首次交接未创建；本次已创建四个独立ENV_*目录用于环境探针，见补充报告。当前远程启动器对归档及两次快照之间的diff均归档。

## 3. 环境、复现方式与成本

| 项目 | 本次证据及限制 |
|---|---|
| 本机 | DESKTOP-54BJCD6，Windows AMD64，Python3.11.9；系统Python无torch/numpy。pypdf只安装于本任务tmp用于读取VPN手册 |
| 连接 | dengqingtian@10.44.9.4 → login10；交互密码认证，密码未落盘；环境补充会话曾返回Unknown process id，所有S00已提交计算作业有终态证据 |
| 时间 | 初次本地冻结14:44+08；远程详细审计17:00起；最后源码快照17:09:02+08，读前后哈希相同。只保证该快照时点 |
| 调度器 | /opt/batch/cli/bin/dsub、djob、dnode、dqueue；q_hpcai已核实。17:00当前账号运行作业2024892/2015576；均非S00新作业 |
| 权限 | 共享/home/share/songzhenlong/eitfm可读不可写；djob查询songzhenlong返回255/Permission denied。login10上该账号有T/Ts/Z状态python进程，仅进程名/状态，不能据此判断计算节点训练任务 |
| 运行时 | 首次只查分发元数据；补充job2026223在cn21417用S00独立venv实际导入torch2.7.1+cpu、numpy1.26.4，Python3.9.9/aarch64。解释器/依赖绝对路径见COMPUTE_ENVIRONMENT_REPORT.md |
| 库 | 当前HBM .so SHA=f981a205e0773c311c7905e4193adbce03b1efc17b0f73b1cbab24c98905c840；shim .so SHA=a52c4da1a87b1a65b11121ecab2b8d0ca3fd2a03a5c92422873592381a92dd73；本次已记录shim/KML/OMP实际映射及15库SHA；尚未证明完整模型KML/OMP算子数值与性能 |
| 工具/硬件 | login10 gcc10.3.1及numactl存在；cn21417实际host_cpu_count608，但job只授权CPU0/4096MB。整机MemAvailable约445GiB不是额度；cgroup文件不可读，硬限未独立读出。未验证HBM放置 |
| 语法 | 远程bash -n当前17:00启动器退出0；本任务构建及隔离启动器通过远程stdin的bash -n，均退出0；未编译或执行训练 |

输入为s0322p0/p1各2帧：images=[2,64,64] float16，v_ref/v_cur=[2,208]或[2,928] float32，J=[208或928,4096] float16。训练使用的图像和电压均finite；最小参考归一化分母分别约1.4071/13.3003，图像全局abs max=0.033203125，均非零。J只核查shape/dtype/哈希，未做全finite扫描。文件读前后SHA稳定。

模型：12层、width512、8头、FF2048、dropout0；U-Net通道128/256/256/512。32_skip4实际skip=5。入口seed0、torch默认初始化，无checkpoint；权重跨16-pre/16-dec/32-pre/32-dec持续更新。预训练为masked voltage MSE+coarse image MSE；解码器为扩散噪声MSE，encoder也更新；AdamW lr1e-4。完整契约及mask分母见INPUT_CONTRACT。

显式配置为DDR B32/membind、HBM B32/membind和独立DDR B64/preferred。CPU fp32、KML_LINEAR=1、LINEAR_DTYPE=fp32、CKPT=0、GN=SAMPLING=0、每belt无条件2次pre+2次dec预热、正式5次计时、计划3轮。历史四域试验REPS=3、仅1轮。38线程为通常设置，HBM历史部分域跳过忙核，实际线程分布已保留逐域JSON。

每进程batch32/64、累积1；多进程各自训练，无DDP及有效全局训练batch。当前JSON未记录mempolicy/HBM/输入和库运行时哈希，配置来源需结合日志/文档，不能补写成已完全验证。

可复现本地命令：

```powershell
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\tests\test_baseline.py'
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\tests\test_remote_analysis.py'
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\analyze_remote_results.py'
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\verify_delivery.py'
```

首次交接没有新增作业；本次补充实际提交4个环境作业，均已结束，调度壁时合计34秒≈0.00944独占节点小时，含两次失败；GPU小时0；该环境补充阶段没有完整模型计时。环境输入副本/实际加载预检已执行；后续S01小试另有一次包装器早退1秒（job2026356），累计35秒≈0.00972节点小时，其后本轮授权的LF小试job2026450新增161秒，模型单域第1轮已完整执行但绑定FAIL，累计196秒；未扩大四域/整节点。CLUSTER_EXECUTION_PLAN给出S01/S02各最多15分钟的有限模型小试命令及停止条件，其中S01两次独立申请均终态失败（2026356包装器；2026450绑定合同），S02仍未提交；未预留后续资源。历史CKPT+HBM两轮runner wall为5401+5402秒，约3小时等待，不等于已核实的计费节点小时。RUNBOOK旧7.5节点小时预算仅为协调建议。

本轮实际成本：S02 29秒、S03 2秒，共31秒≈0.008611独占节点小时，失败计入；累计408秒≈0.113333节点小时。前项终态清理后才提交后项。两项Donau资源/源码/命令/退出原件均在各自完整证据包；S02已按审查补充在runtime重置PATH后重新加载Donau，原包不改。

## 4. 正确性

| 检查 | 预定度量/容差 | 结果 | 证据 | 状态 |
|---|---|---|---|---|
| 25副本及原文件 | 字节/SHA精确相同 | 副本一致，108原文件不变 | tests_after/source_integrity | 本地通过 |
| 生产s2/s3/s6 | 完整SHA精确匹配 | 三份一致；s1指定位置缺失或不可读 | remote_details/source_manifest | 远程核实，样本非逐值验收 |
| 208/928协议 | 顺序逐对完全一致 | s3/s4一致，32偏移5 | test_baseline | 本地通过 |
| demo shape/dtype/finite/分母 | 按原入口，不允许NaN/Inf/零分母 | 训练输入通过；J全扫描未做 | remote_details | 远程输入核查 |
| 16电极图像对应 | 应与自身源单元一致 | 两处都等于32源且不同于16源 | remote_context；remote_tests_after | **失败，训练语义限制** |
| 缺域/步时关系/三轮门槛 | 缺域即无完整域合计；fps=B/step相对容差1e-12 | 检查能拒绝r2缺域及人为破坏的fps；三轮门槛有效 | test_remote_analysis | 本地分析检查通过 |
| 当前汇总行为 | 与归档Python段精确比较 | 17:00及17:09快照均相同，归档的合成缺域/旧JSON误报仍适用 | 两个diff；remote_tests_after | 缺陷证据，运行器未修 |
| 计算节点环境和S01原样导入预检 | 实际import、tiny autograd、numpy桥接、源码/输入/加载库身份 | job2026223/cn21417通过；1CPU/4096MB，完整模型未运行 | compute_environment_verified.json、compute_env_job_2026223.json | 实测通过，范围有限 |
| S01真实模型启动与绑定 | 原38核集合/实际记录一致，逐域状态完整 | child0、job1，期望0–37/记录[0]，首轮FAIL后停止 | S01_LF_RESTART_REPORT及完整证据包 | **FAIL，不能接受计时** |
| S02 R5固定case严格对照 | 原比较器/阈值不变 | 1063指标/95失败；447实际KML调用；7同PID CPU checkpoint通过 | S02_R5_C2_STRICT_REPORT | **数值FAIL，非运行前提错误** |
| S03实际Linux C与独立库 | 冻结源预期失败、候选25项与独立构建 | 冻结源15通过10失败；候选25/25，.so/ELF/依赖通过 | S03_C_SAFETY_REPORT | PASS，仅C替身边界，无真实HBM |
| 输出/loss/输入与参数梯度 | 同权重/输入/mask/t/noise；max_abs、L2差/max(ref范数,1e-12)，实现前固定容差 | 真实模型已运行，但未做同权重参考/候选数值对照，不填零差；约1e-6仅历史fp32参考 | INPUT_CONTRACT/MEASUREMENT_REVIEW | 未运行 |
| optimizer一步/state_dict/dtype/NaN/缺失梯度 | 逐预期参数及状态检查；不能只拼接非None梯度 | 本轮完整模型pre/dec前反向和AdamW已执行；没有参考/候选数值等价断言，S02已有独立Windows数值FAIL | S01_LF_RESTART_REPORT及CLUSTER_EXECUTION_PLAN | 已运行训练，数值对照未运行 |

共10项本地检查通过，包含新增5项真实历史证据分析检查。源码一致及输入finite不能替代模型/optimizer数值验收。

## 5. 性能与内存

下表是**本轮取回历史JSON后重新计算**，不是新性能运行。每列是逐轮完整域合计fps；“-”表示缺域无效。逐域step、最慢/中位域、N×min、legacy RSS及诊断缺域值均见48行详细表/CSV。

| 历史配置/主机 | JSON/期望 | 16-pre逐轮fps | 16-dec逐轮fps | 32-pre逐轮fps | 32-dec逐轮fps |
|---|---|---|---|---|---|
| DDR B64 preferred，cn21346 | 47/48 | 242.9995 / - / 236.7516 | 75.9009 / - / 49.2896 | 30.9701 / - / 32.6976 | 20.5443 / - / 21.3309 |
| DDR B32 membind，cn21348 | 48/48 | 150.1445 /150.7477 /150.9733 | 43.0368 /45.5320 /45.5435 | 21.8474 /20.8633 /20.8848 | 17.0378 /16.5354 /16.7549 |
| HBM B32 membind，cn21338 | 32/32，仅2轮 | 289.5039 /318.0173 | 75.1124 /72.1242 | 21.9243 /21.4177 | 18.0083 /18.2626 |
| 四域DDR B32，cn21338 | 4/4，仅1轮 | 36.2001 | 16.4222 | 5.6070 | 4.5839 |
| 四域HBM B32，cn21338 | 4/4，仅1轮 | 125.6190 | 29.2716 | 7.2081 | 6.0137 |
| B64 CKPT HBM，cn21382，S01上下文 | 0/32 | 无 | 无 | 无 | 无 |

- B64第2轮缺d4整个JSON，四项均只有15域。旧汇总的232.97/49.32/31.07/20.44仅是成功域诊断合计，不能作为整节点数字；完整域仅两轮，不能保留原文16-pre/32-dec的三轮稳定性PASS。
- DDR B32三轮payload的波动为0.550%/5.607%/4.642%/2.995%；仅16-dec数值波动超5%。其它三个只是历史payload波动通过，逐PID退出码、运行时输入/库哈希未记录，不能升级为正式接受。
- HBM B32的两轮描述性波动为9.387%/4.059%/2.338%/1.402%；三轮门槛均不满足。原文9.4%及DDR dec5.6%已由原始JSON核实，不再用舍入表格的6.67%或9.21%代替它们。
- DDR B32与HBM B32整节点来自不同主机且线程排除不同，不是同主机A/B。四域DDR/HBM同主机但只有1轮，DDR有慢域，不正式接受3.5倍收益。
- 慢域不能被sum掩盖：DDR B32的32-pre第2/3轮N×min为2.3936/2.2656 fps，median step约23.689/23.685秒，slowest step约213.904/225.991秒；HBM B32第2轮相应为2.3911 fps及214.124秒。均不是实际DDP吞吐。
- 历史HBM逐域日志包含3800MB arena及约3.98GB bump高水位；不等于峰值驻留或访问流量。legacy peak_mem是累计ru_maxrss换算，HBM不计入RSS，不能把HBM行约3GB/13GB的RSS当总占用。累计申请字节不是带宽。未取得独立DDR/HBM驻留峰值。
- B64 CKPT HBM只有32份日志、0 JSON；摘要含SIGBUS及5401/5402秒等待，NODE16_DONE不证明成功。修复复测归S01。本次未读取后来c36/CKPT目录的内容，不能据其存在判断新方案通过。
- 135份JSON在读取前后哈希稳定，但缺少运行时冻结清单/逐域退出记录；mtime只可用于历史关联，不能证明这些文件从未被复用。原始JSON内容、哈希、mtime和有限日志摘要已保存。
- 新增单域首轮真实模型已执行但绑定FAIL，严格数值对照、四域/整节点A/B、3有效轮及第二主机未运行；没有同步训练或可验收的微算子/整步收益；本轮原始计时和ru_maxrss仅作为绑定失败的诊断记录，见S01_LF_RESTART_REPORT.md，不作为S02内存收益。

## 6. 接受条件与限制

本轮两项执行/完整回传已完成：S02数值FAIL需S02分析，S03限定C通过供S03/总协调审核；未扩大配置或修阈值、未做训练内存/HBM。此前R7的有限启动证据已接受，无须再次等待/重跑R7；以下旧历史接受边界以本段更新为准。

本地冻结、远程身份/权限/源码/输入/manifest、历史JSON完整性和重计算、版本漂移及输入语义问题已形成证据交接，**总协调已接受该交接；现有历史包仍不属于性能/科学正确性已验收结果。** 环境补充解决E01实际导入/解释器来源，E02/E03/E04/E05部分完成；输入来源、真实划分与模型验收仍待补。

没有生产集成或需要回退的共享改动。保留原始fp32、模型架构与数据字节；旧隔离shell保留路径准备用途；本次另提供S01/S02准备包及环境包装器，未修改其接受源码，模型正式运行前仍须按CLUSTER_EXECUTION_PLAN核查资源和门槛。17:09快照并不承诺之后共享文件不变。

| 后续任务 | 可直接使用 | 必须补齐 |
|---|---|---|
| S01 | R7已接受的三轮完整启动、CPU/线程/库及离线汇总证据；旧快照/失败仍保留 | 扩大规模/CKPT+HBM/第二主机另排期；本轮不重复R7 |
| S02 | R5固定case C2/KML严格对照41文件，原阈值1063指标/95失败，CPU/后端身份完整 | 分析95失败；不改阈值；数值/独立测量门槛未过，不开展训练内存/HBM |
| S03 | 实际Linux C原源缺陷/候选25场景/独立.so与完整54文件 | 真实内核/HBM、完整API/并发及生产集成仍未接受，另按后续范围安排 |
| S06 | U-Net架构与fp32原生conv/SDPA基线，历史工具限制 | 可复用S00实测NumPy/torch环境与库加载指纹；仍需对应算子/工具链实测及内存阶段评审 |

已明确分工：运行器修复/验收由S01负责，输入适配与内存优化由S02负责。环境、输入来源与权威subject split仍缺的资料、提供方和适用门槛已在PENDING_ITEMS.md列为15个跟踪项（E01已完成，其余14项OPEN/PARTIAL/条件待补）；资料提供由总协调协调，不由S00推定现有账号或文件即已获验收。

新性能基线先等待S01运行器验收，之后按单域→四域→整节点逐级推进，输入/运行环境适用前提和实际资源排期也需满足。RUNBOOK中的7.5节点小时仅为旧预算建议，不是已有作业授权；完整训练和第二主机另排期。本轮授权恢复一次LF小试已完成并因绑定合同FAIL停止，完整证据交S01/总协调审核；不追加作业或提交S02/训练内存。

用户已明确授权将限定证据保存work/S00，此依赖已解除。一次扩大到完整日志及辅助/环境源码的请求被自动审批拒绝，已收紧为日志摘要、哈希和输入统计后完成核查；该历史探查未返回那些全文、未绕过限制。本轮用户另明确要求回传新job2026450的完整生成日志/结果，已限于该新作业完成，不扩大到共享源码、原始NPZ或旧项目完整日志。

## 7. 证据索引

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00`。下列文件完整SHA256统一见ARTIFACT_SHA256.txt（不对索引本身循环哈希；tmp第三方依赖不计入）。所有原源码/副本另有独立清单。

| 证据 | 绝对路径 |
|---|---|
| S02 R5严格数值执行报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\S02_R5_C2_STRICT_REPORT.md |
| S02完整41文件证据 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s02_r5_s03_c_20261105\JOB_2034953_full_evidence.zip |
| S03有限C安全/独立构建报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\S03_C_SAFETY_REPORT.md |
| S03完整54文件证据 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s02_r5_s03_c_20261105\JOB_2034987_full_evidence.zip |
| 两项独立复核及实际消耗 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s02_r5_s03_c_20261105\review.json |
| R7完整启动与离线复核报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\CPU36_R7_STARTUP_REPORT.md |
| R7完整模型/线程/退出证据包 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\full_evidence.zip |
| R7三轮独立复核结果 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r7_cpu36_2034247\review.json |
| R6有限诊断完整回传报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\CPU36_R6_DIAGNOSTIC_REPORT.md |
| R6完整54文件/原始mtime_ns证据包 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\cpu36_r6_2026725\full_evidence.zip |
| R6五组独立复核 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\cpu36_r6_2026725\review.json |
| 36核执行登记与换包门槛 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\CPU36_READINESS.md |
| 36核目标/旧包禁用状态 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\execution_packages\NEXT_CPU36_EXECUTION.json |
| 本轮LF恢复及绑定FAIL报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\S01_LF_RESTART_REPORT.md |
| 本轮完整日志/结果/退出回执zip | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s01_lf_restart_2026450\full_evidence.zip |
| 本轮独立复核机器结果 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\s01_lf_restart_2026450\review.json |
| 本次S01失败停止/S02绑定修正 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\PILOT_EXECUTION_REPORT.md |
| 计算节点环境实测报告 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\COMPUTE_ENVIRONMENT_REPORT.md |
| 有限小试命令/资源/停止条件 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\CLUSTER_EXECUTION_PLAN.md |
| 可复用环境与库SHA/作业证据 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\compute_environment_verified.json |
| 准备包与逐文件SHA | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\execution_packages\PACKAGE_MANIFEST.json |
| S01准备包，未执行模型 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\execution_packages\S01_pilot_prepared.zip |
| S02准备包，内存阶段未就绪 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\execution_packages\S02_pilot_prepared.zip |
| 全交付物SHA256 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\ARTIFACT_SHA256.txt |
| 原始与副本清单 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\baseline_manifest.json |
| 原始SHA256 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\source_sha256.txt |
| 原文件不变终检 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\source_integrity.json |
| 远程详细证据，135份JSON及统计 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_details.json |
| 日志摘要、图像payload对比 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_context.json |
| 远程源码/依赖完整SHA清单 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_source_manifest.json |
| 17:09启动器快照 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_sources\run_node16_latest.sh |
| 17:00对归档diff | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_launcher_vs_archive.diff |
| 17:00对17:09 diff | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_launcher_1700_vs_latest.diff |
| 540条域测量表 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_domain_measurements.csv |
| 48条轮次测量表 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_round_measurements.csv |
| 含step/慢域/RSS的可读表 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_measurement_table.md |
| 波动与完整性判定 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_recomputed.json |
| 本地检查日志1 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\tests_after.txt |
| 本地检查日志2 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_tests_after.txt |
| 远程shell语法检查 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\remote_syntax_checks.json |
| 最终交付核查 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\delivery_validation.json |
| 显式配置 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\baseline_configs.json |
| 输入/数值契约 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\INPUT_CONTRACT.md |
| 可信度/精度/GPU说明 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\MEASUREMENT_REVIEW.md |
| 远程核查摘要 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\REMOTE_AUDIT.md |
| 可复现命令/资源门槛 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\RUNBOOK.md |
| 收尾待补清单及责任/门槛 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\PENDING_ITEMS.md |
| 已接受报告的逐字节快照 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\REPORT_ACCEPTED_HANDOVER_20261104.md |
| 已接受交接时的哈希索引 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\ACCEPTED_HANDOVER_SHA256_20261104.txt |
| 机器可读收尾状态 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\closeout_status.json |
| 隔离入口最小diff | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\candidate\launcher_paths.diff |

未向其它聊天发送消息或修改共享任务状态。总协调已接受证据交接；本次LF恢复已完成首轮真实模型并因绑定合同失败停止；完整19文件已回传，运行器/数值/性能未达验收。后续按PILOT_EXECUTION_REPORT、CLUSTER_EXECUTION_PLAN及既有恢复门槛继续。接受交接不等于已集成或性能通过。
