# S02 第二轮：真实 torch 运行与资源门禁

日期：2026-11-04（Asia/Shanghai）。

状态：**WAITING_DEPENDENCY — TORCH_RUNTIME_READY / FULL_MODEL_NOT_RUN_RESOURCE_GUARD / TRAINING_MEMORY_NOT_RUN / CLUSTER_NOT_RUN**。

## 1. 结论

已将“无torch”缺口补齐：在本轮独立目录建立CPU torch2.7.1+cpu和NumPy2.2.6环境，实际导入成功，运行首轮脚本中的真实小张量autograd/AdamW负控通过；在torch meta设备构造完整模型，实际参数计数与解析清单一致。

**完整模型B64/B32×2的一步等价检查尚未运行。** 首个16电极pre代表配置被启动前资源门禁拒绝：当时仅约2.87GiB可用物理内存、3.09GiB可用提交额度。该结果是NOT_RUN_RESOURCE_GUARD，不是OOM，不是数值失败，更不是等价通过。遵守“数值通过后再测内存”，未运行训练峰值/时间测量，也未扩大矩阵。

任务仍未完成，需要释放本地资源或S00交付适用计算资源；具体命令、门槛和停止条件见ENVIRONMENT_REQUEST.md。没有4GB达标或性能提升结论。

## 2. 前置条件与执行范围

已读最新STATUS、NEXT_ROUND、ROUND1_REVIEW及ROUND1_ACCEPTED_FILES，核对其中S02报告/候选/测试/协议/模型SHA和首轮60项交付索引。完整初检记录见evidence/start.json。首轮报告SHA仍为`e47a6b2d8c5217a9866bf2dd2c834f2d6c43ab392d06b241c6d9862cca4a14b5`，本轮不覆盖该报告、索引或清单指向的任何文件。

本轮独立根为`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z`。从已接受版本逐字节复制baseline、candidate、两份数值测试、配对/容差文档和静态内存清单；训练步、loader、模型、完整数值检查均未改动。新增的run_16_representative.py仅在独立进程外执行资源/时限保护，调用原B64对照脚本；diff见candidate/resource_guard.diff。

所有本轮写入都在上述目录，包括虚拟环境、下载缓存、证据和补充报告。没有改模型结构、学习率、正式批量、分配器、共享入口、其它任务、阶段二/三、旧demo、冻结corpus或正式manifest；末次原文件/接受文件核验见delivery_validation.json。没有SSH、上传、部署、作业或Git提交。

## 3. 环境、复现方式与成本

| 项目 | 本次实际结果 |
|---|---|
| 本地主机 | DESKTOP-54BJCD6，Windows AMD64，16逻辑CPU；系统物理内存31.052GiB，初查提交上限44.052GiB（会变化，最终快照见resource_latest） |
| 解释器 | 本轮`.venv\Scripts\python.exe`，Python3.11.9，包路径完全在本轮目录 |
| 实际运行库 | torch2.7.1+cpu、NumPy2.2.6；pip check无依赖冲突，pip_freeze.txt冻结依赖 |
| torch构建报告 | MKL2025.1、MKL-DNN3.7.1、OpenMP2019、CPU能力报告AVX512、USE_CUDA=0；这是torch构建/运行配置报告，不是C2工具链证明 |
| 小检查线程 | torch线程4、interop8；无C2 affinity/NUMA绑定，无KML/HBM，CPU fp32 |
| 时间 | 开始UTC=2026-11-04T11:49:49Z，真实torch检查约11:52:43Z，代表配置门禁11:54:26Z；最终复核见delivery_validation，上海时间UTC+8 |
| 安装 | CPU torch固定2.7.1，NumPy固定2.2.6；默认沙箱下载因网络访问失败，获工具自动批准的网络执行后成功；没有自动审批拒绝事件 |
| 成本 | 本机依赖安装/小检查；新增节点小时0、GPU小时0、作业0，无训练超时/OOM消耗 |

固定torch版本与C2历史版本号对齐，Windows MKL原生后端仍不同于C2/KML；不能据此接受C2性能。包来自[PyTorch官方CPU索引](https://download.pytorch.org/whl/cpu/torch/)，实际安装来源/版本与日志见torch_install_network.txt、numpy_install.txt和runtime_probe.json；没有安装torchvision/torchaudio/CUDA。

代表配置命令（当前会因资源不足退出3）：

```powershell
Set-Location 'E:\eitfm_c2_stages2-4_2026-11-03'
& 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe' -B 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\run_16_representative.py' --part pre
```

固定16_adjacent/pre、有效B64、microbatch32、累积2、CKPT0、fresh、seed0、原完整12×512/8与U-Net/64×64、配对合成协议S02_PAIRED_BELT_V1、原预定容差；模型执行前要求12GiB可用物理、16GiB可用提交。16-dec保护线20/24GiB。保护线是工程预留而非实测内存，不改变训练数值设置；未满足时不启动模型。运行中低于1/2GiB剩余额度停止确切子进程，pre/dec时限900/1800秒。

## 4. 正确性

| 检查 | 预定标准 | 实际结果 | 证据 | 状态 |
|---|---|---|---|---|
| torch/NumPy真实导入 | 指定独立环境、实际模块来源 | 2.7.1+cpu/2.2.6加载成功；pip check通过 | runtime_probe.json、pip_freeze.txt、dependency_check.txt | 通过 |
| 小张量真实autograd/AdamW | 原loss_unit_checks：整批与正确分母累积一致，错误mean反转梯度并改变更新；缺失/NaN/Inf比较器拒绝 | PASS_REAL_AUTOGRAD_UNIT_ONLY | runtime_probe.json，沿用原检查源 | 小检查通过；不属于完整模型验收 |
| 完整模型参数计数 | 与static_memory一致 | encoder37,995,777、decoder29,416,449，精确一致 | runtime_probe.json | 实际torch meta计数通过，无模型前反向 |
| 首轮接受身份 | SHA精确匹配，原文件不变 | 初检通过，终检见delivery_validation | start.json、delivery_validation.json | 通过 |
| 完整输出/loss/输入及参数梯度 | 原VALIDATION_PLAN的max_abs/L2容差 | 未运行，无误差数值 | 首个代表配置run.json | NOT_RUN_RESOURCE_GUARD |
| 完整AdamW一次更新/state_dict/CKPT | 原逐键/参数增量/moments/step检查 | 未运行 | 同上 | 未运行 |
| 真实NPZ配对与一步数值 | 可信源SHA/sidecar与逐行映射 | 无真实输入文件，本轮未适配/未下载 | INPUT_PAIRING_PROTOCOL、ENVIRONMENT_REQUEST | 未运行 |

小检查使用真实torch张量/优化器，不是桩；meta参数计数不算模型数值。没有缩小模型、减少B64样本、改变loss或放宽阈值。48组完整模型矩阵仍未运行，第一代表配置资源不满足后停止扩大。

## 5. 性能与内存

| 配置 | 域数/有效模型结果数 | 有效批量/精度 | 总步秒数 | 吞吐/最慢域 | DDR/HBM训练峰值 | 状态 |
|---|---|---|---|---|---|---|
| 16-pre B64对B32×2，CKPT0/fresh | 本机/0 | 64/fp32 | 未运行 | 未运行 | 未运行 | 资源门禁拒绝 |
| 16-dec及后续32/CKPT/seeded | 未运行/0 | 64/fp32 | 未运行 | 未运行 | 未运行 | 前一门槛未过 |
| 独立轻量训练内存入口 | 未运行/0 | 待数值通过后同配置 | 未运行 | 未运行 | 未运行 | 按执行顺序暂不启动 |

运行前Windows GlobalMemoryStatusEx实际记录可用物理/提交额度；它们是整机剩余资源，不是训练进程峰值，也不是HBM/DDR分解。首次resource_before记录约3.80/4.24GiB，启动门禁时约2.87/3.09GiB。未启动B64图，不称发生OOM；没有训练内存/时间收益、四域/整节点、三有效轮、第二主机或同步吞吐可报。

末次resource_latest快照为2026-11-04T11:58:16Z，可用物理约3.36GiB、提交约1.81GiB，仍不足启动条件。没有结束或干预本任务以外的进程。

静态内存清单此次获得真实torch numel支持，但激活/workspace/生命周期仍未测。数值检查保留的参考快照只能用于正确性；下一阶段需独立轻量训练入口，不用该脚本测训练峰值，不把普通Windows RSS当作C2 hugetlb/HBM总量。

## 6. 接受条件与限制

已完成：保留首轮接受文件；独立安装并运行真实torch；依赖一致性、小型autograd/AdamW负控、完整模型meta计数；真实内存资源核验；首代表配置启动保护及明确未运行记录；向用户提出资源信息请求，准备供S00转交的具体命令/门槛。

未完成：完整模型一步等价及其后训练内存测量、真实NPZ适配、C2/KML验证。当前限制是可用内存/提交额度，不再是缺torch。用户可释放本机资源后继续，或提供S00确认的独立计算环境；本窗口不关闭其它进程、不占用未知既有作业或登录节点，不增加远程算力授权。

未达到M2数值/内存/性能接受门槛，任务不能标完成，不建议集成。下一步固定先16-pre B32×2/CKPT0/fresh，再16-dec；正确且资源足够后才32/CKPT/seeded。失败停止扩大、保留误差，不自动放宽。真实输入/正式训练统计/split仍需协调资料，不能把合成检查升级为科研训练协议。原接受文件无回退需求；本轮可停止使用独立目录。

## 7. 证据索引

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z`。

| 文件 | 绝对路径 |
|---|---|
| 补充报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\REPORT.md` |
| 资源需求与继续命令 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\ENVIRONMENT_REQUEST.md` |
| 资源保护入口 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\run_16_representative.py` |
| 实际torch检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\evidence\runtime_probe.json` |
| 可复现小检查程序 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round2_20261104T114949Z\probe_runtime.py`；输出见evidence/runtime_probe_stdout_stderr.txt |
| 安装/依赖记录 | 同根evidence/torch_install.txt（初次网络失败）、torch_install_network.txt、numpy_install.txt、pip_freeze.txt、dependency_check.txt |
| 实际可用资源 | 同根evidence/resource_before.json |
| 首个代表配置未运行记录 | 同根evidence/20261104T115426066987Z_pre/run.json |
| 前置/终态核验 | 同根evidence/start.json、delivery_validation.json |
| 最小diff及哈希 | 同根candidate/resource_guard.diff、ARTIFACT_SHA256.txt、RUNTIME_SHA256.txt |

本轮哈希索引仅覆盖本轮源/文档/结果，不包含全部venv/cache文件；运行时来源/版本/pip freeze及核心二进制SHA另列RUNTIME_SHA256。没有更改首轮根索引。没有发外部消息或改协调状态。
