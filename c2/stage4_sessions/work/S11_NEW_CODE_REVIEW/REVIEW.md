# S11 新版 Stage 4 审阅

2026-11-10 · 只读代码、包清单和既有结果 · 完成静态审阅

11-08 新增了 C/SME 融合注意力、BF16 KLinear v2、节点内共享内存规约和跨节点 Gloo，以及 HBM 安全和慢域诊断改动。**掩码位置编码的改动在默认配置也生效。** 12 节点报告支持的是特定 demo 的聚合帧次吞吐，单节点数据和现有工程验收须分别使用。

## 版本与证据边界

| 对照对象 | 定位 | 对应依据 |
|---|---|---|
| 原 GPU 参考 | 4090 CUDA BF16、B64 demo | 两包 `c2/opt/s4_models_gpu_orig.py` SHA-256 均为 `40bfe92dc31387759917f0b05bc3e2ae45613b119a2be81401b49d53d9961373`。|
| 11-03 根目录 C2 移植 | 当前 HEAD `9fe726a9e19e393ddeb9bec99189c48279d66296`，关键入口首次入库于 `2495b366c153ec79c895199428c45b42786b46fd` | `s4_models.py` / `kml_ops.py` SHA-256 前缀 `9ff6417b80c4` / `e6c5c4411c45`，工作树字节与 HEAD blob 一致。|
| 11-08 外部包 | 无 Git 元数据，README 指向 `opt/code_v2` 暂存部署 | `s4_models.py` / `kml_ops.py` SHA-256 前缀 `85457b521665` / `72a15602eb60`。`hbm_alloc_v1103.c` 与 11-03 根目录分配器字节一致。上游基点 commit、作业源码及二进制 SHA 均为 UNKNOWN。|
| 内部冻结试验 | S00、S05、S09/M23、S10 各自的源文件与结果 | S00 R1 与 S10 基线模型同 11-03 根模型，S05 基线 KML 同 11-03 根 KML。S05 转置、S09 分层 CKPT、M23 HBM、S10 BF16 是各自独立版本，详见 JSON 的 `internal_frozen_anchors`。|

11-08 清单 172/172 项 MD5 匹配。按旧根目录同路径比较，79 项字节一致、16 项变更、77 项新增路径。映射表列出 29 个重点文件和 16 个内部源／结果锚；9 个 Python 文件通过 AST 解析。新版目录只有源码、脚本、文档和清单，两套工作目录均未找到本次关注的原始 `opt_dpmn12_bf.log`、`opt_dpzc_bfattn2.log` 或历史 `models_timing.json`。以下外部数字均为**作者日志转述**。本机 Git Bash 在沙箱内无法启动（`NtCreateDirectoryObject 0xC0000022`），shell 语法未实跑，现场库与硬件派发也未验证。 [VERSION_MAP.json](VERSION_MAP.json) · [部署说明](E:/eitfm_c2_stages2-4_2026-11-08/README.md:532)

## 简明差异表

| 项目 | 新版相对 11-03 的差异与预期作用 | 训练语义 | 已有证据与结论 |
|---|---|---|---|
| FP32 融合注意力 | `KML_ATTN=1` 给 CPU FP32、4D、末维连续的无 mask／dropout／causal SDPA 接 C 实现。前向分块 softmax，反向按块重算，使用 KML locking 和 strided 张量，减少分数矩阵与布局拷贝。其它入口回退原 SDPA。 | Encoder 的随机遮盖发生在输入 token 上，和 SDPA 的 `attn_mask` 是两个层次。融合替换采用近似 exp 和不同归约，需验证误差。 | 作者一 die、928 tokens B32 F+B 0.80→0.53 s，参考误差 3–7e-7；全节点 2025522 的 SDPA/SDPA 对比已撤回，2042021 未出结果。[派发](E:/eitfm_c2_stages2-4_2026-11-08/kml_ops.py:178) · [记录](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:50) |
| BF16 attention | CPU 外部张量仍是 FP32，内核将 Q/K/V/dO/P/dS 转 BF16，softmax 与 GEMM 累加 FP32；多节点选 BQ16，缺 `sbgemm` 时退回 FP32 tile。 | 局部舍入变化，和全模型 autocast、BF16 KLinear、内部 S04/S10 精度候选是不同配置。 | 作者对 float64 相对误差 3.4e-3、2 层 Encoder 梯度差 9.6e-4。独立算子约 2.2–3.2×，2042570 下 BQ16 改善 die 并发；2042605 的 32 电极预训练 56.8 对跨主机旧值约 52（约 +9%），decoder 未获收益。[内核](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/kml_attn.c:285) · [并发与模型结果](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:145) |
| BF16 KLinear v2 | `LINEAR_DTYPE=bf16` + `KML_FAST_LIB` 走 OpenMP cast/fill、权重版本缓存、BF16 激活保存，前向/dX/dW 均为 `sbgemm`、FP32 输出；仍有按输入大小和 dtype 回退。 | 量化涉及权重、激活和反传，和旧 BF16 实现不同。12 节点仍用 FP32 KLinear。 | 作者局部 loss 差约 1e-3、梯度约 6.7e-3；一 die 的 16/32 电极预训练 0.98→1.06、7.16→7.24 s，保留 FP32。[实现](E:/eitfm_c2_stages2-4_2026-11-08/kml_ops.py:281) · [记录](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:100) |
| HBM / CKPT | 旧版已有 HBM arena、DDR 回退和 `CKPT=1` 的逐层重计算；新版增加预触页、短供给缩池、对其它 `MAP_HUGETLB` 调用剥离标志，及默认关闭的 best-fit。Belt 分进程减少碎片。 | 改内存放置和重算开销。DP 使用的 `CKPT=1` 与内部 `CKPT12` 是分别绑定的入口。 | 作者探针 2025670 将 B64 SIGBUS 定位到 KML 36 MB 打包映射；cn21347 的 `_nh` 两轮无 SIGBUS，32 电极约 41.4 / 27.0–27.5 帧次/s，仍慢于 B32+CKPT；2026043 best-fit 落后于分进程方案。[预触页](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/hbm_alloc.c:65) · [mmap 包装](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/hbm_alloc.c:167) · [记录](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:56) |
| 绑核与慢域 | `CORES_PER_DOM=36` 后再减忙核，预留末两核；新增 per-rank 采样、SME SVCR/FPCR guard、文件屏障超时与 DP 丢慢 rank。 | `SYNC_STRICT=0` 超时继续并记录，所得窗口可能错位；`DP_DROP` 会改变实际参与样本与批量。 | 作者在 cn21338 d4 观察到 SDPA 的 Sleef expf 占比高、IPC≈0.06；2046750 切 BF16 attention 后该次无重度慢域，硬件根因未定。RoCE、HBM=0、guard 和替换启动路径均有慢域记录。[绑核](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/run_node16.sh:37) · [文件屏障](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:203) · [诊断](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:187) |
| 节点内 DP | `DP_LIB` 让各 rank 写共享梯度槽，原地读归约结果，省去复制式归约的两次复制和一个屏障。普通 `run_node16.sh` 在未设 `DP_LIB` 时仍是独立副本。 | 每步共享梯度并各自执行 AdamW。零拷贝指节点内梯度缓冲路径。 | 作者 2042691 独立 270 MB 规约 49 ms、sum check PASS；B32 的 32 电极训练 40.9–41.4 / 31.5–31.7 帧次/s。主耗时可来自等慢 rank。[共享规约](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/shm_allreduce.c:84) · [记录](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:177) |
| 跨节点 DP | BF16 入口经 `run_dp_multi.sh` → Donau `drun` → `dp_node_task.sh` → `run_node16.sh`。每台 16 rank，按本地 rank 各启一组 Gloo TCP，对节点规约结果的切片做跨节点 all-reduce。 | 名义批量随节点数增长，DP 可丢 rank。训练入口缺数据分片和持久化训练 checkpoint。 | 作者 2046930 双轮报告 12 节点的四项聚合吞吐均超过旧 4090 记录；32 电极预训练波动 11% 超 A1。[入口](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/run_dp_multi_bf.sh:6) · [节点任务](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/dp_node_task.sh:12) · [规约和更新](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:299) · [报告](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:215) |
| 模型、数据与目标 | 保留 Encoder 12 层/512/8 heads、条件扩散 U-Net、两项 pretrain MSE、decoder 噪声 MSE、AdamW 初始 LR 1e-4。默认 pretrain 由被 mask 时的 `mask_tok` 改为 `mask_tok + position`。 | 遮盖概率仍为 0.5，位置分支的输入及梯度已变。decoder 调用 Encoder 时无 mask，但先前预训练轨迹可影响其权重。 | GPU 与旧 C2 代码均在相加后替换。新版 README 的默认复现表述与源码冲突，参数布局一致只支持结构对照。[GPU 掩码](E:/eitfm_c2_stages2-4_2026-11-03/c2/opt/s4_models_gpu_orig.py:82) · [旧 C2 掩码](E:/eitfm_c2_stages2-4_2026-11-03/s4_models.py:102) · [新版掩码](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:123) · [README 声明](E:/eitfm_c2_stages2-4_2026-11-08/README.md:78) |

## 单节点和 12 节点

单位为作者报告的帧次/s，顺序为 Encoder 预训练 / decoder。每个整节点最多使用 16 个 NUMA 域，表内独立副本的最佳值来自不同配置。

| 口径 | 16 电极 | 32 电极 | 证据与批量 |
|---|---:|---:|---|
| 单张 RTX 4090 | 1188 / 284 | 219 / 134 | 历史 demo BF16 autocast B64，2+20 步，CUDA 同步。原始 JSON 缺。|
| 单台 C2，16 个独立副本 | 341 / 119–127 | 52.0–56.8 / 34.9–36.1 | 分阶段最佳；独立模型聚合。32 电极预训练约为 4090 的 24–26%。|
| 单台 C2，同步 DP + BF16 attention | — | 47.8 / 24.5 | job 2046750，一轮；名义全局 B512，约为 4090 的 22% / 18%。|
| 12 台 C2，同步 DP + BF16 attention | 1338–1362 / 652–655 | 415.9–464.2 / 237.4–239.1 | job 2046930，`opt_dpmn12_bf.log`，两轮；16 rank/节点，每 rank B32，名义全局 B6144。作者称 `DP_DROP` 开启但未触发。|

12 台平均到每节点约为 16 电极 111.5–113.5 / 54.3–54.6，32 电极 34.7–38.7 / 19.8–19.9。相对 2046750 单台 DP 的 32 电极，总吞吐约 8.7–9.7× / 9.7–9.8×，属于跨作业描述性比值。12 节点 32 电极预训练波动 11%（A1 上限 5%），作者报告其规约约 4.6 s/步、其中 Gloo 约 3.0 s；6 节点 16 电极 decoder 的 18% 波动也超限。节点数、批量和精度共同变化，无法归因 12 节点的收益给某个内核。 [单节点表](E:/eitfm_c2_stages2-4_2026-11-08/README.md:338) · [跨节点表](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:215) · [历史 GPU 口径](E:/eitfm_c2_stages2-4_2026-11-03/c2/C2_OPTIMIZATION_REPORT.md:166)

- **计时。** C2 launcher 默认每 belt 预训练和 decoder 各 2 次真实更新预热，各计时 5 步，默认按 belt 分进程；即使 `PARTS=pre` 也会执行 decoder 预热。计时覆盖前向、反向、AdamW 及启用时的规约，排除加载、建模、预热和计时前文件屏障。每 rank 输出 `B/平均步时`，独立副本汇总另有 `rank数 × 最慢 rank 速率`。超时、缺 rank 或 `DP_BALANCE` 时要从实际完成的帧次和共同墙钟重算，动态批量路径的 JSON 分子仍写名义 B。GPU 峰值重置一次后跨两个阶段，C2 的 `ru_maxrss` 是单进程高水位，与 HBM 驻留、GPU 显存及全节点峰值分别看待。README 快速入口将 `run_dp_zc.sh` 标成独立 rank，实际设置了 `DP_LIB`。 [计时主体](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:373) · [launcher 与汇总](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/run_node16.sh:45) · [DP 入口](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/run_dp_zc.sh:15)
- **数据与 AdamW。** demo 读取 `cases/<case>/frames.npz`，launcher 固定 `s0322p0,s0322p1`。所有 rank 用同一随机种子并从相同池在每 belt 抽一次索引、重复使用输入，mask 和扩散噪声按步生成。源码没有按 rank 派发不同样本，也没有 epoch、优化器恢复或正式验证集入口，subject/split 为 UNKNOWN。DP 给所有参数预挂零梯度缓冲，预训练阶段只把 decoder 的 grad 恢复为 None；在 decoder 阶段，未参与损失的 Encoder 预测头仍会以零梯度进入 AdamW，导致权重衰减及已有动量/步数更新，与独立路径的 None 跳过语义不同。即使做了样本分片，直接平均每 rank 的 masked MSE 对应的是 rank 均值，mask 数不等时与合批的逐遮盖 token 均值有差异。 [种子和读入](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:62) · [梯度缓冲](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:299) · [输入和损失](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:339)
- **慢域与失败。** `DP_DROP` 在两类预热后以最后一次预热的本节点 busy time 判断，超过上中位数两倍的 rank 在计时阶段跳过 F/B，继续参加规约与更新；跨节点聚合以 active rank 数归一。它只筛一次，不能处理后续出现的慢域或掉进程；本地 C 规约屏障无超时。若同时启用 `DP_BALANCE` 和 `DP_DROP`，loss 用 `b/B` 加权而分母仍是 active rank 数，无法保证按活跃样本数归一。外层 `wait`、`sed` 管道及尾部 DONE 字样也不足以证明所有 rank 成功。 [慢域与归一](E:/eitfm_c2_stages2-4_2026-11-08/s4_models.py:290) · [本地屏障](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/shm_allreduce.c:30) · [节点退出路径](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/dp_node_task.sh:16)

## 复用判定

- **可直接复用的运行方法。** 各 belt 单独进程、先取本域 36 核再减忙核，核实实际 TID/NUMA 驻留，保留 per-rank 时间、all-reduce wait 和屏障超时。比较时用实际共同窗口吞吐，将文件屏障超时或缺 rank 的轮次单列。HBM 容量、RSS、驻留和大块回退单列。 [操作记录](E:/eitfm_c2_stages2-4_2026-11-08/c2/STAGE4_HANDOVER.md:235)
- **HBM 采用本项目已核配置。** S09 32 电极 B32 四域，CKPT0 DDR/HBM 步中位数 29.14→17.40 s，HBM CKPT12 约 3.64 GiB/域峰值估算但 5.436% 波动失败。S00 16 域数值与安全通过范围有 496640 项严格记录最大差 0；稳定性只接受 cn21762 的 16 电极 B64/CKPT0，32 电极稳定性未接受。R2 2081280 慢域失败、2081519 实分配 15 域，C1 未得到 A/B。M23 安全证据绑定不同 SHA，无法覆盖外部 `mmap` 包装和进程级临时 SIGBUS handler；外部分配器只作诊断参考。 [S09](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/COORDINATION/S09_32E_RESULT_REVIEW_20261108.json) · [S00 R1](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/COORDINATION/S00_FULL16_REVIEW_20261110.md) · [S00 R2](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/COORDINATION/S00_FULL16_R2_TERMINAL_RECEIPT_20261110.json)
- **保持已拒绝项。** S04 P1 为 57/83；S10 BF16 模块 83/83，完整五步 98/3865 FAIL，融合 AdamW 的二阶矩超限，性能未跑。S05 FP32 dW 转置全 25 步合计慢 0.21%、HWM +5.85 MiB，未采用。这些证据不迁移到外部 attention，外部局部结果也无法解除旧 FAIL。外部 BF16 KLinear、`DP_BALANCE`、`HBM_FIT` 缺少值得优先复测的收益；整包替换会引入掩码和 DP 语义差异。 [S04](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S04/SESSION_STATUS.md:9) · [S10](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/COORDINATION/S10_BF16_FUSION_R1_RESULT_REVIEW_20261108.json) · [S05](E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/s05_ab_main_20261107/A_B_SUMMARY.md:16)

## 优先实测候选

1. **FP32 融合 attention，32 电极 B32/CKPT12 Encoder。** 采用内部固定样本与旧掩码语义，隔离替换 SDPA，固定 FP32 KLinear、36 核、同一主机和已绑定的 HBM 分配器。先用作者有局部数据的 BQ64，确认 native dispatch、无回退及参考一致性，再走现有五步严格门，核 loss、梯度、更新量、参数与 AdamW 状态。过门再以同主机配对测步时、共同墙钟和内存；单域通过后再考虑整节点扩域。优先依据是局部 1.5× 且保持 FP32 输入与 GEMM，整节点 FP32 A/B 仍空缺。
2. **BF16 融合 attention BQ16，针对 32 电极慢域。** 单独隔离该内核，保持 FP32 KLinear、相同旧掩码语义、样本和 HBM；与同主机同域 FP32 SDPA 配对，优先选择能重现该慢域症状的分配，记录实际 BQ/BF16 派发和各域耗时。沿用现有严格数值门，门失败即停止性能阶段。通过后才测整节点窗口及尾部、峰值和驻留；比较时用全 rank，避免以丢样本解释收益。优先依据是 2042570 die 并发数据和 2046750 对 cn21338 的绕过记录。

两个候选均需在隔离验证入口先核 C ABI 和真实前后向调用。新版 C 内核有分配失败后直接返回或跳过 tile 的路径，Python 端输出用 `torch.empty` 且未接收失败状态。性能读数的前提是验证实际派发、完整有限输出与有效内存路径。若以后评估跨节点训练，先绑定版本/库/数据，冻结分片、mask 目标归一、全局 batch 和优化器更新语义，再谈扩展效率。 [输出与 ABI](E:/eitfm_c2_stages2-4_2026-11-08/kml_ops.py:210) · [C 前向](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/kml_attn.c:311) · [C 反向](E:/eitfm_c2_stages2-4_2026-11-08/c2/opt/kml_attn.c:365)
