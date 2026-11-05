# S02 第二轮：真实完整模型一步检查未通过

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — FULL_MODEL_NUMERICAL_FAIL / TRAINING_MEMORY_NOT_RUN / LOCAL_ONLY / CLUSTER_NOT_RUN**。

## 1. 结论

实际安装并运行CPU torch2.7.1+cpu/NumPy2.2.6。首个完整模型配置为16_adjacent/pre、有效B64、B32×2、CKPT0、fresh、fp32。参考和候选均已执行前向、反向及一次AdamW更新，**未通过首轮事先固定的数值容差**。没有缩模型、少算样本或放宽阈值。

首轮原检查在loss处失败：max_abs=3.0517578125e-05，高于2e-5；relative=1.0070243979857095e-07。同配置追加一次诊断，仅收集所有原比较失败，未改模型/候选/计算/容差；权重与全部固定输入/随机变量SHA和第一次一致。诊断共194个比较未过，涉及loss、49个参数梯度、13个更新后参数、33个参数增量、98个AdamW moment张量。输出与输入梯度本次逐位相同，但不足以接受更新等价。

按NEXT_ROUND的失败停止规则，没有扩大到16-dec/32/CKPT/seeded，也没有在数值未过时测训练峰值。当前停止点是数值门槛，已不再是首例内存不足。M2未通过、不建议集成。

## 2. 前置条件与范围

读取STATUS、NEXT_ROUND、ROUND1_REVIEW和ROUND1_ACCEPTED_FILES；核对S02首轮报告/候选/测试/协议/模型及60项索引SHA。首轮根REPORT仍为`e47a6b2d8c5217a9866bf2dd2c834f2d6c43ab392d06b241c6d9862cca4a14b5`，全部保持不变。

仅写`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z`。accepted baseline/candidate/check_equivalence/fixture/容差协议逐字节复制，本轮计算源码不改。数值脚本SHA=`e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`，训练步SHA=`524e35817080a3f28a0bc0cda8ecce9c8264b15d73edebe05c5d9d8b9632a0aa`。

新增资源保护入口run_16_representative.py、小检查probe_runtime.py和诊断tests/diagnose_same_config.py。诊断只拦截原compare抛出的断言以收齐失败列表，保留小张量负控原行为；有任何失败即退出1、标FAIL_DIAGNOSTIC，不能用它产生放宽后的PASS。两份新增diff在candidate目录。

19:59时资源不足的本轮早期报告及28项文件已按当时SHA完整保存到history/resource_blocked_20261104T123753Z，原报告SHA=`b5c16e69b06eb8a41464af83c43d8e3475fa370d6adee75189c4b60275ab4772`。早期资源拒绝记录仍保留。

阶段二/三、冻结corpus、原demo、正式manifest/批量/LR/schedule、HBM/KML、共享入口与其它任务未改。没有SSH、上传、集群作业、生产部署或Git提交。终态原文件/接受身份见delivery_validation.json。

## 3. 环境、命令与成本

Windows DESKTOP-54BJCD6，AMD64，16逻辑CPU、31.052GiB物理内存。本轮`.venv\Scripts\python.exe`为Python3.11.9，实际torch2.7.1+cpu、numpy2.2.6；pip check通过，pip freeze与核心二进制SHA留档。torch报告MKL2025.1/MKL-DNN3.7.1/OpenMP2019、USE_CUDA=0；不是C2/KML环境。

torch线程4、interop8；没有NUMA绑定、KML或HBM。所有本机时间均不作为C2性能。新增节点小时0、GPU小时0、作业0。依赖从官方CPU索引安装，初次沙箱网络失败后经工具自动批准的网络执行成功；没有自动审批拒绝事件。

代表配置：完整12层/512/8编码器、原U-Net、64×64目标、M208、fp32、seed0、AdamW lr1e-4/betas0.9,0.999/eps1e-8/weight_decay0.01。每个参考/候选从同一权重和fresh状态出发，整批mask/t/noise/idx固定；S02_PAIRED_BELT_V1合成输入。无DDP，有效全局训练batch不适用。正式训练归一化/split尚未决定。

```powershell
Set-Location 'E:\eitfm_c2_stages2-4_2026-11-03'
# 原始严格检查：当前配置已运行，退出1。
& 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe' -B 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\run_16_representative.py' --part pre
# 同一配置诊断：收集所有原阈值失败，不改变算法；已运行，退出1。
& 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe' -B 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\run_16_representative.py' --part pre --diagnostic
```

原检查北京时间20:33:34–20:34:02，外层总墙钟28.015秒；诊断20:35:56–20:36:28，32.031秒。含两路计算、快照和比较开销，**不是训练step耗时，不能换算吞吐或收益**。资源保护仅监视本机剩余物理/提交额度，若过低只终止本任务确切子进程；两次实际计算均正常结束、退出1，无OOM/超时/保护终止。

## 4. 正确性

沿用VALIDATION_PLAN，不放宽。max_abs与L2 relative=`||c-r||2/max(||r||2,1e-12)`逐张量检查；norm<=1e-8只判绝对值。输出/loss/梯度/参数/增量绝对≤2e-5、relative≤2e-6；moments绝对/relative≤2e-6。其余keys/shape/dtype/step及应有梯度集合严格检查。

同配置完整诊断结果如下。各行最大绝对与最大相对可能来自不同张量，不能拼为一个张量的误差。state行不包含精确整数step比较。

| 对象 | 已比较张量/失败数 | 最大绝对差 | 最大L2相对差 | 结论 |
|---|---|---:|---:|---|
| loss | 1/1 | 3.05176e-5 | 1.00702e-7 | 绝对阈值失败 |
| 输入v/y0梯度 | 2/0 | 0 | 0 | 本例通过 |
| h/voltage/coarse输出 | 3/0 | 0 | 0 | 本例通过 |
| 应有参数梯度 | 153/49 | 1.02234e-2 | 1.14082e-5 | 失败 |
| 更新后参数 | 299/13 | 3.66643e-5 | 8.11271e-3 | 失败 |
| 相对初值的参数增量 | 299/33 | 3.66643e-5 | 8.11271e-3 | 失败 |
| AdamW exp_avg/exp_avg_sq | 306/98 | 1.171875e-2 | 2.31473e-5 | 失败 |

没有缺失/非finite/shape/dtype或inactive-state/step断言异常；预训练decoder无梯度和无更新的断言执行通过。全mask为空的拒绝检查在诊断中也执行通过。两次运行初始权重与v/y0/idx/mask/t/noise哈希完全一致，见numerical_summary.json及两个equivalence.json。原检查仍保留首次loss失败，而不是用诊断覆盖它。

例如mask_tok梯度绝对差9.765625e-4但相对8.38826e-8，属于原规则绝对门槛失败；部分LayerNorm梯度相对差也超过2e-6，因此不只是loss绝对阈值问题。部分self_attn.in_proj_bias更新差异被fresh AdamW放大；这是需要复核的实测现象。输出/输入梯度一致、参数梯度有差异与归约舍入及近零梯度对AdamW敏感相符，**这是解释方向，尚未完成因果隔离**。不据此自动放宽阈值、改eps/LR、冻结参数或换合成输入来获取PASS。

其它已运行检查：真实torch小张量autograd/AdamW负控通过；完整模型meta实际参数计数encoder37,995,777、decoder29,416,449与解析清单一致。它们不能覆盖本次完整模型失败。真实NPZ/sidecar适配与真实输入一步检查仍未运行。

## 5. 性能与内存

| 配置 | 有效结果 | 整步时间/吞吐 | 训练峰值/DDR-HBM分解 | 状态 |
|---|---|---|---|---|
| 16-pre/B64对B32×2/CKPT0/fresh | 1项严格配置已运行、未通过；另1次同配置诊断 | 未测 | 未测 | NUMERICAL_FAIL |
| 16-dec/32/CKPT/seeded及其余矩阵 | 未运行 | 未测 | 未测 | 首例失败后不扩大 |
| 独立轻量训练内存测量 | 未运行 | 未测 | 未测 | 等待数值门槛 |

19:54初次启动资源不足，标NOT_RUN_RESOURCE_GUARD；20:33首例启动时可用物理约16.39GiB、提交22.97GiB，已满足该配置工程保护门槛。guard_samples只用于安全监视和记录整机剩余资源，**不能作为训练进程峰值**。保留参考快照的脚本不能用于证明4GB工作集或内存收益。

没有C2/hugetlb/HBM、四域/整节点、三有效轮、第二主机或同步训练结果。静态参数清单此次有真实torch计数支持，但激活/workspace/生命周期仍未测，不给S03虚构实际热度或同时占用数据。

## 6. 接受条件与下一步

已完成真实运行环境、固定代表配置严格执行、首次失败证据与同配置完整诊断；首轮接受文件及108个原文件保持不变。**本例不符合预定容差，不能接受数值等价，不能进入“数值通过后”的内存阶段，也不建议集成。**

下一步应先复核参数梯度归约与fresh AdamW近零梯度敏感性，确定是否存在可在原规则下通过的计算修复；若提出改变度量/容差，必须带明确依据交总协调另行评审，当前不自动更改。保持原模型、loss、样本、有效批量与optimizer定义，不擅自调整正式schedule。真实输入与正式split/统计前置仍另列，合成检查不升级为科研质量验证。

此前资源不足说明见ENVIRONMENT_REQUEST，已加状态更新：首例本机资源现已可用，当前阻塞是数值门槛。没有需要用户关闭进程的动作，没有清理或结束其它程序。回退为停止使用本轮独立目录，首轮源无需回退。

## 7. 证据索引

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z`。逐文件SHA见ARTIFACT_SHA256.txt；venv/cache不整目录哈希，核心二进制与依赖版本见RUNTIME_SHA256.txt、pip_freeze.txt。

| 产物 | 绝对路径 |
|---|---|
| 本补充报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\REPORT.md` |
| 首个严格结果 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\evidence\20261104T123334613760Z_pre\equivalence.json` |
| 同配置完整诊断 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\evidence\20261104T123556349698Z_pre\equivalence.json` |
| 汇总与固定哈希一致检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\evidence\numerical_summary.json` |
| 运行命令/退出码/安全采样 | 上述两次结果目录各有run.json、stdout_stderr.txt、guard_samples.jsonl |
| 诊断程序 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\tests\diagnose_same_config.py` |
| 保护入口及diff | 同根run_16_representative.py、candidate/resource_guard.diff、candidate/diagnostic.diff |
| 真实运行时/小检查/参数计数 | 同根probe_runtime.py、evidence/runtime_probe.json、runtime_probe_stdout_stderr.txt、dependency_check.txt |
| 依赖安装与冻结 | 同根evidence/torch_install_network.txt、numpy_install.txt、pip_freeze.txt，RUNTIME_SHA256.txt |
| 前置/末次核验 | 同根evidence/start.json、delivery_validation.json |
| 早期资源拒绝版本归档 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\history\resource_blocked_20261104T123753Z` |

没有向其它聊天发送消息或改协调状态；报告由用户交总协调审核。
