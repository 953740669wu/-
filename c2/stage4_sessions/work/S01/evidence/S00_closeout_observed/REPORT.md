# S00：建立阶段四可复现基线

日期：2026-11-04（Asia/Shanghai）。
状态：**ACCEPTED_HANDOVER / CURRENT_WORK_COMPLETE / RETEST_DEFERRED**。
证据范围：REMOTE_VERIFIED / HISTORICAL_RECOMPUTED / NEW_CLUSTER_BENCHMARK_NOT_RUN。

收尾确认：总协调已接受本次证据交接（依据用户在本聊天的明确确认）。待补资料已整理至PENDING_ITEMS.md；S01负责运行器修复/验收，S02负责输入适配与内存优化。新的性能基线等待S01运行器验收，再按单域→四域→整节点推进。S00本轮在文档交接后收尾，保留后续复测入口，不启动新实验。

## 1. 结论

已完成S00的源码冻结、远程版本核对、输入契约审查和历史性能证据交接，总协调已接受该交接；运行环境、输入来源和数据划分的剩余缺项及完成标准见PENDING_ITEMS.md。**没有性能优化或新训练计时，性能与数值基线尚未正式验收，未修改生产默认或数据。**

关键结论：

- 成功登录dengqingtian@10.44.9.4，落点login10；共享项目可读不可写。当前账号的既有作业不能当作S00分配资源。项目拥有者作业查询返回Permission denied，不能声明服务器无作业。
- 远程模型/KML/HBM/shim源码、生产冻结s2/s3/s6与本地归档SHA256一致；s1在指定远程位置缺失或不可读。manifest核实为11,900单元、1,190,000对、119个case，全部记录同一代码/配置标识；未独立遍历所有样本，真实subject split仍缺。
- 共享启动器在核查期间发生变化。17:00快照为ea27…，17:09快照为0da6…；后者新增faulthandler和故障关键词。两个快照的Python汇总段都与归档相同，缺域、过期文件、退出状态及barrier风险仍在。以本任务带时间戳副本及SHA为版本依据，不把共享路径当作不可变基线。
- 取回135份历史逐域JSON并重算540条域/工作负载记录、48条轮次/工作负载记录。B64/preferred第2轮仅15/16份JSON，**四项工作负载该轮均无效**；原报告的三轮PASS不能保留。DDR B32虽48/48份JSON齐全，16-dec波动5.607%失败；HBM B32只有两轮，16-pre波动9.387%，均不能作为正式稳定性通过。
- 总吞吐掩盖慢域：DDR B32的32-pre第2/3轮合计20.863/20.885 fps，但16×最慢域仅2.394/2.266 fps，最慢单步213.904/225.991秒。这个参考仍不包含DDP通信。
- 实际demo为两个文件各2帧，总共4帧。已用payload哈希证实：**两处demo的images均等于32电极源单元，且不同于16电极源单元**。16电极目标对齐有实际证据问题，不能作为科学训练正确性基线。保留它只为复现历史计时，S00不修改数据。
- GPU只有历史B64/bf16参考，CPU为fp32。32-pre完整域历史DDR B64约31–33 fps对应GPU约1/7；HBM B32约21–22对应约1/10，必须分开，不能称同配置公平加速比。

## 2. 前置条件与执行范围

读取阶段四sessions README、S00任务卡、REPORT_TEMPLATE、根README、STAGE4_HANDOVER、STAGE4_C2_PLAN、C2_OPTIMIZATION_REPORT及相关生产/源码文件。仅写本任务work/S00；原始108个本地文件终态SHA复核不变。无Git仓库，使用25个逐字节副本和显式哈希清单。共享源码、生产数据、manifest、其他任务目录未改；远程没有创建文件或部署候选。

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

最小修改：模型和allocator零改动。candidate/launcher_paths.diff仅改变源码/输出/preload路径；build_isolated.sh只在当前账号自己的S00目录构建，不覆盖共享sw。未来远程目录为`/home/share/dengqingtian/opt/stage4_sessions/S00/<unique_run_id>/`，本次未创建。当前远程启动器对归档及两次快照之间的diff均归档。

## 3. 环境、复现方式与成本

| 项目 | 本次证据及限制 |
|---|---|
| 本机 | DESKTOP-54BJCD6，Windows AMD64，Python3.11.9；系统Python无torch/numpy。pypdf只安装于本任务tmp用于读取VPN手册 |
| 连接 | dengqingtian@10.44.9.4 → login10；交互密码认证，密码未落盘；所有SSH会话正常退出 |
| 时间 | 初次本地冻结14:44+08；远程详细审计17:00起；最后源码快照17:09:02+08，读前后哈希相同。只保证该快照时点 |
| 调度器 | /opt/batch/cli/bin/dsub、djob、dnode、dqueue；q_hpcai已核实。17:00当前账号运行作业2024892/2015576；均非S00新作业 |
| 权限 | 共享/home/share/songzhenlong/eitfm可读不可写；djob查询songzhenlong返回255/Permission denied。login10上该账号有T/Ts/Z状态python进程，仅进程名/状态，不能据此判断计算节点训练任务 |
| 运行时 | /usr/bin/python3，3.9.9，aarch64；PYTHONPATH指向sw/torch_kml时元数据为torch2.7.1+cpu，同调用未找到numpy；未import torch，不能推断所有集群环境都缺numpy |
| 库 | 当前HBM .so SHA=f981a205e0773c311c7905e4193adbce03b1efc17b0f73b1cbab24c98905c840；shim .so SHA=a52c4da1a87b1a65b11121ecab2b8d0ca3fd2a03a5c92422873592381a92dd73；实际加载/KML/OMP配对未验证 |
| 工具/硬件 | login10 gcc10.3.1、gcc/g++/clang/numactl命令存在；归档有608核/DDR/HBM硬件记录。登录节点不能替代计算节点ISA、NUMA、动态库和内存实测 |
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

远程构建、输入副本/实际加载路径检查及1→4→16域准备命令见RUNBOOK；未执行。实际新增作业0、计算节点小时0、GPU小时0，无本轮性能超时。历史CKPT+HBM两轮runner wall为5401+5402秒，约3小时等待，不等于已核实的计费节点小时。后续7.5节点小时分门槛预算只是协调建议，尚未排期。

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
| 输出/loss/输入与参数梯度 | 同权重/输入/mask/t/noise；max_abs、L2差/max(ref范数,1e-12)，实现前固定容差 | 未运行模型，不填零差；约1e-6仅历史fp32参考 | INPUT_CONTRACT/MEASUREMENT_REVIEW | 未运行 |
| optimizer一步/state_dict/dtype/NaN/缺失梯度 | 逐预期参数及状态检查；不能只拼接非None梯度 | 无张量运行；预训练decoder/解码阶段预训练heads的None需按图处理 | 同上 | 未运行 |

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
- 新的正确性、单域→四域→整节点A/B、3轮及第二主机全部未运行；没有同步训练、微算子/整步收益或新内存峰值可报。

## 6. 接受条件与限制

本地冻结、远程身份/权限/源码/输入/manifest、历史JSON完整性和重计算、版本漂移及输入语义问题已形成证据交接，**总协调已接受该交接；现有历史包仍不属于性能/科学正确性已验收结果。** 本轮收尾不表示PENDING_ITEMS中的缺项已解决。

没有生产集成或需要回退的共享改动。保留原始fp32、模型架构与数据字节；两份隔离shell只作路径准备，正式运行前须使用S01接受版本。17:09快照并不承诺之后共享文件不变。

| 后续任务 | 可直接使用 | 必须补齐 |
|---|---|---|
| S01 | 两个远程启动器快照及diff；同哈希HBM/shim源码；135份历史JSON、失败摘要、缺域/慢域证据 | 逐PID退出/超时/过期处理及barrier；输入/库冻结；CKPT+HBM复测和第二主机；不用目录名当版本 |
| S02 | 同哈希模型/KML源码；B32与独立B64配置；4帧legacy输入SHA；mask分母、共享optimizer语义 | 明确16电极图像目标协议；固定随机变量的一步检查；有效batch一致；使用S01运行器；无本轮实测内存分解 |
| S06 | U-Net架构与fp32原生conv/SDPA基线，历史工具限制 | 当前账号numpy依赖来源、计算节点工具链/实际库加载；内存阶段评审后再做性能候选 |

已明确分工：运行器修复/验收由S01负责，输入适配与内存优化由S02负责。环境、输入来源与权威subject split仍缺的资料、提供方和适用门槛已在PENDING_ITEMS.md列为15项待补信息；资料提供由总协调协调，不由S00推定现有账号或文件即已获验收。

新性能基线先等待S01运行器验收，之后按单域→四域→整节点逐级推进，输入/运行环境适用前提和实际资源排期也需满足。RUNBOOK中的7.5节点小时仅为旧预算建议，不是已有作业授权；完整训练和第二主机另排期。当前不继续远程核查或新实验。

用户已明确授权将限定证据保存work/S00，此依赖已解除。一次扩大到完整日志及辅助/环境源码的请求被自动审批拒绝，已收紧为日志摘要、哈希和输入统计后完成核查；未返回那些全文，未绕过限制，无需为本次已完成范围再次确认。

## 7. 证据索引

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00`。下列文件完整SHA256统一见ARTIFACT_SHA256.txt（不对索引本身循环哈希；tmp第三方依赖不计入）。所有原源码/副本另有独立清单。

| 证据 | 绝对路径 |
|---|---|
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

未向其它聊天发送消息或修改共享任务状态。总协调已接受证据交接；本轮文档收尾完成，后续按PENDING_ITEMS和RUNBOOK的恢复门槛继续。接受交接不等于已集成或性能通过。
