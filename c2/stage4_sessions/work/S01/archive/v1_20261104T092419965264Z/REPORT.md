# S01：本地运行器失败处理、完整计数与有界 barrier

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — LOCAL_ONLY / SHELL_NOT_TESTED / CLUSTER_NOT_RUN**。

候选版本：`S01_LOCAL_RUNNER_20261104`。提交本地候选供总协调复核，未集成、未部署；S01 的集群与性能验收仍未完成。

## 1. 结论

已复现原汇总器五种安全要求失败，交付隔离的失败传播、逐轮结果完整性校验、原子结果发布和有界 barrier 候选。最终本地正常测试 **32 项：31 通过、1 项 Linux 检查跳过**；另有 **8 个真实 Python 子进程驱动的合成协议场景**全部符合预期。缺域、失败进程、过期/损坏结果、部分工作负载、配置不一致不能取得 PASS。

本次没有测量加速或运行模型。建议接受为**本地可复核候选**，待 Linux/shell 与集群验证后再决定是否供后续任务正式引用。原始模型计算、损失、精度策略和数据均未修改。集群连接及性能始终由 S00 负责，本窗口没有探测 SSH、提交作业或接管连接排查。

## 2. 前置条件与执行范围

- 先读 `work/COORDINATION/STATUS.md` 的 S01 开场说明，再读 sessions README、S01_STABILITY、REPORT_TEMPLATE、S00_REVIEW、S00/REPORT、S00 冻结源码/清单/环境/汇总误报证据与 MEASUREMENT_REVIEW，并参照根 README、STAGE4_HANDOVER 与原阶段四计划相关条目。
- 接受的前置版本是 `S00_LOCAL_ARCHIVE_20261104 / ACCEPTED_LOCAL_ONLY`，不是已接受的集群基线。S00 报告 SHA256 本次重算仍为 `6275eb39ba3f7c1ff79a9b9a1aa719c826f1920dae83e957d57aa97378d7dc84`。S00 的 25 个冻结文件及原始对应文件、全交付物哈希索引全部校验一致；没有重跑会改写 S00 证据的脚本。
- 所有新增/修改仅在 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01`。未发现 Git 仓库，不做提交/合并或共享工作树改动。
- 任务前后对 **163 个共享文件**比较 SHA256，0 个修改/缺失；其中原始 108 个文件还与 S00 的原始基线逐项一致。覆盖原始代码、全部 S00 文件和协调文件，不包括并行任务自己的目录。真实冻结 corpus/manifest 本地不存在，未核验远程样本，不据此声称远程数据冻结已验证。

以下原始路径相对于 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00`；候选路径相对于本 S01 根。完整绝对映射见 `evidence/source_hashes.json`。

| 文件 | SHA256 |
|---|---|
| 原 `baseline/s4_models.py` | `9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2` |
| 原 `baseline/c2/opt/run_node16.sh` | `a21aafcd1a3384f4ab07b146f24f5ebcf0b2a1b25eb35b725e8d26db9c655979` |
| 候选 `candidate/s4_models.py` | `512dc202e4c0d60363b57317ed612694b80a4d5d3467740ed582bcf600bf1d92` |
| 候选 `candidate/run_node16.sh` | `77d1faa164f4a03b3897fd83c3bb91d58dda77220be52904fe5a26b5194753e3` |
| 新增 `candidate/runner.py` | `e7a9faaba429255d7796f6a81fc0b26421f4050c6af9e4122a35b65f15e573d6` |
| 原样复制 `candidate/kml_ops.py` | `e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26` |
| `candidate/minimal.diff` | `9ddc43e125f960a48899b9124dc37fa8855a9b49eec9cd51a3090e91d0a6518d` |

修改清单与取舍：

1. `s4_models.py` 仅将原 barrier 接到辅助文件，移除因此不再使用的 SYNC 全局变量，将最终 JSON 改为带身份的原子发布。保留原 CRLF；没有改 warm-up、随机数调用、forward/backward、AdamW、计时区域和计算步骤。
2. `run_node16.sh` 变为隔离路径的薄入口。进程/状态/汇总逻辑移入无 torch 依赖的 `runner.py`，便于本机无 Bash 时实际验证。这比保留全部 shell 逻辑多一个文件，但避免在无法执行 shell 的环境中只用文本断言充当行为验证；未增加模型功能。
3. `runner.py` 记录逐 PID 退出与超时；任一子进程失败快速终止本次其他子进程，保留日志。每轮结果无效立即停止后续轮次，完整三轮后才允许稳定性 PASS。barrier 默认内部 300 秒，整轮默认 5400 秒，清理宽限 0.5 秒。
4. 新 tag 必须不存在；精确核对期望结果/状态文件集合、run_id/host/round/rank/PID、时间窗、配置、case 名、torch 版本、实际核心与源码哈希。输入 NPZ/候选/库在正式入口启动前哈希冻结、每轮复查。正有限值、吞吐与步时自洽同时检查；无效轮不输出聚合性能数字。
5. 默认期望 16 域；NDOM 必须显式匹配可用 affinity 内的 CPU 域数，任一域零核心拒绝。保留原 SKIP_BUSY 启动前快照方式，新增原始快照和最终绑定留档；没有宣称解决突发占核或慢域。

最小 diff 在 `candidate/minimal.diff`，包含两个修改文件与一个新增辅助文件；原样 kml_ops 不在 diff 内。已对 S01 内独立冻结副本执行 `git -c core.whitespace=cr-at-eol apply --check`，退出 0。没有应用到共享源码；检查目录在本任务 `tests/patch_check`。

## 3. 环境、复现方式与成本

| 项目 | 本次实际情况 |
|---|---|
| 主机/系统 | DESKTOP-54BJCD6；Windows build 26200，AMD64 |
| Python | 3.11.9；`C:\Users\A\AppData\Local\Programs\Python\Python311\python.exe` |
| 本地依赖 | 当前 Python 未找到 torch/numpy；未安装依赖 |
| 时间 | 环境采集 15:33:47 +08；最终合成协议场景 15:42:06–15:42:10 +08；最终完整性采集时间见 shared_integrity.json |
| 本地命令退出 | 候选正常测试 0；合成场景验证脚本 0；旧版缺陷见证预期 1；patch check 0 |
| Bash | PATH 无 Bash；找到 Git Bash，但启动失败：NtCreateDirectoryObject，0xC0000022，进程退出 3221225794。语法检查和 shell 集成未运行 |
| Linux/NUMA/HBM | Linux 进程组分支测试跳过；真实 numactl/affinity/hugetlb/preload 链未执行；未构建或加载库 |
| 集群/job ID | 未连接、无新增作业；主机/调度器/运行进程状态未查询 |
| 成本 | 集群节点小时 0、GPU 小时 0；本地仅短时 stdlib 子进程检查，失败/超时均为合成协议测试 |

本地复现命令（项目根执行）：

```powershell
python -B c2\stage4_sessions\work\S01\tests\test_runner.py
python -B c2\stage4_sessions\work\S01\exercise_local.py
```

全部本地命令、独立候选布局、后续 Linux 检查/计时准备稿和返回状态见 `RUNBOOK.md`。实际 CPU/KML/torch/输入与库身份仍待 S00 现场核实。没有复制真实 NPZ、生成数据、修改 batch/loss 或实际执行预训练。

未来运行仍沿用原 demo 的 s0322p0/p1、seed=0、随机初始化、encoder 12层/512宽/8头、原 U-Net 和 AdamW、每 belt pre/dec 各两步预热及 REPS=5。拟复测 microbatch=32/64、累积=1、CPU fp32、KML_LINEAR=1；这些均为未执行的实验配置，不是本地合成数值的来源。无 DDP，有效全局训练批量不适用。

## 4. 正确性

| 检查 | 预定容差及误差定义 | 本次结果 | 证据 | 状态 |
|---|---|---|---|---|
| 旧运行器安全要求 | 缺域/旧结果/失败退出标记/部分工作负载/仅一轮不能 PASS | 原汇总器五项都违反要求；有意保存红色缺陷见证 | legacy_safety_before.txt | 原版失败被复现 |
| 候选失败处理/结果完整性 | 任一缺域/非零退出/超时/损坏/旧身份/配置错不能 PASS | 32 项中 31 通过，1 Linux 检查跳过 | tests_after.txt | 本地通过；Linux 未运行 |
| 真实子进程与协议 | 完整三轮成功退出0；七种失败退出非零 | 8/8 预期一致；失败后停止后续轮次 | local_exercise_index.json 及对应 SYNTHETIC 目录 | 本地通过 |
| barrier | 只认期望 rank/run_id；peer abort 和 deadline 有界 | 正常/旧标记/额外 rank/同伴失败/超时检查通过；真实子进程正常过四个 phase | test_runner.py；SYNTHETIC 日志 | 本地通过 |
| 进程清理边界 | 同伴失败可结束本任务子进程，独立对照进程仍存活 | 退出7同伴被终止；独立对照进程存活；超时有明确标记 | tests_after.txt | Windows 直接子进程通过 |
| Linux session/后代清理 | 只终止自己创建的进程组 | 对应测试在 Windows 跳过，未假定等价 | tests_after.txt | **未运行** |
| 原子结果/数据格式 | 不写 NaN/Inf；坏写入不覆盖已完成结果；拒绝重复键 | 通过；吞吐×步时与batch检查 rel_tol=1e-9，mtime仅容许±2秒精度余量 | test_runner.py | 本地通过 |
| 模型计算代码 | 除同步、输出、相关 import/废弃 SYNC 赋值外 AST 完全相同 | 一致；KML 文件逐字节相同 | tests_after.txt | **静态通过** |
| 输出/loss/梯度/optimizer一步/state_dict/dtype/NaN | 需真实固定输入/权重/随机变量；预先定义科学误差指标 | 无模型执行，无误差数值；不能用 AST 一致代替数值验收 | environment.json | **未运行** |
| Python语法/最小diff | Python compile成功；diff在冻结副本apply --check成功 | 全部通过 | syntax_check.json；patch_check.json | 本地通过 |
| shell/真实导入和库加载 | 可执行 shell+numactl+目标 torch/KML | Bash初始化失败，未运行 | shell_status.json | **未运行** |

合成场景采用 2 个真实 Python 子进程，工作量数值完全由测试指定；完整场景有 3 轮，七个异常场景在第 1 轮终止。它不是“四域小试”或任何集群吞吐验收。最终场景索引为 `evidence/SYNTHETIC_20261104T074206918024Z/INDEX.json`；前两次 SYNTHETIC 目录与初次测试失败日志保留为开发过程记录，以最终索引和 tests_after 为结论依据。

开发中修正了两处测试夹具问题：旧版退出标记最初误用了会被旧 glob 当作结果的文件名；NaN/Inf 注入最初被候选原子写入函数提前拦截。修正后，原版五项均为明确 assertion failure，候选正常套件通过。没有以夹具异常冒充实现已通过。

## 5. 性能与内存

**本次没有 C2 数值、吞吐、DDR/HBM 或慢域负载实测。合成数字不进入下表。**

| 配置 | 域数/有效结果数 | 有效批量/精度 | 总步秒数 | 域吞吐合计 | 最慢域参考值 | DDR/HBM峰值 | 退出状态 |
|---|---|---|---|---|---|---|---|
| B32+HBM；16/32 belt pre/dec | 未运行 | 拟每进程32/fp32 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 |
| 32 belt B64+CKPT+HBM；pre/dec | 未运行 | 拟每进程64/fp32 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 |
| 若上项稳定，再32 belt B32+CKPT+HBM | 未运行 | 拟每进程32/fp32 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 |
| 同主机/同配置原始与候选A/B、三轮、第二主机 | 未运行 | 待排期 | 未运行 | 未运行 | 未运行 | 未运行 | 未运行 |

没有新速度提升、节点相对收益或稳定性结论。没有实际同步训练，域吞吐合计即使日后测得也不含梯度通信。原 `peak_mem_GB` 口径保留为 legacy 指标，在新汇总中明确命名 `legacy_peak_mem_GB`；它是生命周期 RSS/历史峰值字段，不能视作 HBM 驻留或总内存。

没有运行期间 per-core 采样、36/38线程比较、内存放置诊断或 HBM容量测量；原因是本窗口明确只执行本地部分。SKIP_BUSY 仍可能漏掉突发负载，不归咎于其他用户或硬件。真实 DDR/HBM 分列、hugepage占用/高水位与测量方法、SIGBUS/OOM排查仍须远程补齐。

## 6. 接受条件与限制

已完成：前置身份校验；原版安全缺陷见证；候选失败传播、完整计数、旧结果隔离、有界 barrier；本地进程/文件协议测试；模型静态计算边界检查；最小 diff 检查；共享文件完整性与交付哈希。

未完成：Bash 语法/集成、Linux进程组/真实 affinity、目标 torch/KML/preload 运行时、真实训练步数值、单域→四域→整节点、CKPT+HBM、三真实有效轮、第二主机和慢域原因。它们不属于本地已接受结论。**未达到完整 S01 或原计划 M1/A1 的集群门槛。**

分配器源码修改明确归 S03。`HBM_HANDOFF.md` 留存 nfree=0..15 无符号转换和策略调用错误处理的静态疑点；没有修改/编译 allocator，也未将疑点认定为历史 SIGBUS 根因。

建议总协调先复核 `S01_LOCAL_RUNNER_20261104` 的本地交付；在 Linux shell/进程组及集群运行链补验之前，不标记“运行器正式接受”、不让下游声称性能通过。没有请求新的全局 batch、学习率、模型或资源预算决策。后续测试资源与连接由 S00/总协调安排。

可复用产物是四文件 candidate、严格汇总接口、测试、合成证据和 RUNBOOK。候选 `PASS` 只限于完整性与旧 A1 波动定义，不能代替数值/科学/性能/生产验收。回退只需停止引用 S01 候选，不存在共享代码或正式 manifest 的回滚。

## 7. 证据索引

交付根绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01`。下表均为实际文件；完整逐文件 SHA256 在 ARTIFACT_SHA256.txt，索引本身不自哈希。

| 产物 | 绝对路径 |
|---|---|
| 报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\REPORT.md` |
| 全交付哈希 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\ARTIFACT_SHA256.txt` |
| 候选入口 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\run_node16.sh` |
| 模型候选 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\s4_models.py` |
| 协议/监督/汇总 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\runner.py` |
| 最小diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\minimal.diff` |
| 复现/接口 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\RUNBOOK.md` |
| S03交接疑点 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\HBM_HANDOFF.md` |
| 基线身份检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\baseline_validation.json` |
| 共享文件起点 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shared_before.json` |
| 共享文件终态 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shared_integrity.json` |
| 源码/候选哈希 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\source_hashes.json` |
| 本地环境 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\environment.json` |
| shell未运行证据 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shell_status.json` |
| 原版五种缺陷 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\legacy_safety_before.txt` |
| 候选最终正常套件 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\tests_after.txt` |
| 候选测试源码 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\tests\test_runner.py` |
| 8场景最终索引 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\local_exercise_index.json` |
| 最终原始子进程日志/JSON/退出状态 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\SYNTHETIC_20261104T074206918024Z\INDEX.json`，各目录由此索引 |
| Python语法检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\syntax_check.json` |
| diff可应用检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\patch_check.json` |

没有远程实测日志可索引；没有向其他聊天发消息，由用户将报告路径交回总协调复核。
