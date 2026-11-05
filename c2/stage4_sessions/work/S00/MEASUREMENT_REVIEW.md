# S00 计时与汇总可信度审查

日期：2026-11-04。原运行器与 allocator 不修复；缺陷交 S01。路径替换版不构成已接受运行器。

## 1. 本地已证实的汇总误报

`tests/test_baseline.py` 直接提取原 `run_node16.sh` 的 Python heredoc 汇总器，给每轮只放 1/16 域的 JSON，mtime 设为 2000-01-01，既没有进程退出状态也没有日志。旧汇总器对四个 workload 全部打印 PASS。证据：`evidence/legacy_summary_witness.txt`，**合成缺陷见证，不是任何机器的性能数据**。

补充：17:00及17:09远程快照的Python汇总段与归档完全相同，检查已覆盖两份快照。17:09版本新增faulthandler及SIGBUS/segmentation等关键词，但不是完整退出码/域数/时效门槛修复。

| 位置 | 问题及后果 | S01 应验证的行为 |
|---|---|---|
| `run_node16.sh` 的后台启动／`wait` | 没有逐 PID 记录退出码；`wait` 后继续汇总 | 期望域到 PID、退出码、超时逐一对应，任一失败整轮无效 |
| 末尾 `echo NODE16_DONE` | 没有严格错误传播，DONE 不能代表成功 | 明确 success／failure、非零退出状态 |
| 日志 grep | 归档只查三类关键词；17:09版已扩展SIGBUS/segmentation等，仍不能代替退出码 | 以退出码为主，日志辅助定位 |
| `mkdir reports/tag`、只清 sync | 重用 tag 不清旧 JSON，失败可沿用旧结果 | 唯一 run_id；只接受本轮新结果，原子写入并校验身份 |
| glob JSON + 按键过滤 | 未验证期望域集合、配置、主机、输入或结果文件数量；各 workload 可有不同域数 | 四项必须均覆盖冻结的期望域，检查 schema、正有限值及配置一致 |
| `len(v)*min(v)` | 用成功域个数代替期望域数，掩盖缺域 | 缺域即不可接受；有效轮才计算 N_expected×min |
| `(max-min)/mean <= 5%` | 一轮也可因 spread=0 而 PASS；没有强制 3 轮 | 三个独立有效轮为最小接受条件 |
| `barrier()` | 文件计数无内部 deadline／故障传播，失败进程让其它进程等到外部 5400s | 可复现快速失败、清理本任务进程与文件，禁止僵等 |
| 节点发现／NUMA | 直接发现系统所有 CPU node；不校验调度器授权 affinity；假定 HBM=16+d | 限制在授权集合，现场核实拓扑、映射与可用内存 |
| SKIP_BUSY | 使用开跑前 lifetime-average %CPU；可能漏突发负载，核心全被排除也没前置拒绝 | 采样证据、逐域核心数、空集合拒绝、主机间复测 |

已取回135份历史逐域JSON：B64/preferred round2缺d4整个文件，因此四项工作负载该轮均只有15/16域，不只是32-dec无效。DDR B32三轮48份及HBM B32两轮32份JSON齐全，但逐PID退出状态和运行时指纹未记录，仍不正式接受性能。

## 2. 数值检查覆盖不足

原 `check_linear.py` 比较一个合成 encoder→decoder MSE 的 loss 和拼接梯度范数；过滤所有 None 梯度，没有逐参数键对齐、输入梯度、optimizer.step 后参数／AdamW 状态、NaN/Inf 或 state_dict 检查。它不是完整预训练加解码器两类训练步的验收套件。历史 loss／梯度小误差只能作为设定检查的参考，不代表本次通过。

后续fp32等价检查应先冻结同一权重/输入/mask/t/noise；分别报告max_abs与L2差/max(ref范数,1e-12)，逐个预期梯度检查，近零时同时看绝对差。约1e-6仅历史参考；S00未运行模型，不虚构实测容差。训练输入finite已查，但已证实16电极使用不同的32电极images，必须先明确目标语义。注意力仍沿用任务规定的预设门槛，本任务未改算子。

## 3. HBM 与内存指标

- `peak_mem_GB` 是进程生命周期的 `ru_maxrss/1e6`，不是某个 part 的增量，也不是某个 belt 独立峰值。Linux ru_maxrss 单位通常为 KiB，这个历史换算不是严格 SI GB；重测须保留原始值和单位。
- hugetlb 不计入通常 RSS，HBM 必须另外记录每个 node 的 2MiB hugepage 可用数、占用变化及实际映射，DDR 与 HBM 分列；不能把 RSS 当总内存。
- allocator 的 `hbm allocs (...GB)`、`ddr large allocs (...GB)` 是累计申请字节，并非流量／带宽／峰值驻留。`arena high-water` 是 bump 指针到过的最高 offset，含粒度、header 和已释放块；也不等于同时存活 tensor 字节。映射 arena 大小还不等于所有页已经触达。
- 源码包含历史 SIGBUS 修复：读 node free hugepages、留 16 页、临时切换 mempolicy 再 mmap、随后 mbind。共享 `.so` 是否由此版本构建，本次未核实；历史一域成功不能替代整节点复测。
- **静态边界疑点**：`(size_t)(nfree - 16) * 2 < mb` 在 nfree=0..15 时会因无符号转换回绕，可能跳过预期 cap。未编译／未触发，不写作实测 SIGBUS 原因；由 S01 在独立副本中先补低页数和策略调用失败检查。此处没有更改 allocator。

## 4. 历史结果口径

`evidence/historical_measurements.csv` 共 40 行，全部为原报告表格转录，非逐域原始结果；未知项留空。DDR B64+CKPT 仅供 S01 上下文，不作为本任务新增配置。

`historical_spreads.json` 明确从**四舍五入的文档数字**重算波动。例如 DDR B32 的 16-dec `[43,46,46]` 算出约 6.67%，原文为 5.6%；HBM 16-pre `[290,318]` 算出 9.21%，原文为 9.4%。这不能证明原始统计错误；没有原始值时，不应用转录数覆盖原文，也不能据此提升接受状态。

当前已有原始JSON：remote_recomputed.json重算DDR B32的16-dec为5.607%、HBM16-pre为9.387%，证实原文四舍五入值；此前6.67%/9.21%仅保留作舍入陷阱示例，不能作为当前结论。完整540条域/48条轮次记录见remote_measurement_table.md及CSV，缺域完整合计留空。

| 配置／文档轮值，frames/s | 16-pre | 16-dec | 32-pre | 32-dec |
|---|---|---|---|---|
| DDR B64 preferred，3轮 | 243/233/237 | 76/49/49 | 31.0/31.1/32.7 | 20.5/20.4/21.3 |
| DDR B32 membind，3轮 | 150/151/151 | 43/46/46 | 21.9/20.9/20.9 | 17.0/16.5/16.8 |
| HBM B32 membind，2轮 | 290/318 | 75/72 | 21.9/21.4 | 18.0/18.3 |
| DDR B64 CKPT，2轮，S01上下文 | 121/118 | 56/42 | 16.6/16.8 | 14.3/14.0 |

不能从文档node sum反推每域step/最慢域/峰值；本次已直接从逐域JSON读取这些历史值并重算。DDR32与HBM32整节点不同主机，不是同主机A/B；四域同主机仅一轮且有慢域。没有新测量或实测收益声明，node sum不含通信，不是DDP吞吐。

## 5. GPU 参考的准确口径

原 `C2_OPTIMIZATION_REPORT.md` 的 GPU 行为 RTX 4090、amax demo、B64、CUDA bf16 autocast：1188/284/219/134 frames/s。包内保留 `s4_models_gpu_orig.py` 可核对 B64、20计时步、seed0、bf16、AdamW 和架构；没有 GPU 原始 JSON、日志、torch/CUDA 版本、具体主机或样本 SHA256。这里只能说“参考来源定位到历史报告及源码”，不能说完整运行证据已核实。当前没有 GPU 连接信息；未尝试替代机器重测。

32电极预训练：完整域DDR B64第1/3轮30.9701–32.6976对比GPU219，约1/6.70–1/7.07；HBM B32两轮21.4177–21.9243，约1/9.99–1/10.23。32-dec的完整域DDR B64为20.5443–21.3309，对比GPU134约1/6.28–1/6.52；HBM B32为18.0083–18.2626，约1/7.34–1/7.44。缺域第2轮20.44不得加入完整域范围。交接中的“32电极1/10”针对HBM B32，不是所有历史最佳CPU配置；这些范围都尚未正式接受。

以上均为历史工作负载比值，存在精度/批量/计时长度差异；B64第2轮四项已证实缺域，完整轮仅两轮。GPU原始运行证据仍缺，不能称公平硬件加速比，也不能拼成一个已验证统一配置。
