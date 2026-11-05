# S00：R6独立首步DDR内存诊断与UBSan条件验证

日期：2026-11-05（Asia/Shanghai）。
状态：READY_FOR_REVIEW / MEMORY_DIAGNOSTIC_COMPLETE / UBSAN_RECOVERY_BLOCKED。

## 1. 结论

本轮恰好两个新job且均已终态。R6完整B64/CKPT0、CKPT1在不同进程各完成一次fresh训练步，训练阶段进程峰值RSS为5836.0078125、4313.87890625 MiB，退出均0；只作为首步诊断，不能据此正式接受内存收益或稳态吞吐。UBSan任务在获准有限位置未找到运行库，退出1并停止，正负控、新50场景和独立库均未运行。没有重试、安装、真实HBM或S06/S07探针。

## 2. 前置条件与执行范围

先读自己的SESSION_STATUS.md、ROUND_DELTA.md和COORDINATION/STATUS.md相关行；本轮依据AFTER_S06_S07_NEXT.md的S00章节、S02 R6 C2_HANDOFF.md内存节、原memory_gate.py/run_c2_memory.sh/train_memory.py及S03 round2_api_bounds_20261105/LINUX_COMMANDS.md。协调S06_S07_AND_R6_RUNTIME_REVIEW.md已接受job2037034固定case的1063项严格数值通过。没有重跑严格对照或旧25场景。

原包保持逐字节：

| 原样包 | SHA256 | 文件数 |
|---|---|---|
| S02_CKPT64_R6_CODE.zip | `26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f` | 28 |
| S03_ROUND2_C_VALIDATION.zip | `0fe3eeb3a7ad7fe2fb34eea220f3147edba5b72cdc44f5c7db4fd46d98ea872a` | 18 |

固定case只读沿用`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt`，271979513 bytes，SHA=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`，执行前后mtime_ns均1793850592308132590。未上传、复制或重新生成case。

实际严格PASS引用为`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T060434Z/payload/evidence/c2_2037034_checkpoint_strict/result.json`，SHA=`1f2aac7dee498cd839b696d1305e80236227c445da69e26ffd38f5c80c9aba17`。提交前及计算作业内两次原memory_gate都通过，来源、1063项指标、双侧KML、CPU36和case身份相符。原始引用及其原mtime_ns/bytes/SHA随证据回传。

新远程目录分别为`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_R6_MEMORY_20261105T064800Z/`和`/home/share/dengqingtian/opt/stage4_sessions/S00/S03_R2_UBSAN_20261105T064800Z/`。本地只写work/S00；原包、候选、比较器、阈值、阶段二/三及共享运行环境未修改。上一轮报告和两份完整证据ZIP哈希复核未变。

执行层新增candidate/prepare_memory_ubsan_round.py、run_s03_r2_ubsan_recovery.py/.sh、collect_memory_ubsan_evidence.py与audit_memory_ubsan_delivery.py。C执行层保留原previous/candidate各50场景和独立库命令，在它们之前加有限库发现、ELF/依赖/身份及正负控门槛；与旧执行层差异见本轮evidence/execution_layer.diff。原数值/C源码未改。

## 3. 环境、复现方式与成本

| 任务 | job / 主机 | 北京时间起止 | 调度终态/退出 | 时限/实际墙钟 |
|---|---|---|---|---|
| 独立首步内存 | 2037434 / cn21339 | 14:48:38—14:49:16 | SUCCEEDED / 0 | 900 / 38秒 |
| UBSan恢复/条件C | 2037491 / cn21339 | 14:51:41—14:51:43 | FAILED / 1 | 300 / 2秒 |

两个job均q_hpcai、`cpu=38,mem=24576MB`、`-RL mem=24576MB`、单NUMA pack、`--env none`；调度实际分配0–37，选0–35，留36–37。首项结束后才提交第二项。无调度重试，最终PID字段均为`-`，SSH和下载连接已正常退出。调度usage首项wallclockDuration为37秒，按UTC起止差记38秒，不混淆两个字段。预计时限总计1200秒，实际40节点秒（约0.011111节点小时，含C阻断2秒）；累计S00十四job共483节点秒。

内存解释器`/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3`，Python3.9.9，torch2.7.1+cpu（`/home/share/songzhenlong/eitfm/sw/torch_kml/torch`），numpy1.26.4（上述venv的lib64/python3.9/site-packages）。实际KML为`/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so.1.26.0.RC1`，SHA=`c9b2f040c5b4756d426589956059e3865749cd8751eb3914c57d42a9e84ebf3c`；shim SHA=`a52c4da1a87b1a65b11121ecab2b8d0ca3fd2a03a5c92422873592381a92dd73`。每个result含全部库路径、SHA及结束重验。

内存环境OMP36/MKL36/OpenBLAS1/cores/close，两个进程各7项同PID检查，实际Torch intra-op=36；interop元数据为608，未覆盖该默认值，全可见TID的实际掩码仍均限于选中36核。工作量为16_adjacent/pre、完整B64、fp32、fresh AdamW一次、原mean、输入梯度保留、预热0、HBM0。encoder37995777参数，decoder29416449参数存在但本pre步不活跃；初始权重重复副本在训练前释放，无比较快照。

实际命令和资源见两个received/submit_*.sh、submission.json和djob_final.json。内存主命令为：

```bash
env S02_CASE_FILE="$CASE" S02_EQUIVALENCE_RESULT="$STRICT" bash "$PAYLOAD/run_s00_job.sh" memory
```

原入口分别以`timeout --signal=TERM --kill-after=15s 360`启动两个train_memory.py进程，并用numactl约束获分配域，再在框架导入前按原守卫绑定实际36核。每个进程原始command.txt、stdout_stderr.txt和exit_code.txt已回传。复测须另行授权、新目录、新job，不能原目录直接重放。

## 4. 正确性

| 门槛 | 本轮实际证据 | 结果 |
|---|---|---|
| 前置严格等价 | 引用2037034原1063/1063 PASS；本轮不重新计算 | 前置通过 |
| 不同进程、完整工作量 | CKPT0 PID1428225；CKPT1 PID1429732；各optimizer_steps=1，包装层0/12 | 通过 |
| case/权重/源 | 28源及case前后相符，两个加载身份与严格PASS一致 | 通过 |
| 真实KML及CPU36 | 两侧调用149/197；各7检查、CPU errors=[]；全部可见TID在0–35 | 通过 |
| loss/梯度/optimizer | loss均303.04705810546875；原内存入口校验活动梯度、fresh AdamW状态及step1；未保留逐项比较快照 | 通过原入口检查，非新增1063项比较 |
| RSS重置/hugetlb | clear_refs写5成功；训练开始HWM等于当时RSS且低于初始化HWM；全部HugetlbPages=0 | 通过 |
| UBSan恢复正负控 | 未发现匹配运行库，未编译/执行控制程序 | 阻断/未运行 |
| 新previous/candidate各50及独立.so | 未越过运行库门槛 | 未运行 |

一次提交前准备脚本用整块read_bytes计算case SHA得到不一致摘要，断言在提交前停止。原始失败JSON、脚本、payload和修正记录全部保留。GNU sha256sum及沿用原方案的1MiB分块SHA均匹配冻结case，大小/mtime也未变；准备脚本仅改用该分块方法后完成预检，模型、case和正式诊断代码未改，无job重试。整块摘要不一致根因未确定，不据此声称case曾被改动。复核脚本另修正了“ZIP不保存空build目录”的本地证据断言，未运行任何额外集群测试。

## 5. 性能与内存

口径为整个进程的/proc/self/status RSS/HWM，含共享库驻留页；MiB=2**20 bytes，不是tensor独占量、PSS或真实HBM驻留。训练峰值在后置校验及JSON等开销之前读取。初始化与训练高水位分开，不以生命周期峰值代替训练峰值。

| 配置 / 独立有效进程数 | 初始化秒 | 初始化峰值bytes / MiB | reset后训练起始RSS bytes / MiB | 一步秒 | 训练峰值bytes / MiB | 训练结束RSS MiB | 退出 |
|---|---|---|---|---|---|---|---|
| CKPT0 / 1 | 14.6575342608 | 915197952 / 872.80078125 | 728817664 / 695.0546875 | 2.4526388668 | 6119497728 / 5836.0078125 | 3523.84375 | 0 |
| CKPT1 / 1 | 13.5683002570 | 946135040 / 902.3046875 | 738398208 / 704.19140625 | 3.3435222791 | 4523429888 / 4313.87890625 | 3950.484375 | 0 |

仅一个同主机顺序配对，训练峰值原始差1596067840 bytes（1522.12890625 MiB），CKPT1一步时间更长且结束RSS更高；没有重复轮次、稳态吞吐、多域通信、训练效果或正式内存收益接受。完整未舍入原值见review.json和两个result.json。

## 6. 接受条件与限制

内存首次计量已完成；clear_refs可用且计数下降至当前RSS、hugetlb为0、来源/工作量/CPU/KML及退出证据完整，建议交S02和总协调解释首步结果，不能直接集成或扩规模。

C job保留干净环境及所有sanitizer要求。实际`/usr/bin/cc`（解析到GCC，版本10.3.1、AArch64 ELF）对libubsan.so及libubsan.so.1只返回未解析文件名；libgcc_s.so.1位于编译器报告的既有lib64目录。仅检查该目录及`/usr/lib64`、`/lib64`、`/usr/lib/aarch64-linux-gnu`、`/lib/aarch64-linux-gnu`的有限libubsan.so*，没有文件命中，runtime_locations.json记录checked=[]。没有全盘搜索、安装、另选工具链重试或改全局环境。结论仅限本次有限位置，不声称全节点或全平台不存在任何UBSan环境。

没有运行库可记录SHA/ELF/依赖，也未创建链接目录；执行层在无库分支提前退出，因此编译器文件SHA记录步骤也未到达，只有编译器路径/版本/ELF原件，不伪造完整工具链身份。正负控程序尚未生成/编译，50场景与库构建均未运行，不能把阻断视为候选缺陷或C验收通过。后续需协调提供可核实、与编译器匹配的已有运行库/工具链位置，另行安排新有界job并仍先过正负控；本轮不自行补交作业。

既有R5数值失败、旧C有限通过、R6数值通过与2037064链接失败原件继续保留。本轮没有生产部署、真实HBM或06/07探针。

## 7. 证据索引

报告绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\R6_MEMORY_UBSAN_REPORT.md`。

证据绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\r6_memory_ubsan_20261105\`。

| 完整原件包 | bytes / 文件数 | SHA256 |
|---|---|---|
| JOB_2037434_full_evidence.zip | 196064 / 90 | `d2dd91be74c2bba01f529f926d07ab38b184d88b6389bcbae0a1283fd1f51881` |
| JOB_2037491_full_evidence.zip | 55539 / 49 | `08410627941e6249cb10fed875c9204891f6ad9cdc93364880051ae3b9a22754` |

解压原件在S02/received及S03/received；各COLLECTION_S00.json保留所有文件远端原始mtime_ns、bytes、SHA，下载逐项核对一致，payload及包装器执行前后未变。S02含提交前门禁、完整前置strict引用、cpu_allocation.json、两个进程全部日志/命令/result/exit及case前后身份；S03含compiler、uname、glibc、source/package校验、compiler ELF/target/print-file-name、runtime_locations、steps和SUMMARY。空目录不存入ZIP。

ROUND_REQUEST.json保留本轮界限和旧产物哈希；SESSION_STATUS_before.md/ROUND_DELTA_before.md为更新前快照；更新后快照及ARTIFACT_SHA256.txt冻结本轮交接；review.json为本地非模型复核结果。完整复核入口为`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\candidate\audit_memory_ubsan_delivery.py`，只读原件数据，不重跑模型或C。登录凭据不写入报告或文件。
