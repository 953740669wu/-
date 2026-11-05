# S00本轮：S02 R6 CKPT严格对照与S03 R2 C/UBSan

日期：2026-11-05（Asia/Shanghai）。状态：**READY_FOR_REVIEW / S02_FIXED_CASE_STRICT_PASS / S03_UBSAN_LINK_BLOCKED / BOTH_TERMINAL**。

## 1. 本轮结论

按R6_S03R2_NEXT_S00.md顺序，只执行一项新数值job和一项新C job，无重试或扩大。两项均分配单域38个物理核心、实际选前36留末2，resAlloc.mem及resLimit.mem均24576MB。完整回传源身份、命令、退出、指标及原mtime_ns/bytes/SHA。

| 项目 | job / 节点 | 北京时间 | 时限/实际 | 真实结论 |
|---|---|---|---|---|
| S02 R6完整B64 CKPT0/1 | 2037034 / cn21339 | 14:06:24–14:06:57 | 900s / 33s | SUCCEEDED、checker/job exit0；PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY，1063/1063通过 |
| S03 R2新50 C/UBSan | 2037064 / cn21339 | 14:10:03–14:10:05 | 300s / 2s | FAILED、job exit1；previous harness链接找不到-lubsan，场景和独立库构建未到达 |

S02仅本固定合成case通过，不改写旧R5拆批95项FAIL。S03为执行前提/链接阻断，不是previous的21个预期缺陷被验证，也不是新候选C场景失败。内存、真实HBM均未运行。

## 2. 来源、范围与远端提交门槛

已先读本任务SESSION_STATUS.md、ROUND_DELTA.md，再读总表、本轮集中交接及本轮本地审核，按链接读取R6严格对照入口与S03新cases/runner。没有重跑R7、旧R5/旧25 C场景或Windows模型。

- S02原包SHA256：26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f；28成员原样核验，53项作者索引核对。
- case只读复用旧远端S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt；271979513字节，SHA256=4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846，前后均重新核对，未生成/复制/下载case。
- S03原包SHA256：0fe3eeb3a7ad7fe2fb34eea220f3147edba5b72cdc44f5c7db4fd46d98ea872a；18成员、17项作者索引原样核对。frozen为上一已接受候选8ec586…，新候选d1f5dbbfb6aa4a973dcc4d12607f62a8b2be5166690897dfd5ea35e067c7d7a2。
- 两项实际远端ZIP/payload/source SHA、shell/env字节LF、真正Linux bash -n、实际Python3.9语法均通过后才提交；提交层再次核对并使用唯一marker。S02 source runtime后重新加载Donau并确认dsub路径，没有改原包。
- 新目录分别为/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T060434Z/和S03_R2_C_20261105T060824Z/；各用新job，不复用旧allocation。任务作者/协调目录、旧结果与数值标准未修改。

## 3. S02实际数值、模型隔离和CPU/KML

唯一配置：16_adjacent/pre、完整B64×1参考CKPT0对完整B64×1候选CKPT1、backend=kml/mode=checkpoint_strict、原mean、fp32/fresh/HBM0，一次AdamW。参考完成释放模型后构造独立候选并加载同一case初权重；候选只给encoder的12层使用原非重入checkpoint（use_reentrant=False）。实际记录independent_model_instances=true、reference=false/candidate=true、wrapped_encoder_layers=12。

全部1063项原严格指标passed=true，failures=[]，max_abs及L2 relative最大值都为0；保持原loss/输出/输入梯度/参数梯度/更新后参数/增量/AdamW状态的比较器与阈值，没有把它替换为近似或控制PASS。不是对所有case、32电极、decoder或训练效果的验收，也不声称浮点符号位逐位检查。

实际KML GEMM reference=149、candidate=197，总346；双方均真实调用，库路径/SHA结束复核通过。模型参数/固定张量身份与case manifest匹配。7项同PID CPU36 checkpoint完整有序、框架后真实Torch intra-op36、所有记录TID mask在选中0–35内，预留36/37，errors=[]；close绑定的调用线程子集保持真实。该检查不是连续线程采样或精确in-region team证明。

实际入口只调用run_s00_job.sh equivalence，未调用memory、memory_gate或clear_refs。包内内存入口仅归档，不因本次数值PASS自动执行/接受计量或收益。

## 4. S03实际阻断与未运行项

新执行层使用env -i清除KML/HBM/LD_PRELOAD/PYTHONPATH污染；用冻结R7 CPU拓扑帮助模块将父执行进程收窄到36核，各编译/检查子进程继承该集合。源码/包完整性检查通过，随后按新命令编译previous：

```text
/usr/bin/cc -std=gnu11 -O1 -g -Wall -Wextra -pthread -fsanitize=undefined -fno-sanitize-recover=all -DS03_SOURCE="../frozen/hbm_alloc.c" tests/bounds_harness.c -o build/bounds_previous
/usr/bin/ld: cannot find -lubsan
collect2: error: ld returned 1 exit status
```

编译器为本节点/usr/bin/cc GCC10.3.1，glibc2.34。保留UBSan flags与halt_on_error设置，未移除sanitizer、未安装/更换工具链或追加job。准确阻断是**本次干净默认工具链不能链接-lubsan**，未据此断言所有节点/其它现有工具链都不可用。

本轮previous的50场景（应逐项审查21预期失败/29控制）、candidate的50场景及独立.so均未运行/未构建。没有套用旧25场景或冻结runner应退出1的判据；新runner审查成功应退出0，但尚未到达runner。未执行policy_probe、模型preload、真实内核策略或HBM。

## 5. 资源、时限、退出与消耗

两job的djob_final记录分配38核、选中36/留2的receipt及24576MB请求/限制；job时限分别900/300秒。S02内部780秒+15秒宽限；S03总deadline270秒，命令超时只终止本任务session。没有资源越界、不可控进程或超时，本轮最终PID字段均“-”，S02正常终态/清理后才开始S03。

本轮实际节点壁时33+2=35秒≈0.009722独占节点小时；此前408秒另计，累计12作业443秒≈0.123056节点小时。失败计入，GPU小时0。数值checker含对照快照/比较与checkpoint，不能用其墙钟或高水位当训练吞吐/训练内存收益；C编译阻断也没有性能结论。

## 6. 完整回传与当前停止点

- S02完整48文件、S03完整43文件，ZIP CRC/远端摘要/逐文件SHA和bytes核对通过；原始远端mtime_ns保留。28/18个payload成员运行后身份不变，旧报告/包SHA未变，received原件未改。
- S02结果为PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY，供S02/总协调审核；原R5拆批失败独立保留。内存测量语义和执行仍需另行安排。
- S03结果为UBSan链接前提阻断，50场景/独立库尚无本轮接受结果。需提供可用受控UBSan工具链/库搜索配置后另行授权；本轮不自动重试。
- 本轮只维护S00自己的交接、执行层、报告和证据，不操作Git/共享暂存区；更新SESSION_STATUS.md与ROUND_DELTA.md作为续接入口。

原始108文件清单本轮107项字节匹配；唯一变化为协调新增sessions/README.md的交接入口两行，已从Git只读恢复精确旧SHA并单独diff核验，见evidence/readme_handoff_review_20261105.json。未将其伪记为108项全未变，计算代码/实投payload及旧实验原件仍不变。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/s02_r6_s03_r2_20261105/JOB_2037034_full_evidence.zip：48文件，SHA256=7d6365f5ebe41c6fa8e80168a3ea3bb9a55ec7105944d7b0575818d496201bce。
- evidence/s02_r6_s03_r2_20261105/S02/received/payload/evidence/c2_2037034_checkpoint_strict/：result、全1063 metrics/failures、双方KML/CPU/隔离、命令/stdout/退出及身份原件。
- evidence/s02_r6_s03_r2_20261105/JOB_2037064_full_evidence.zip：43文件，SHA256=28a6530ecc4fc32b3984572330a48817ad07dafc5ef471420ba71de1cc9c1646。
- evidence/s02_r6_s03_r2_20261105/S03/received/payload/linux_evidence/：实际compiler/glibc、flags、package检查、build_previous链接错误、steps/SUMMARY原件。
- 两项received中的djob_final.json、submission.json、pre_submit_checks.json、COLLECTION_S00.json：完整job/资源/退出/实投/原始mtime_ns清单。
- evidence/s02_r6_s03_r2_20261105/review.json及S02/S03各自review.json：独立完整性与本轮判读。
- evidence/s02_r6_s03_r2_request_20261105.json、candidate/audit_r6_r2_delivery.py及collect_r6_r2_evidence.py：范围/冻结身份及可重复的非执行复核。
