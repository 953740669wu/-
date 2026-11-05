# S01 本地候选复现与后续接口

版本：`S01_LOCAL_RUNNER_20261104`。仅本地协议测试通过；未部署，未获总协调集成接受。

## 本地复现（PowerShell）

```powershell
Set-Location -LiteralPath 'E:\eitfm_c2_stages2-4_2026-11-03'
python -B c2\stage4_sessions\work\S01\tests\test_runner.py
python -B c2\stage4_sessions\work\S01\exercise_local.py
```

第一条当前是 32 项：31 通过、1 项 Linux 进程组检查跳过；第二条创建唯一的 `evidence/SYNTHETIC_<UTC>/`，8 个合成协议场景全部符合预期。所有数值由测试指定，无真实训练计算。

旧行为的独立缺陷见证：

```powershell
python -B c2\stage4_sessions\work\S01\tests\test_legacy.py
```

此命令**预期退出 1，5 条安全断言失败**，证明冻结的旧汇总器不满足安全要求。不要把它和候选的正常测试门槛混为一组。

不重跑 S00 的脚本；其中部分会覆写 S00 证据。S01 的 `audit_delivery.py after` 只读外部文件，更新 S01 内的差异、哈希和完整性证据。`before` 是任务起点快照，复核时不要覆盖。

## 候选目录与协议

交付根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01`。

候选 `candidate/` 必须整体使用：`s4_models.py`、`runner.py`、`run_node16.sh`、原样 `kml_ops.py`。只有模型文件的同步与输出设施改变；模型计算、随机变量、优化器、计时区间和预热仍是 S00 源码。

- `run_node16.sh <unique_tag> [BATCH=32 CKPT=0 ...]` 保留原 tag/env-assignment 调用形式；路径由绝对 `S01_RUN` 决定。只接受已有模型参数赋值，拒绝覆盖路径、SYNC、TIMING_OUT 等协议变量。
- 运行源码固定为 `$S01_RUN/candidate`；输出固定为 `$S01_RUN/output`；shim/HBM `.so` 固定为 `$S01_RUN/lib`。只读 torch 仍来自历史 `$H/sw/torch_kml`，需要 S00 核实实际版本和来源。
- 默认 `NDOM=16`、`ROUNDS=3`、`REPS=5`、`RUN_TIMEOUT=5400` 秒、`SYNC_TIMEOUT=300` 秒；本 S01 入口固定 CPU/fp32、GN=SAMPLING=0。后续正式配置必须显式给出 BATCH/KML_LINEAR/CKPT/BELTS/PARTS，避免沿用环境中的默认值。
- 使用 Linux `sched_getaffinity` 与每域 cpulist 的交集；不足指定域数或任一域零可用核心即拒绝。不会少开域后继续计算“整节点”。它只能约束继承的 CPU affinity，不能单独证明调度器授权；S00 仍须核对作业/cgroup。
- SKIP_BUSY 保留原来的启动前 lifetime-average 快照逻辑，只新增原始快照和最终核心清单留档。它未解决突发负载；本任务没有新增 36/38 线程搜索。
- HBM 仍采用历史 `16+d` 映射，额外验证该 node 存在且没有 CPU；这不证明完整 NUMA/允许内存关系，必须现场复核。不含 allocator 改动，也不保证消除 SIGBUS。
- tag 目录必须不存在，已存在即失败，不删除或重用旧结果。每轮有独立 sync 目录，barrier 使用 run_id 与期望 rank 集合，默认 300 秒内部超时，检查 `ABORT.json`。
- Linux 每个子进程以独立 session 启动；失败时只向这些 session 发 TERM，宽限 0.5 秒后 KILL，逐 PID 留存真实退出码。Windows 测试只覆盖直接子进程；Linux 分支未运行。
- 结果通过临时文件与 `os.replace` 原子发布，禁止写 NaN/Inf。元数据含 run_id/host/round/rank/PID、时间窗、实际 affinity/线程数和候选源码 SHA256。
- 每轮校验结果集合、退出状态、身份、时间、配置、输入 case 名、运行时版本及正有限值；吞吐×步时与 batch 的相对容差固定为 `1e-9`，它是协议自洽检查，不是模型数值容差。文件 mtime 允许进程时间窗两侧各 2 秒的文件系统精度余量，身份和进程内部时间窗仍须匹配。
- manifest 冻结两个 frames.npz、候选脚本、源码和本次 preload/KML 库 SHA256，每轮复查。依赖项的完整运行时身份和数据划分仍需 S00 验收。
- 任一当轮结果缺失或无效时立即停止后续轮次。前两轮只能 `INCOMPLETE`；至少三轮完整时才计算各 workload 的域吞吐合计、最慢/中位/最大域、期望域数×最慢域、最慢步时与轮间波动。完整但波动>5%返回 `UNSTABLE` 和非零退出码；失败时不输出可误用的聚合性能指标。
- `PASS` 只代表此运行器的完整性与 A1 波动检查通过；不代表完整科研、数值、HBM、第二主机或集成验收。

## 后续 Linux/集群使用准备稿（本次未执行）

由 S00 核实环境、输入和授权资源，再经总协调接受候选后引用。只把候选复制到唯一的 `/home/share/songzhenlong/eitfm/opt/stage4_sessions/S01/<run_id>/candidate/`。输入及经过身份核验的库放在同一根下的 `output/cases/<case>/frames.npz` 和 `lib/`。不要覆盖共享路径，也不要重建或改写冻结数据；本交付没有包含实际 NPZ 或 .so。

在已分配的 Linux 节点先运行纯 stdlib 测试和以下语法检查，补齐本机未运行项：

```bash
bash -n "$S01_RUN/candidate/run_node16.sh"
python3 -B "$S01_RUN/tests/test_runner.py"
```

完成上述前置后，计时调用形式如下；`S01_RUN` 须预先设置成实际唯一绝对根。这是入口示例，不是提交调度器的授权，也未在本任务运行。

```bash
ROUNDS=3 NDOM=1 HBM=0 MEMPOL=membind SKIP_BUSY=0 \
  bash "$S01_RUN/candidate/run_node16.sh" ddr_b32_single \
  BATCH=32 KML_LINEAR=1 LINEAR_DTYPE=fp32 CKPT=0
```

后续顺序为单域→四域→整节点；HBM B32、32 电极 B64+CKPT+HBM，稳定后再 B32+CKPT+HBM，每个接受配置至少三轮，并补第二主机。先确认 HBM 分配器状态和独立 DDR/HBM 测量方案。整个远程门槛、预算和作业安排由 S00/总协调处理，本任务新增节点小时为 0。

离线严格复核现有输出：

```bash
python3 -B "$S01_RUN/candidate/runner.py" --summarize "$S01_RUN/output/reports/<tag>"
```

证据布局：`manifest.json`、`r<r>_d<d>.json`、`r<r>_d<d>.status.json`、`summary.json`；逐 PID 的日志/原始状态/命令位于 `sync_r<r>/`。失败或中断可保留缺失顶层状态，但该轮必定不能通过。预检错误和源/库漂移会直接非零退出，错误见启动 stdout/stderr，未必生成最终 summary。

回退：停止使用 S01 独立入口即可；没有改共享入口、数据或库，无生产回滚操作。
