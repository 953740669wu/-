# S01 R3：Linux进程清理与实际启动链补验准备

日期：2026-11-04（Asia/Shanghai）。

状态：**WAITING_DEPENDENCY / PREPARED_ONLY / LINUX_NOT_RUN / REAL_MODEL_NOT_RUN / CLUSTER_PERFORMANCE_NOT_RUN**。

## 1. 结论

已按NEXT_ROUND读取首轮验收与接受清单，保留已接受R2全部文件，准备独立Linux补验包及真实导入/输入/动态库探针。当前没有可用的已授权Linux执行环境，尚不能完成Linux进程清理或真实启动链验证；没有把Windows防误用检查或脚本编译写成Linux通过。

已向用户请求S00安排的Linux主机/账号、现有登录方式与独立目录；真实模型启动还需实际job/计算节点、解释器与输入/库交接。请求仍待答复。本窗口没有SSH探测、安装WSL/容器、占用既有作业或提交新作业。

## 2. 前置条件与执行范围

已读STATUS、ROUND1_REVIEW、NEXT_ROUND、ROUND1_ACCEPTED_FILES及S01既有RUNBOOK/代码/相关清理检查。首轮接受的是S01_LOCAL_RUNNER_R2_20261104本地候选，非Linux/M1/真实模型/HBM或性能接受。

起点逐项核对原S01索引1607项，全部匹配；接受清单中的S01报告及8个文件全部匹配；原始108个项目文件仍与S00初始清单一致。本轮仅在新的revisions目录写补充文件，**不覆盖接受清单中的根REPORT、candidate、tests或原索引**。

接受报告SHA：`e0a840aa4552fc52f5d6748591c6d3b8c5b4d1d651540a178ca29b1059fb8420`。

接受runner SHA：`692113888fab4ac23c0188f39731ceea0f0fec1a8ef09f25cee872515ba7dd0b`。

当前补充目录：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z`。

linux_payload中5个候选文件、2个既有测试文件及exercise_local.py共8个副本逐字节匹配原交付。SOURCE_MANIFEST.json记录各副本SHA；本轮候选代码diff为0。新增的三个执行/探针脚本见new_helpers.diff，未改模型、分配器、输入或接入S02。

## 3. 环境、复现方式与成本

| 项目 | 实际状态 |
|---|---|
| 本机 | Windows，系统Python3.11.9；没有Linux内核执行会话 |
| WSL | wsl --list --quiet返回未安装Windows Subsystem for Linux；原始输出已按UTF-16解码保存 |
| 容器 | PATH未发现docker/podman；未安装或启动新运行时 |
| Git Bash | 初始化失败0xC0000022，退出3221225794；即使可运行也不能替代Linux内核分支 |
| 当前Python | torch未找到；未安装依赖，未运行模型 |
| Linux/job | 无新交接的Linux环境或本任务分配job；既有集群账号/历史作业不自动成为额度 |
| 成本 | 新集群作业0、节点小时0、GPU小时0；仅本地文件核验、Python语法及平台拒绝检查 |

Linux协议交接最小需求：已有授权Linux终端、Bash、Python≥3.9、账号自有目录。无需torch/NPZ/HBM。实际启动前另需S00提供分配节点与CPU/内存集合、实际Python模块来源和库/输入。

实际模型小试的待排期建议：1节点、1NUMA域、最多38线程、DDR预算32GiB、最多15分钟、HBM=0，先16电极pre/dec、B32、CKPT0、fp32/KML、REPS1/ROUNDS3；不是已有资源授权。完整模型、原预热、反向与AdamW保留。每轮240秒/外层900秒停止；失败或不完整不扩大到32电极、四域/整节点或HBM。

精确命令与各层返回材料在LINUX_HANDOFF.md。runtime_preflight.sh逐字复用接受入口exec之前的环境设置，仅执行新导入探针；实际模型小试直接调用接受的run_node16.sh，不用桩替代模型。

## 4. 正确性

| 检查 | 判断与实测 | 状态 |
|---|---|---|
| R2原交付与接受身份 | 原1607索引及S01接受文件全部匹配 | 本地核对通过 |
| 8个payload副本 | SHA逐一相同，未修改接受候选 | 本地核对通过 |
| Python及shell内嵌Python语法 | 本机compile成功；未运行Bash解析器 | Python静态通过 |
| 平台拒绝 | runtime_probe及protocol内嵌Python在Windows均非零拒绝，明确NOT_RUN | 两项本地防误用行为检查通过；不是Linux验证 |
| Bash语法 | 待在Linux执行3项bash -n | **未运行** |
| Linux进程组/后代清理 | 选取既有4项覆盖后代、失败同伴/独立对照、超时及启动失败，不新增重复套件 | **未运行** |
| Linux8场景合成协议 | 可执行包会运行既有exercise_local并核对8项结果 | **未运行** |
| 真实解释器/模块/库/输入 | 探针记录实际路径、CPU/内存集合、相关变量、实际maps/SHA并匹配legacy NPZ | **未运行** |
| 完整真实启动链 | 接受shell→runner.main→numactl→模型前反向/更新→barrier→结果/状态/汇总 | **未运行** |
| 输出/loss/梯度/optimizer/state_dict | 没有真实张量执行或科学误差数字 | **未运行** |

没有重跑或扩写已经通过的39项普通本地套件；R2的38通过/1Linux跳过仍是历史接受记录，本轮不能将该跳过改成通过。原模型计算和KML未改，真实数值接受保持未运行。

## 5. 性能与内存

| 工作负载 | 域数/结果 | 批量/精度 | 步时/吞吐/最慢域 | DDR/HBM | 状态 |
|---|---|---|---|---|---|
| Linux协议/合成 | 未运行 | 无真实模型 | 不填合成性能 | 未运行 | 未运行 |
| 首次实际16-pre/dec启动 | 未运行 | 拟B32/fp32 | 未运行 | 未运行 | 未运行 |
| 32电极/CKPT/HBM/四域/整节点/三性能有效轮/第二主机 | 未运行 | 未排期 | 未运行 | 未运行 | 未运行 |

协议PASS仅限Linux进程/文件协议。runtime探针PASS只代表导入与文件身份；不代表实际训练、OMP ABI数值配对或完整链通过。REPS1启动小试不作为正式性能验收；UNSTABLE必须原样保存，不放宽5%。仍无DDP吞吐、内存收益或加速结论。

## 6. 接受条件与限制

当前未完成用户要求的Linux实际补验，具体缺项是可登录且已授权的Linux执行环境，以及实际模型所需的S00资源/解释器/库/输入交接。不能通过本地仿真、增加纯文本检查、安装新系统或占用旧作业替代。

交S00/总协调的环境需求及一个可审查的小试命令已写入LINUX_HANDOFF；没有向其他聊天自动发消息。收到环境后直接运行包内既有Linux检查，不重新开发一套替代测试。

原demo继续LEGACY_TIMING_ONLY，16电极目标错配不在本轮修正，不宣称科学正确性通过；不改分配器、不整合未过数值门槛的S02。停止使用本轮验证目录即可回退；接受R2与其哈希保持不变。

## 7. 证据索引

| 产物 | 绝对路径 |
|---|---|
| 本补充报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\REPORT.md` |
| Linux完整交接/小试边界 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\LINUX_HANDOFF.md` |
| 可传输验证包 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\S01_R3_linux_validation.zip` |
| 原交付/接受SHA核验 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\evidence\baseline_audit.json` |
| Linux不可用的现场输出 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\evidence\local_linux_availability.json` |
| Windows拒绝检查原始输出 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\evidence\windows_guard_checks.json` |
| 原样候选/既有检查SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\linux_payload\SOURCE_MANIFEST.json` |
| Linux协议执行入口 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\linux_payload\run_linux_checks.sh` |
| 真实启动前环境入口/探针 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\linux_payload\runtime_preflight.sh`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\linux_payload\runtime_probe.py` |
| 新增辅助文件diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\new_helpers.diff` |
| 本轮独立SHA索引 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R3_LINUX_20261104T115103605246Z\ARTIFACT_SHA256.txt` |

没有Linux或真实模型结果文件可索引，不创建假PASS。实际执行后的RESULT和原始日志需由Linux环境返回，再更新新的补充版本；本报告不替换已接受的根REPORT。
