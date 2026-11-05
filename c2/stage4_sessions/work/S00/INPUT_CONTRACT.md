# S00 环境与输入契约

日期：2026-11-04。标记：`LOCAL_VERIFIED` 为本次源码或本机核查；`HISTORICAL_DOCUMENT_ONLY` 为原文记录；`REMOTE_NOT_VERIFIED` 为缺现场证据。

最新远程证据见REMOTE_AUDIT.md及evidence/remote_details.json、remote_context.json：已登录dengqingtian@login10，训练输入的shape/dtype/finite和非零分母已核查；图像目标对齐失败，不能因输入finite就视为训练语义正确。

## 1. 输入来源及缺口

- `LOCAL_VERIFIED`：本包没有 `data/`、`corpus_shape_20261102/`、`frames.npz`、`manifest.csv`、subject split、checkpoint、逐域计时 JSON、日志或预编译 `.so`。完整原始文件清单见 `evidence/source_before.json`。没有生成、改写或伪造这些文件。
- `REMOTE_VERIFIED_METADATA`：C2冻结语料路径已可读，manifest为11,900行／1,190,000对、119个case，各行的代码／配置标识与记录一致；仅核查manifest及指定源码哈希，没有遍历样本或sidecar逐值复核。amax副本路径仍只是历史记录，本次未连接其它服务器。
- `LOCAL_VERIFIED`：默认 `s6_corpus.py` 的 SHA1 前 10 位为 `d8b2be8d1f`；仅求值 CFG 字面量、未使用 `CFG_OVERRIDE` 时，配置 SHA1 前 10 位为 `b1049eac1a`，均与文档相符。完整 SHA256 另存。
- **哈希范围差异**：CODE_HASH只读s6自身字节，不含s1/s2/s3，README的相应描述不能按程序机制理解。本次额外冻结完整SHA256，远程生产s2/s3/s6已匹配；s1尚未远程核查，样本逐文件相同仍未证明。
- `LOCAL_VERIFIED / REMOTE_VERIFIED_METADATA`：prod_setup输入外部case list，只做排序去重及作业分片，shards不是训练／验证／测试划分。远程manifest已确认无split字段；cases.txt的SHA256已记账但不能代替真实subject split。真实split来源及SHA256仍缺。
- 历史约定为 splits/corpus seed=2026、训练 seed=0/1/2；本计时入口实际固定 `torch.manual_seed(0); np.random.seed(0)`，无训练 seed 环境开关，本次没有运行 1/2。

## 2. demo 与 corpus 不是相同文件契约

`s4_models.py` 读取 `<O>/cases/s0322p0/frames.npz` 和 `<O>/cases/s0322p1/frames.npz`；不读取冻结 manifest，不加载正式训练 checkpoint，不实现 epoch、独立数据划分或 DDP。只是随机初始化后的 demo 更新计时。

这两个名字是同一s0322受试者的两个placement，不是两个独立受试者；每个文件2帧，总4帧，在一次batch抽样后被重复用于预热/计时。

历史适配器 `c2/opt/run_bench_s4.sh` 从 `/home/share/songzhenlong/eitfm/opt/worker_test/parts/s0322_p{p}_{belt}_c0.npz` 生成 demo 文件。它不是从生产 manifest 选取的已验证训练集。

| demo 字段 | 预期维度／用途 | 本次验证范围 |
|---|---|---|
| `images` | `[N,64,64]`，两个case沿N拼接 | 每文件[2,64,64] float16，训练输入finite；合计4帧 |
| `16_adjacent_v_ref/v_cur` | 同形`[N,208]`，reference已展开 | 每文件[2,208] float32，finite，参考分母最小约1.4071 |
| `32_skip4_v_ref/v_cur` | 同形`[N,928]` | 每文件[2,928] float32，finite，参考分母最小约13.3003 |
| `{belt}_J_img` | `[208或928,4096]`；仅GN/采样需要 | shape/dtype(float16)/哈希已核查，未全finite扫描；GN=SAMPLING=0 |

corpus 单元的 `v_ref` 是 `[baselines,M]`，`v_cur` 为 `[baselines*breaths,M]`，需用 `base_of_pair` 展开 reference；`images` 是 float16，`J_img` 为归一化 float16，另有 `J_scale`，以及 `drives/meas`。不能把单元 NPZ 直接当 demo `frames.npz`。

**适配器限制**：循环对两种 belt 反复赋值同一个 `out['images']`，最终保留 32 电极图像；它未验证两种 belt 的图像相同，也未验证各帧身份对应。它复制归一化 `J_img` 而没有应用 `J_scale`。前者限制训练语义，后者限制物理采样／GN；本次未执行该适配器。S00 保留历史模型代码，不把该输入路径宣传为正式训练质量基线。后续须核实帧身份和图像对应，不能静默换数据继续沿用历史性能数字。

**远程证实的目标错误**：对两个placement逐一比较NPY payload SHA256，demo images均等于32电极源单元且不等于16电极源单元，详见remote_context.json。这里不是仅靠覆盖代码推测。当前images全局abs max=0.033203125，数值finite但16电极目标归属不正确。S00不修改数据；后续需单列输入语义版本和固定目标协议，不能用这些历史计时帧宣称完整语料训练正确性。

## 3. 协议及数值路径

- `16_adjacent`：L=16，驱动 `(i,(i+1)%16)`，排除电流／测量电极相交，208 tokens。
- `32_skip4`：L=32，**实际偏移 5**，即中间隔 4 个电极，驱动 `(i,(i+5)%32)`，928 tokens。s3、s4 和 s6 的参数一致；本地执行两个协议函数的无依赖提取片段，确认有序测量对一致。没有修改名字或 skip。
- `x = float32((v_cur-v_ref) / mean(abs(v_ref), axis=1))`，随后 `v=x[idx]*1e2`。分母没有 epsilon；实际输入需检查零、NaN 和 Inf。
- `scale = abs(concat(images)).max()`，`y0=images[idx]/scale`，加 channel 维；这里也是无 epsilon，需要验证 scale>0。不是逐训练集统计的已冻结归一化。
- 一个 batch 的 `idx` 只抽一次，随后所有预热／计时步重复这些样本；有放回抽样。每个进程 seed 相同，不代表不同 rank 有不同数据。
- 编码器 12 层、width=512、heads=8、FF=2048、dropout=0、norm_first=True；Fourier nfreq=8；`mask_tok` 初始化为零，其余沿用 torch 默认初始化。U-Net 通道 `(128,256,256,512)`、tdim=ctx=512，不变。
- 一个进程只初始化一次 encoder 和 decoder，按 `16 pre → 16 dec → 32 pre → 32 dec` 累积更新；不会在每个 belt／part 前复位权重。初始权重值取决于 torch 版本与 RNG；没有 checkpoint 或初始权重张量哈希可供跨版本验证。
- 预训练：每步重新采样 `<0.5` 的 token mask；masked voltage MSE 与 16×16 pooled image coarse MSE 相加，两项均用 PyTorch 默认 mean。跨 microbatch 累积时，mask 元素数分母必须匹配整个有效 batch。
- 解码器：T=1000，beta 从 `1e-4` 线性到 `0.02`；每步新 t 和标准正态噪声 e；`xt=sqrt(abar)*y0+sqrt(1-abar)*e`；loss 为预测噪声与 e 的 MSE。encoder 同步反传更新，没有冻结。
- AdamW 同时注册 enc+dec 参数，lr=1e-4，其余用该 torch 版本默认值（历史 torch 2.7.1：betas=(0.9,0.999)、eps=1e-8、weight_decay=0.01）。共享 optimizer 持续跨 belt 使用。预训练的 decoder 梯度、解码器阶段的预训练 heads 梯度通常为 None，这是按计算图确定的预期；不能把所有 None 梯度一律当故障。
- CPU 基线：参数、激活 fp32，AMP=fp32，KML_LINEAR=1、LINEAR_DTYPE=fp32、KML_CONV=0、CKPT=0，原生 SDPA。`patch_attention()` 未调用。bf16 KLinear 不属于这三个基线配置。

## 4. 计时与环境契约

- 每 belt 先做 **2 次 pre + 2 次 dec** 的完整更新，即使 PARTS 只选其中一种，也会预热两者；再按顺序计时 5 次 pre、5 次 dec。计时包括 forward、loss、zero_grad、backward、optimizer.step，排除数据加载、归一化、batch 抽样、模型构建、阶段 barrier 和预热。
- 每域 B32／B64、梯度累积=1；1/4/16 个进程各自训练自己的模型。DDP rank 数为 0，**不存在有效全局训练 batch**；512／1024 只是 16 个独立进程的每次更新样本数之和，不能作为同步训练实验设置。
- OMP close/cores，正常 38 threads/domain；SKIP_BUSY=1 可减少线程数，实际线程／核心名单需要逐域记录。历史脚本不显式设置 torch interop、MKL 或 OPENBLAS 线程数；需现场采集，不能补写为固定值。
- DDR membind=d；HBM membind=d,16+d，arena 3800 MiB、阈值 256 KiB；B64/preferred 独立配置，不能与 B32 作同批量加速比较。
- `PYTHONPATH` 仍读取共享 `sw/torch_kml` 运行时，只把模型源文件切换到任务副本。此运行时与 KML/BiSheng 未在本包提供，远程 `.so`、Python 和编译器哈希／版本是运行前必需项。
- 本机为 Windows AMD64，Python 3.11.9；当前 Python 没有 torch/numpy，未安装依赖。C2 的 608 核、16 compute NUMA、DDR/HBM、gcc、torch 2.7.1+cpu 等均为历史记录；当前调度节点、库加载和 CPU 拓扑未核实。
