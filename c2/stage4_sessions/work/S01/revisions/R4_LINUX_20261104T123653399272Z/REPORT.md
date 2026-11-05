# S01 R4：Linux进程清理与运行协议实测补充

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — LINUX_PROTOCOL_PASS / REAL_MODEL_STARTUP_NOT_RUN / CLUSTER_PERFORMANCE_NOT_RUN**。

## 1. 结论

已在授权登录环境 **login10 / Linux aarch64 / Python3.9.9** 实际完成：**3项Bash语法检查、4项Linux进程清理检查、8个合成协议场景**，全部符合预期。原来跳过的Linux进程组/后代清理已有实测结果；失败同伴清理、独立对照进程保护、超时和启动失败也均通过。

返回199个S01自有文件，逐文件SHA256全部匹配。接受的R2候选/根报告/原1607项交付物及108个原始项目文件保持不变，没有模型或分配器源码修复。

**完整真实模型启动链仍未运行**：S00明确尚无本任务计算job/节点，也尚无已验证能同时导入torch和numpy的解释器。本轮只完成Linux进程/文件协议层，未调用numactl执行模型、未import torch、未运行HBM、不提交作业或占用既有计算作业。没有新的性能或科学数值结论。

## 2. 前置条件与执行范围

依据最新STATUS、ROUND1_REVIEW、NEXT_ROUND与ROUND1_ACCEPTED_FILES，以及用户补充的S00环境交接：已知地址10.44.9.4:22，账号dengqingtian，登录落点login10，交互密码认证；独立目录在当前账号自有路径创建。

保留版本：S01_LOCAL_RUNNER_R2_20261104。接受报告SHA256：`e0a840aa4552fc52f5d6748591c6d3b8c5b4d1d651540a178ca29b1059fb8420`。runner.py SHA256：`692113888fab4ac23c0188f39731ceea0f0fec1a8ef09f25cee872515ba7dd0b`。

上传的是上一补充轮准备的原样包，SHA256：`162620a88c6edb9ee12c2d7d8bc4b07bd574c93be6d4d1b8f8018ad8586968b6`。远端先验证完整包SHA，再验证SOURCE_MANIFEST中的8个原样文件。候选源码diff为0，未改接受文件、共享owner目录、冻结输入或S02接口。

远程唯一目录：

`/home/share/dengqingtian/opt/stage4_sessions/S01/R4_LINUX_20261104T123653399272Z/`

远端仅在此目录写入S01代码副本及合成结果，无安装、构建.so或调度提交。主机公钥严格使用S00已保存known_hosts验证，没有关闭主机校验。密码由用户在可见SSH窗口输入，没有落盘或写进脚本/报告；SSH已正常退出。

本地补充报告/传输/核验目录：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z`。

本地成功接收目录使用较短路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received`。它同样位于work/S01内。

## 3. 环境、复现方式与成本

| 项目 | 实际记录 |
|---|---|
| 主机/系统 | login10；Linux5.10.0-285.5.v2403.ky10p.aarch64；aarch64/glibc2.34 |
| Python | /usr/bin/python3；3.9.9；GCC10.3.1构建信息来自sys.version |
| 账号 | dengqingtian |
| 时间 | 2026-11-04 20:38:26.884–20:38:31.535 +08；UTC原值在remote_context.json |
| 实际命令 | bash /home/share/dengqingtian/opt/stage4_sessions/S01/R4_LINUX_20261104T123653399272Z/linux_payload/run_linux_checks.sh |
| 退出状态 | 远端协议入口退出0；所有5个子命令步骤退出0 |
| 范围/成本 | 登录节点短时stdlib测试，约4.65秒墙时；新增计算作业0、计算节点小时0、GPU小时0 |
| torch/numpy/KML/OMP/numactl/HBM | 本轮没有实际导入或执行，模型运行时与计算节点仍待交接 |

可复现命令与资源边界保留在R3的LINUX_HANDOFF.md。远端协议脚本只需Bash/Python，不需要NPZ或torch；原4项测试和exercise_local原样运行，没有扩写已经通过的普通本地测试矩阵。

实际模型小试准备仍为：1个已分配计算节点、1NUMA域、最多38线程、建议DDR预算32GiB、最多15分钟、HBM=0，先16电极pre/dec、B32/CKPT0/fp32/KML、REPS1/ROUNDS3。它是尚未安排的受控启动请求，不是已授权作业或正式性能验收。失败不扩大；不在login10执行模型。

## 4. 正确性

| 检查 | 实际结果与判断边界 | 证据 | 状态 |
|---|---|---|---|
| 接受入口bash -n | run_node16.sh退出0 | step1.txt | Linux通过 |
| 协议/预检脚本bash -n | run_linux_checks.sh与runtime_preflight.sh各退出0 | step2/step3.txt | Linux通过 |
| Linux后代清理 | 既有test_posix_descendant_cleanup通过；判据为后代不存在或已为Z，不宣称init已立即回收所有僵尸 | step4.txt | Linux通过 |
| 同伴失败与独立进程 | 失败rank退出7；同伴被本任务监督器终止，独立对照进程仍存活 | step4.txt；合成failed_rank状态 | Linux通过 |
| 超时/正常退出 | 超时进程终止并带timed_out标记；正常进程退出0 | step4.txt；合成timeout状态 | Linux通过 |
| 启动失败 | 缺失可执行文件被记录失败，已启动同伴被终止 | step4.txt | Linux通过 |
| 8个真实子进程合成场景 | 完整3轮PASS；其余七类FAIL；独立汇总CLI退出码对应0/1 | step5.txt；local_exercise_index.json | Linux通过 |
| 包/原样副本/返回证据SHA | 包与8份源码检查通过；返回199文件逐一复核 | linux_verification.json；IMPORT.json | 通过 |
| 原交付/原始项目完整性 | 原1607索引不变、接受R2/根REPORT不变、108个原文件不变 | linux_verification.json | 通过 |
| 真实解释器/模块来源/允许CPU与内存/库实际加载/实际NPZ | 新探针只通过Bash语法，没有执行 | runtime_preflight.sh | **未运行** |
| 完整真实启动链 | 接受shell→runner.main→numactl→模型前反向/AdamW→barrier/结果/状态/汇总 | 没有实际训练日志或JSON | **未运行** |
| 输出/loss/梯度/optimizer/state_dict/dtype/NaN科学数值 | 没有模型执行，不提供误差数字 | 不适用 | **未运行** |

Linux合成逐项结果：

| 场景 | 汇总/CLI退出码 | 实际进程退出码 | 结论 |
|---|---|---|---|
| complete | PASS / 0 | 3轮共6个退出0 | 完整协议通过 |
| failed_rank | FAIL / 1 | 7与-15(SIGTERM) | 失败传播和同伴清理 |
| timeout | FAIL / 1 | 两个-15，均带timed_out | 超时失败，未误报 |
| missing_json | FAIL / 1 | 两个0 | 仅进程成功不能替代完整结果 |
| corrupt_json | FAIL / 1 | 两个0 | 损坏结果拒绝 |
| stale | FAIL / 1 | 两个0 | 旧身份/结果拒绝 |
| partial | FAIL / 1 | 两个0 | 缺工作负载拒绝 |
| config_mismatch | FAIL / 1 | 两个0 | 配置不一致拒绝 |

本轮数字均来自合成协议，不能用作C2模型吞吐、内存或科学正确性。该合成链调用接受runner的监督/barrier/发布/汇总基础设施，尚未覆盖真实shell的模型调度主分支与动态库/输入链。

取回过程中发生一次本地Windows长路径解包错误，远端测试及完整返回包已成功。保存原失败状态与部分解包作为过程记录，随后仅用保存的transport改到短目录重新核验/解包，未再次SSH或重跑远端。修正了本轮接收辅助脚本的长路径预检及默认短目标；接受R2代码完全未改。当前权威结果为短目录与linux_verification.json，interactive_status.json中的FAILED仅表示首次本地解包失败。

## 5. 性能与内存

| 工作负载 | 域数/有效模型结果 | 批量/精度 | 步时/吞吐/最慢域 | DDR/HBM | 状态 |
|---|---|---|---|---|---|
| Linux进程/合成协议 | 不是模型NUMA域实验 | 合成数值 | 不报告假性能 | 未测 | 协议通过 |
| 原模型16-pre/dec实际启动 | 未运行 | 拟B32/fp32 | 未运行 | 未运行 | 待环境/job |
| 32电极/CKPT/HBM/四域/整节点 | 未运行 | 未排期 | 未运行 | 未运行 | 未运行 |
| 三有效性能轮/第二主机/实际DDP | 未运行 | 未排期 | 未运行 | 未运行 | 未运行 |

约4.65秒只是检查脚本墙时，不是模型加速。没有新增整步性能、RSS/HBM占用或热度trace。Linux协议PASS不能代替真实模型、OMP ABI配对、HBM稳定性、性能基线和正式训练接受。

## 6. 接受条件与限制

建议总协调接受本轮 **Bash语法与Linux进程/协议补验**，保留R2候选身份不变；原“Linux分支未运行”在这四项既定检查范围内得到补充。不是自动生产部署或完整M1通过。

仍需S00/总协调安排计算job/节点与CPU/内存额度，交接能同时导入torch/numpy的解释器、KML/OMP/shim实际来源、输入副本与加载证据。随后才运行已准备的runtime_preflight，再执行受控原模型启动链；实际启动失败或资源不足时停止，不占用已有作业、不在登录节点补模型重测试。

两个demo仍是已知16电极图像错配的LEGACY_TIMING_ONLY，仅用于历史计时兼容；S02负责新输入配对协议。HBM与分配器修复仍归S03，本轮没有相关源码/库改动，也不直接拼接S02。

没有需要用户再次提供密码的当前工作；完整Linux证据已经本地核验。剩余依赖是计算运行环境与资源交接。停止引用本轮补充即可回退，根REPORT与接受清单保持原值。

## 7. 证据索引

| 产物 | 绝对路径 |
|---|---|
| 本轮补充报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z\REPORT.md` |
| 本轮核验/范围/映射 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z\evidence\linux_verification.json` |
| 传输归档SHA与199文件导入索引 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z\evidence\transport_20261104T1238048494295Z\IMPORT.json` |
| 原始完整返回transport | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z\evidence\transport_20261104T1238048494295Z\transport.txt`（含压缩证据，不必直接阅读） |
| 远端现场元数据 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\remote_context.json` |
| Linux总结果 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\linux_payload\evidence\LINUX_PROTOCOL_20261104T123826969145Z\RESULT.json` |
| Bash检查日志 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\linux_payload\evidence\LINUX_PROTOCOL_20261104T123826969145Z\step1.txt`、step2.txt、step3.txt（成功时为空文件） |
| Linux四项进程检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\linux_payload\evidence\LINUX_PROTOCOL_20261104T123826969145Z\step4.txt` |
| 八场景入口日志 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\linux_payload\evidence\LINUX_PROTOCOL_20261104T123826969145Z\step5.txt` |
| 八场景原始索引 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\linux_payload\evidence\local_exercise_index.json`（其中远程绝对路径可按remote_context.root映射到本地接收根） |
| 返回199文件SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\linux_r4_received\ARTIFACT_SHA256.txt` |
| 本补充目录SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R4_LINUX_20261104T123653399272Z\ARTIFACT_SHA256.txt` |
| 原准备包及实际启动边界 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\LINUX_HANDOFF.md` |

所有原始日志、进程状态、JSON及脚本已在上述短目录与索引保存；没有真实训练/数值/HBM或性能结果可索引。未向其他聊天自动发消息，由用户将本补充报告交总协调审核。
