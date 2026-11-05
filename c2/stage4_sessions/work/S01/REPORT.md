# S01：可靠运行器本地候选及远程快照对照

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — LOCAL_ONLY / SHELL_NOT_TESTED / CLUSTER_NOT_RUN**。

版本：`S01_LOCAL_RUNNER_R2_20261104`。本轮按最新 STATUS 与 S00_REMOTE_REVIEW 补齐远程诊断差异；提交供总协调审核，未获运行器正式接受、未集成或部署。

## 1. 结论

已完成本地失败处理、结果完整性与有界 barrier 候选，并对照归档及两份远程启动器确认基线。正常本地套件共 **39 项：38 通过、1 项 Linux 分支跳过**；另有 **8 个真实 Python 子进程驱动的合成协议场景**符合预期。缺域、过期/损坏 JSON、非零退出、超时、配置错和部分工作负载均不能得到 PASS。

保留远程新增的核心数上限、faulthandler 与故障日志诊断；显式禁用只有哈希、没有源码的 sample_foreign.py，不静默调用未知共享脚本。两份 legacy demo 的文件哈希已固定，输入标签强制为 LEGACY_TIMING_ONLY；没有修正数据，也没有宣称16电极目标配对或科学训练正确性通过。

本次没有新的模型数值、集群性能或加速结论。建议接受为本地可复核候选；Linux/shell、真实运行链及单域→四域→整节点复测仍须补齐。

## 2. 前置条件与执行范围

已先读最新 `c2/stage4_sessions/work/COORDINATION/STATUS.md`，再读 sessions README、S01_STABILITY、REPORT_TEMPLATE、S00_REMOTE_REVIEW、S00/REPORT、两份远程快照及两个 diff，并核对相关源码、manifest、输入身份与既有 S01 内容。原阶段四计划及交接中的集群/性能任务边界不变。

前置接受状态为 **ACCEPTED_EVIDENCE_HANDOVER / NEW_NUMERICAL_AND_PERFORMANCE_ACCEPTANCE_PENDING**。本次重新核对 S00 的87项交付索引和25份冻结源码/原文件，全部一致。本轮读取的已接受S00报告 SHA256 为 `8c10b0b2182608eba42eeaa14285d6ee05c9d9f088e9b1bd51fc44ccd3deec08`。这些是已保存快照的证据，不代表共享脚本此刻未变化，亦不把当前目录存在解释为总协调已接受。 S00随后完成文档收尾，并把该已接受报告逐字节保存在 `work/S00/evidence/REPORT_ACCEPTED_HANDOVER_20261104.md`；本窗口核对其SHA仍相同。当前收尾报告SHA为 `b67004b15bdca8e998be3dc8d9e10fa12eedc2b89a1949af7727f1fbb94cfa23`，终态91项S00交付索引另行校验一致。已阅读新增PENDING_ITEMS.md，待补环境/输入/split不因收尾而解决。

本轮开始先验证已有 S01 索引中707项全部匹配，再连同原索引完整复制到：

`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\archive\v1_20261104T092419965264Z`

旧报告 SHA256 仍为 `894462a84f3203747dfbdbb752f14c541ece243ed6de1b80743b976e58bbe0ad`。归档保留旧候选、报告、测试与原始证据；当前 REPORT 是本次更新后的审核入口。

所有写入仅在 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01`。本轮起点记录324个共享文件；终态通用guard检出其中 **5个S00收尾文件变化、319个起点文件未变**。经只读复核，这5项为S00报告/运行说明及索引/校验元数据更新，源码、远程启动器/输入快照等关键payload均未变；108个原始文件仍与S00起始基线全部匹配。新增的S00收尾文件另列于shared_integrity.json，起点快照没有重置。external_updates_review.json保存逐项前后SHA、更新副本及当前索引独立复核；通用guard的非零退出保留，不冒称所有共享文件未变。本窗口没有修改阶段二/三、冻结数据、其他任务目录、共享源码、库或manifest。真实corpus未在本窗口逐文件核验。

模型/KML采用已与远程同哈希的 S00_LOCAL_ARCHIVE_20261104；启动器以保存的 **17:09快照**为差异基线。三份启动器的 Python 汇总段逐字相同。最小 diff `candidate/minimal.diff` 对 S00模型+17:09启动器生成，并新增 runner.py 与 legacy_inputs.json；kml_ops原样复制、不进入diff。

| 文件/版本 | SHA256 |
|---|---|
| S00 baseline/s4_models.py | `9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2` |
| 归档启动器 | `a21aafcd1a3384f4ab07b146f24f5ebcf0b2a1b25eb35b725e8d26db9c655979` |
| 远程17:00启动器 | `ea27c594dd61865dfbbd67e3bdda216fc8a63df4acb2cb363807be52d8f9ccaf` |
| 远程17:09启动器（本轮diff基线） | `0da6c46de4e4f7ac9694ba966af9ee23a4b63227137fea72f9c99b7e62f73e41` |
| candidate/s4_models.py | `512dc202e4c0d60363b57317ed612694b80a4d5d3467740ed582bcf600bf1d92` |
| candidate/run_node16.sh | `aaac8557b00abbf68a0e296e7119c0150c3fbfd467c42d132035ed69f929fd5f` |
| candidate/runner.py | `692113888fab4ac23c0188f39731ceea0f0fec1a8ef09f25cee872515ba7dd0b` |
| candidate/kml_ops.py | `e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26` |
| candidate/legacy_inputs.json | `24df1ad655fa3263efaf1ec8a721074fdfbae15fcb1d054b30d88bf5b9734835` |
| candidate/minimal.diff | `cf0adc672631916d6c8535f4be21a02ccbcf41385169c061b664726b484a0533` |

绝对路径映射在 `evidence/source_hashes.json`。模型文件保留CRLF，shell/新增辅助文件为LF。`git -c core.whitespace=cr-at-eol apply --check` 在S01内独立副本上退出0；未将补丁应用到共享代码。

远程诊断逐项处理：

| 远程新增行为 | 本候选决定及验证 |
|---|---|
| CORES_PER_DOM | 保留默认99，在affinity/忙核过滤后截取前n核；36核选择及过滤顺序已有行为检查，未测36/38性能 |
| PYTHONFAULTHANDLER=1 | shell入口和worker环境均保留；合成子进程实际断言faulthandler已启用 |
| 故障关键词grep | 保留关键词含SIGBUS相关文本，改为状态中diagnostic_matches；总匹配数+末20条，每条至多1024字符。退出码/完整结果仍是成功判据 |
| SAMPLE_FOREIGN | 源码未取回，明确默认0，manifest记录source unavailable；设为1或其他非0值预检拒绝。仅有哈希不允许调用 |
| foreign.log轮次时间 | 不伪造采样日志；逐进程started/finished保留时间索引。没有运行期间忙核采样证据 |
| pids与wait | 用逐PID监督/超时/退出状态替代仅等待一串PID；失败只清理本次创建的子进程/session |

当前账号对共享项目目录只读，远程独立路径准备稿改为 `/home/share/dengqingtian/opt/stage4_sessions/S01/<unique_run_id>/`。共享owner目录仅作只读依赖来源；本轮没有创建远程目录。

## 3. 环境、复现方式与成本

| 项目 | 本次实际情况 |
|---|---|
| 本机 | DESKTOP-54BJCD6；Windows build26200/AMD64；Python3.11.9 |
| Python路径 | C:\Users\A\AppData\Local\Programs\Python\Python311\python.exe |
| 依赖 | 当前Python无torch/numpy；未安装包、未加载KML/HBM |
| 执行时间 | 起点见revision_start.json；最终合成检查的UTC起止见local_exercise_index.json（+8为北京时间）；终态见shared_integrity.json |
| Bash | 找到Git Bash，但启动NtCreateDirectoryObject失败，0xC0000022，退出3221225794；当前候选shell语法/集成未运行 |
| Linux | 进程组/后代清理检查在Windows跳过；numactl、真实affinity/NUMA与preload链未执行 |
| 集群/job/成本 | 本窗口未探测SSH、未连接集群、未新增作业；节点小时0、GPU小时0；连接与性能由S00窗口负责 |

可复制的本地正常验证命令（项目根执行）：

```powershell
python -B c2\stage4_sessions\work\S01\tests\test_runner.py
python -B c2\stage4_sessions\work\S01\tests\test_remote_delta.py
python -B c2\stage4_sessions\work\S01\exercise_local.py
```

旧行为的缺陷见证另行执行：

```powershell
python -B c2\stage4_sessions\work\S01\tests\test_legacy.py
```

该命令预期退出1：五类安全断言在三份基线上共15次失败。它是红色缺陷证据，不是候选正常门槛失败。当前辅助与测试Python语法编译9份通过。

后续入口、库/输入布局、Linux指定分支检查、严格汇总接口与准备稿命令在 RUNBOOK.md；没有提交调度器命令或新增资源授权。S00历史建议预算仍需统一排期。

正式入口固定CPU/fp32、GN=SAMPLING=0。模型计算不变：encoder12层/512宽/8头、原U-Net和AdamW、seed0、原随机初始化/随机变量、每belt无条件pre/dec各2步预热、REPS默认5。拟复测batch32/64、累积1、KML_LINEAR=1、原损失定义不变；本次未实际执行这些训练配置。无DDP，不将域数×microbatch称为有效全局训练批量。

legacy_inputs.json固定S00已保存的两个原始文件SHA：

- s0322p0：`4bb9cfaffa8f7d464d1efd80a45e98edd2cf990179b923c160573078f97bfdad`
- s0322p1：`a5db12595bb7486a9a86e4f9bce9a0680876d2a732bc5f05d361c7b9657737c0`

本窗口未取回NPZ；这里只固定已接受证据中的身份，候选运行前必须逐文件匹配，并逐轮复查输入/脚本/源码/preload与KML库哈希。S00已确认两份demo images均来自32电极源、不同于16电极源，故仅用于legacy timing，不能推导冻结corpus错误。修正配对协议归S02；本候选没有改数据。

## 4. 正确性

| 检查 | 预先定义的判断 | 实测与证据 | 状态 |
|---|---|---|---|
| 原版/快照缺陷 | 缺域、过期、失败标记、部分输出或仅一轮不能PASS | 三份相同汇总段各违反五类要求；legacy_safety_before.txt | 缺陷复现 |
| 候选基础套件 | 缺/坏/旧/多结果、配置/身份/运行时错、零核心、失败/超时均不能PASS | test_runner.py：31通过、1 Linux跳过；tests_after.txt | 本地通过/一项未运行 |
| 本轮远程差异 | 快照SHA与汇总一致、核心上限、显式禁用sampler、faulthandler、故障摘要、输入标签及文件身份 | test_remote_delta.py：7通过；先有remote_delta_before/legacy_identity_before失败证据，再实现 | 本地通过 |
| 实际子进程协议 | 完整三轮退出0；七类异常非零退出且停止后续轮次 | 8/8符合预期；local_exercise_index.json | 本地通过 |
| barrier | 期望rank/run_id精确匹配、peer abort、有界deadline | 正常、旧标记、多余rank、超时/同伴失败通过；子进程实际经过四个phase | 本地通过 |
| 清理边界 | 只停止本次子进程，独立对照进程存活 | 真实子进程失败/超时检查通过；Linux session/后代分支跳过 | Windows通过；Linux未运行 |
| 结果自洽与原子发布 | 正有限值；rate×step=batch相对容差1e-9；坏写入不覆盖完整结果 | 重复键、NaN/Inf/布尔/零负值、PID/时间/配置错误均拒绝；mtime只容许±2秒文件系统精度余量 | 本地通过 |
| 模型代码边界 | 除同步/输出/相关import与废弃SYNC赋值外，计算AST完全一致；KML字节相同 | tests_after.txt；模型候选本轮未再改动 | 静态通过 |
| 输出/loss | 真实相同输入/权重/固定随机变量，预先定义科学误差 | 无模型执行、无误差数字 | 未运行 |
| 输入/参数梯度 | 逐应有梯度、缺失/NaN/Inf检查及预定误差 | 无张量运行 | 未运行 |
| optimizer更新/状态、state_dict/dtype | 一次原AdamW更新及逐状态兼容 | 未运行；不能以AST一致替代 | 未运行 |
| 当前候选shell/实际导入/动态库 | 可执行Bash/numactl/目标torch与KML | 本机Bash启动失败；S00对旧快照bash -n成功不能覆盖本候选 | 未运行 |
| 最小diff/源码冻结 | 对明确模型+17:09启动器独立副本apply --check成功、共享哈希不变 | patch_check.json；shared_integrity.json；external_updates_review.json | 关键基线通过；通用guard检出并行文档变化 |

合成协议场景使用2个真实Python子进程，吞吐/步时/内存数字完全由测试指定；它不是单域/四域C2数值或性能测试。当前最终场景为：

`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\SYNTHETIC_20261104T092733816606Z\INDEX.json`

当前结果标签为SYNTHETIC_RUNNER_PROTOCOL_ONLY；正式入口结果标签固定LEGACY_TIMING_ONLY，并要求manifest与结果一致。早先版本的合成证据保留作过程记录，不使用其缺少新协议字段的JSON通过本轮门槛。

## 5. 性能与内存

没有新的C2性能、负载或DDR/HBM实测；下表不填合成数据。

| 待复测配置/工作负载 | 域数/有效结果 | 批量/精度 | 总步/吞吐/最慢域参考 | DDR/HBM | 状态 |
|---|---|---|---|---|---|
| B32+HBM，16-pre | 未运行 | 拟每进程32/fp32 | 未运行 | 未运行 | 未运行 |
| B32+HBM，16-dec | 未运行 | 同上 | 未运行 | 未运行 | 未运行 |
| B32+HBM，32-pre | 未运行 | 同上 | 未运行 | 未运行 | 未运行 |
| B32+HBM，32-dec | 未运行 | 同上 | 未运行 | 未运行 | 未运行 |
| 32电极B64+CKPT+HBM，pre/dec | 未运行 | 拟每进程64/fp32 | 未运行 | 未运行 | 未运行 |
| 上项稳定后B32+CKPT+HBM，pre/dec | 未运行 | 拟每进程32/fp32 | 未运行 | 未运行 | 未运行 |

没有同主机A/B、三有效性能轮、第二主机或36/38核心收益；没有运行期间per-core采样、实际内存放置/hugepage使用量或慢域原因置信结论。SKIP_BUSY仍只是启动前lifetime-average快照，不能排除突发外部负载。

保留历史 `peak_mem_GB` 并在聚合输出标为legacy_peak_mem_GB；它不能代表hugetlb HBM驻留、独立belt峰值或总内存。DDR/HBM需另外测量。没有同步训练，未来域吞吐合计/期望域数×最慢域仍不含梯度通信。

S00最新复核中B64/preferred第2轮缺整个域JSON、四项均无效；DDR B32的16-dec三轮波动5.607291%失败；HBM B32仅两轮。这些是已保存历史证据的结论，本次未重跑集群，不提升为新性能基线。

## 6. 接受条件与限制

已完成本地前置身份审查、旧产物完整归档、快照差异逐项记账、失败检查先行、退出状态/结果身份与集合/逐轮停止/原子发布/有界barrier、诊断保留、legacy输入身份固定、局部回归、diff与共享哈希检查。

当前候选至少要求三轮完整结果，前两轮仅INCOMPLETE；任一缺域/失败/超时/配置错即FAIL且不输出可误用的聚合性能数字，完整但波动>5%返回UNSTABLE及非零退出码。PASS只表示运行器完整性和旧A1波动定义通过。

仍未完成Linux进程组、shell、实际库加载/计算节点affinity、真实数值、HBM/SIGBUS/OOM、单域→四域→整节点、三真实有效轮和第二主机。**未达到完整S01/M1/A1集群接受门槛**。本轮不请求更改全局batch、学习率、训练计划或新增算力；连接与后续实验仍由S00/总协调安排。

HBM分配器源码/算法修改归S03；HBM_HANDOFF.md保留低hugepage数无符号转换与mempolicy调用失败的静态疑点，未编译或证实历史根因。运行器能传播失败，不能替代allocator修复。16电极目标配对修正归S02，原demo只用于legacy timing。

建议总协调复核本轮五文件候选、测试与诊断决策后，再安排缺失验证；未接受前下游不得称为正式接受运行器。回退只需停止引用S01候选；没有共享代码、生产默认或manifest变更需要回滚。

## 7. 证据索引

任务绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01`。完整逐文件SHA256见ARTIFACT_SHA256.txt；根索引本身不自哈希，旧归档索引也被纳入本次索引。

| 产物 | 绝对路径 |
|---|---|
| 当前报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\REPORT.md` |
| 全交付哈希 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\ARTIFACT_SHA256.txt` |
| 候选入口 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\run_node16.sh` |
| 协议/监督/汇总 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\runner.py` |
| legacy身份 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\legacy_inputs.json` |
| 最小diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\candidate\minimal.diff` |
| 复现与后续Linux指定检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\RUNBOOK.md` |
| 当前前置验证 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\baseline_validation.json` |
| 快照/诊断处理/输入范围 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\remote_baseline_review.json` |
| 原有707项验证与归档起点 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\revision_start.json` |
| 共享文件起点/终态 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shared_before.json`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shared_integrity.json` |
| 并行收尾变化复核 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\external_updates_review.json` |
| 源码/快照/候选SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\source_hashes.json` |
| 本机环境/Bash失败 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\environment.json`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\shell_status.json` |
| 三份基线15次预期失败 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\legacy_safety_before.txt` |
| 基础正常检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\tests_after.txt` |
| 新增检查修复前/后 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\remote_delta_before.txt`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\remote_delta_after.txt` |
| 输入身份修复前见证 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\legacy_identity_before.txt` |
| 最终8场景索引 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\local_exercise_index.json` |
| 当前原始日志/JSON/退出状态 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\SYNTHETIC_20261104T092733816606Z\INDEX.json`（包含各场景绝对路径） |
| 语法/diff检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\syntax_check.json`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\evidence\patch_check.json` |
| S03交接 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\HBM_HANDOFF.md` |

没有本轮远程日志/实测JSON可索引；未向其他聊天发消息，由用户将本报告绝对路径交总协调审核。
