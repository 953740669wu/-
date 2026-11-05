# S02：计算等价性与内存优化准备

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — LOCAL_PREPARATION_ONLY / NUMERICAL_NOT_RUN / CLUSTER_NOT_RUN**。

## 1. 结论

已明确并实现独立的“整批分母、微批反传、一次 AdamW 更新”候选，交付预先固定容差的完整模型数值检查与解析内存分解。本地4项代数/AST/字节检查通过；默认Python与找到的三个隔离环境均无torch，**模型、autograd、AdamW及CKPT数值检查全部未运行**。没有新增性能或实际峰值结果，没有证明工作集进入4GB。建议接受为S02本地准备材料供评审，暂不集成或宣称数值验收通过。

关键结论：pre的masked MSE必须以整个有效批的mask总数归一化，不能简单平均微批mean；coarse分母为B×256，dec为B×4096。B64×1、B32×2、B16×4只是等价检查配置，每个有效批只做一次step，没有决定正式batch/LR/schedule。

## 2. 前置条件与执行范围

- 按指定顺序读取COORDINATION/STATUS.md及“交给S02的开场说明”，随后读取stage4_sessions/README、S02_WORKING_SET、REPORT_TEMPLATE、COORDINATION/S00_REVIEW、S00/REPORT、S00/INPUT_CONTRACT、项目README、STAGE4_HANDOVER、STAGE4_C2_PLAN和相关优化报告/源码。本次未找到同级INPUT_CONTRACT.md，依据S00报告索引定位到work/S00/INPUT_CONTRACT.md；未自行补造契约。
- 接受依据：`S00_LOCAL_ARCHIVE_20261104`，协调决定`ACCEPTED_LOCAL_ONLY / REMOTE_ACCEPTANCE_PENDING`。S00报告SHA256为`6275eb39ba3f7c1ff79a9b9a1aa719c826f1920dae83e957d57aa97378d7dc84`。全部依赖文件SHA见evidence/source_integrity_before.json和终态source_integrity.json。
- `s4_models.py`原件/S00冻结件/S02只读基线件SHA256均为`9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2`；`kml_ops.py`均为`e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26`。没有改模型文件；S02副本置于baseline目录。
- 候选为新加独立程序`candidate/training_step.py`，SHA256为`524e35817080a3f28a0bc0cda8ecce9c8264b15d73edebe05c5d9d8b9632a0aa`。最小diff为`candidate/training_step.diff`：新增训练步和与原源码相同的CKPT包装；原始模型的diff为空，没有共享入口修改。其余新增为测试/文档/审计与证据。
- 开始和结束均逐项核对S00记录的108个原文件、S00哈希索引52个交付物，结果见source_integrity*.json；没有改阶段二/三、原始报告、其它任务目录、分配器、共享库、冻结数据或正式manifest。本地没有真实corpus/NPZ，不能声称远程数据已验证。协调文档若并发更新，单列dependency_changes.json，不覆盖他人文件。
- 所有本任务交付物位于`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02`；没有远程路径创建、上传、作业或生产部署，没有Git提交。

## 3. 环境、复现方式与成本

| 项目 | 本次状态 |
|---|---|
| 本地主机/系统 | DESKTOP-54BJCD6，Windows build26200，AMD64 |
| 默认解释器 | `C:\Users\A\AppData\Local\Programs\Python\Python311\python.exe`，3.11.9，torch/numpy均不存在 |
| 隔离环境核查 | `E:\Codex\home\cache\phase2-speed-venv`、phase3-speed-venv、phase4-speed-venv：均Python3.11.9，有numpy、无torch；未修改这些环境 |
| 本地开始/结束 | 首次显式时间记录2026-11-04 15:32:10 +08（此前已开始阅读，精确开始时间未记录）；末次本地检查起止UTC见local_validation.json，交付复核时间见delivery_validation.json，UTC+8即上海时间 |
| C2/作业/DDR/HBM/NUMA | 未连接、未探测，无job ID；实际硬件、绑定、库、hugetlb驻留均未核实 |
| torch/KML/编译器/动态加载 | 无torch运行；KML/SME/oneDNN、编译器和动态库未运行/加载；未安装依赖 |
| 本地检查 | stdlib检查退出0；数值脚本依赖门返回退出2/NOT_RUN；Python源码语法检查通过，不能称运行时检查通过 |
| 成本 | 新增节点小时0、GPU小时0、作业0；没有连接排查/性能搜索/远程超时消耗 |

可复制的本地复核命令及后续真实torch/C2占位命令见RUNBOOK.md。完整数值脚本为`tests/check_equivalence.py`，SHA256为`d06a03b5c8e02b465f38c9cddf4169eabf14434b3156577b97e0da23a1abd3a9`。

准备的数值设置：seed0、完整12×512/8编码器、原U-Net、64×64目标、M208/928两个协议、CPU fp32，固定整批v/y0/angles/belt/mask/t/noise及同初始权重；每个参考从原始mean损失和CKPT0开始。有效单进程batch64、microbatch64/32/16、累积1/2/4、CKPT0/1、fresh/seeded optimizer两种历史，共48配置。所有配置尚未执行，逐项NOT_RUN见planned_matrix.json。seeded是人工固定的既有AdamW状态，不是训练checkpoint。没有DDP，有效全局训练batch不适用。

数值程序默认native torch；只有显式`--kml`且实际库可加载才允许标为KML。不将fallback/native torch、合成输入或Windows耗时称为C2验收。数值快照会增加内存，不用于峰值/吞吐测量。线程模板4仅为未来本地检查设置，不是C2授权绑定；预热、性能计时轮次/值本次不适用。

## 4. 正确性

实施前写入VALIDATION_PLAN.md。度量逐张量max_abs、L2 relative=`||candidate-reference||2/max(||reference||2,1e-12)`；norm<=1e-8只检查绝对误差，否则两个阈值均需满足。输出/loss、梯度、参数及参数增量max_abs≤2e-5、relative≤2e-6；AdamW moments max_abs≤2e-6、relative≤2e-6；step、keys、shape、dtype严格一致。失败不自动放宽。详见预定方案；这不是实测误差。

| 检查 | 实测/准备内容 | 证据 | 状态 |
|---|---|---|---|
| masked分母负例与正确加权、空局部mask、不齐尾批 | Fraction精确代数；错误均值与全批均值不同，整批分母求和相等 | tests_before/after.txt，test_contracts.py | 本地通过；无autograd |
| zero_grad/step及随机变量位置 | AST检查：清梯度一次、step一次且在微批循环外；循环backward；不重新采样 | tests_after.txt | 本地静态通过 |
| 冻结模型/共享原文件/S00证据 | 两份模型副本相同；108原文件及52个S00交付物SHA复核 | source_integrity*.json、baseline_manifest.json | 本地通过 |
| 输出h、voltage/coarse或noise prediction与loss | 脚本准备；reference直接调用原始mean公式，candidate使用sum/整批分母 | check_equivalence.py | **未运行** |
| 输入v/y0梯度、逐参数梯度 | 预期集合明确；pre decoder无梯度，dec mask_tok及预训练heads无梯度 | VALIDATION_PLAN.md | **未运行** |
| 更新后权重、相对初值增量、AdamW step/moments | 一次step计数、fresh lazy state、seeded状态中的非活动参数严格不变 | check_equivalence.py | **未运行** |
| state_dict/shape/dtype/NaN/Inf/缺失梯度 | 逐键/逐张量检查；另有真实小张量autograd分母负例与比较器负控 | 同上 | **未运行**；小张量也未运行 |
| 整批mask=0 | 候选在清梯度或更新前拒绝，避免原始mean(empty)的NaN；局部mask=0仍算coarse | 同上 | 实现/静态审查；真实检查未运行 |
| 无torch行为 | 退出2、JSON status=NOT_RUN；不产出数值PASS | numerical_not_run.json、local_validation.json | 依赖门通过；数值未运行 |

先测试后实现：初次4项检查中2项代数通过，缺候选/副本的2项预期ERROR（退出1）；创建候选与副本后4项通过。首次失败不是被修复的训练数值故障，也不证明数值等价。没有使用torch桩、缩小模型或模拟梯度。

当前真实输入/帧身份、demo图像对齐、J_scale仍沿用S00未验收缺口，不通过合成样本绕过这些条件。

## 5. 性能与内存

| 配置（每个belt和pre/dec独立） | 域数/有效结果数 | 有效批量/精度 | 总步秒数/吞吐/最慢域 | DDR/HBM峰值 | 退出状态 |
|---|---|---|---|---|---|
| B64×1 CKPT0参考，四项工作负载 | 未运行/0 | 单进程64/fp32，无DDP | 未运行 | 未运行 | NOT_RUN |
| B32×2、B16×4 CKPT0候选，四项各自 | 未运行/0 | 同上 | 未运行 | 未运行 | NOT_RUN |
| B64×1、B32×2、B16×4 CKPT1候选，四项各自 | 未运行/0 | 同上 | 未运行 | 未运行 | NOT_RUN |

完整原始配置列表见planned_matrix.json；不存在性能/数值原始指标，metrics明确为null。不转录历史计时冒充本次结果，不计算相对收益/波动，不选最优配置。同步训练未执行，单域/四域/整节点、三有效轮、第二主机均未运行。

静态逻辑存储：67,412,226参数的fp32权重257.157MiB；两个全模型AdamW moments514.314MiB；pre梯度144.942MiB，dec梯度256.652MiB。两阶段历史state已建立后的权重+moments+当前梯度小计pre916.414MiB、dec1028.124MiB；**不含激活/临时workspace/输入/容器/allocator/页碎片，不是峰值或4GB达标证据**。参数解析计数尚待实际torch numel断言核验。

32电极B64/B32/B16的单个encoder FF隐层分别464/232/116MiB，单个h分别116/58/29MiB；减少microbatch针对这类激活，权重及moments不随之减少。原有CKPT只覆盖encoder，不能消除decoder激活。SDPA是否物化N²、后端workspace实际大小、输入常驻和同时存活均未知，不能累加理论张量冒充工作集。

MEMORY_REVIEW.md交给S03解析大小类和生命周期测点，保留实际同时占用/热度trace缺失。HBM驻留/hugetlb、DDR RSS/PSS、tensor存活、arena high-water/累计申请量必须分开测；当前没有任何一类运行时测量。未做缓冲复用、allocator修改或依据预测选择放置策略。

## 6. 接受条件与限制

已完成：任务边界与源码身份核对；预训练/解码器整批分母和一次更新约定；只写S02的最小候选；预先确定的数值容差；48组矩阵和真实完整模型检查脚本；4项本地检查；无torch明确退出；静态内存清单、S03测量约定、S07有效批量接口和diff/哈希交付。

未完成：真实torch执行、实际numel核对、输出/梯度/AdamW/CKPT等价、真实数据契约、DDR/HBM峰值/时序、整步耗时、单域→四域→整节点重复测试、第二主机、最小内存和最优性能配置。原因是无适用本地torch，且远程连接/性能仍由S00负责、运行器等待S01接受。本次不探测连接、不部署候选，也不新增算力预算。

**S02本地准备可评审；原M2数值/内存/性能门槛未通过。** 不建议集成候选到正式入口。回退只需停止使用S02独立程序；原始代码及正式manifest未改。真实执行若失败，应保留首次失败证据并分析，不根据loss相似就接受，也不自动调整容差。

后续协调事项：S00确认输入和环境后，在已有排期内决定先执行哪些数值配置；S01运行器接受后才测内存/性能，后续资源未在本报告获批。没有需要用户现在重新选择的正式batch/LR/schedule。S03可以读取静态清单，但不应据此宣布已获得实际热度/同时占用数据；S07接DDP时须另定跨rank mask分母与默认梯度平均的补偿，当前不提供分布式等价保证。

## 7. 证据索引

绝对任务根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02`。完整逐文件SHA256位于下列索引（索引本身不自哈希）。

| 产物 | 绝对路径 |
|---|---|
| 报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\REPORT.md` |
| 全交付物SHA256 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\ARTIFACT_SHA256.txt` |
| 预定语义/容差 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\VALIDATION_PLAN.md` |
| 内存分解/S03交接 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\MEMORY_REVIEW.md` |
| 命令/接口/S07约定 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\RUNBOOK.md` |
| 独立候选/最小diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\candidate\training_step.py`；同目录training_step.diff |
| 真实完整模型检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\tests\check_equivalence.py` |
| 本地测试前后 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\tests_before.txt`；同目录tests_after.txt |
| 本地运行退出码/完整输出 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\local_validation.json` |
| 无torch未运行证据 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\numerical_not_run.json` |
| 四个解释器环境核查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\environment.json` |
| 原文件/S00前后核验 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\source_integrity_before.json`；同目录source_integrity.json、dependency_changes.json |
| 基线副本哈希 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\baseline_manifest.json` |
| 解析参数/张量原始字节 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\static_memory.json` |
| 48项未执行矩阵 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\planned_matrix.json` |
| 交付复核 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\delivery_validation.json` |

没有向其它聊天或外部服务发消息；报告由用户提供给总协调复核，不自行改COORDINATION/STATUS。
