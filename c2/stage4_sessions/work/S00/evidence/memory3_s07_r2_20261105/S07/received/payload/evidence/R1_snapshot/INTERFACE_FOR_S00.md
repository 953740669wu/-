# S07 R1：仅限固定小张量的两进程通信检查

状态：READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN。本文件不提交或授权新作业。
仅使用本轮 `candidate/`；不需要 EIT 模型、KML 算子、NPZ、corpus、训练入口或旧 S01 payload。
Python >=3.9；默认采用历史环境的 Python3.9.9 / torch2.7.1+cpu。不得安装或替换共享软件。

## 环境判断与接口依据

- 本地默认 Python3.11.9 未安装 torch，见 `evidence/local_environment.json`，实际环境检查 exit3；本机不能运行 Gloo 张量探针。
- S00 历史 job2026200 的原始 `result.attempts[0].stdout` 中 torch 配置为 USE_GLOO=ON、USE_MPI=OFF、USE_NCCL=OFF。提取内容及原始文件 SHA 见 `evidence/historical_backend.json`。这证明历史构建含 Gloo，不证明当前环境、socket/文件 rendezvous 或两 rank 已通过。
- 现有 R4 venv 曾运行 torch2.7.1+cpu（S00 R7 报告）；本轮未 SSH，也未实时核验集群环境。必须在获授权的同一 job 中重新执行 import-only 环境检查和实际通信检查。
- 使用 [PyTorch 2.7 官方通信接口](https://docs.pytorch.org/docs/2.7/distributed.html)：CPU Gloo、`init_process_group(timeout=...)`、`all_gather`、`broadcast`、`all_reduce(SUM)`、`destroy_process_group`。不采用原计划未经验证的“Gloo 共享内存”表述。本轮是同节点 loopback socket 通信，独立新目录的 `file://` 仅作 rendezvous；不测跨节点/网络互联。

## 资源方案：先具备实际两域授权，再运行

以下是待 S00/总协调排期的方案，不复用旧单域 job 授权，不调用 dsub、SSH 或自动申请资源。
一个物理节点内两个不同的完整 38 物理核 NUMA 域；通常分配 2×38=76 核，实际计算边界 2×36=72 核、预留 4 核。若只分配 36 核，须恰好是完整域的前36核。

| rank | 授权边界，必须由实际调度证据逐 CPU 列出 | 实际 worker 边界 | 预留边界 |
|---|---|---|---|
| 0 | allocation.json.ranks.0.allocated = A0；属于实际 NUMA 域 D0 | sorted(D0)[:-2]，36 个不同物理核，必须为 A0 子集 | sorted(D0)[-2:]，worker 禁用 |
| 1 | allocation.json.ranks.1.allocated = A1；属于不同实际域 D1 | sorted(D1)[:-2]，36 个不同物理核，必须为 A1 子集 | sorted(D1)[-2:]，worker 禁用 |

要求 A0∩A1=空集，D0≠D1，A0∪A1 是启动进程继承 CPU 掩码的子集。各域 sysfs 拓扑须为38个不同物理核；禁止将同一域拆两份或把主机全部可见核当作调度授权。
目前无本轮实际 allocation，**不提供虚构 CPU 号码**；`allocation.template.json` 故意留空，原样运行必拒绝。S00 从该 job 的原始调度分配填写两个实际 NUMA ID 与逐核列表，`scheduler_evidence` 填同 job 原始资源证据绝对路径，`job_id` 填实际 ID。程序校验 sysfs/继承掩码并记录原件 SHA；调度器专有文本未自动解析，S00 必须人工核对原件与 JSON 一致。

总内存建议上限24GiB（不是每 rank 24GiB），HBM=0；总时限建议≤300秒（≤900秒旧上限），单 case 父监督截止30秒、进程组宽限2秒、清理/回收最多另2秒。四项顺序执行，失败即停、不重试。拟占最多1节点×300秒=0.0834节点小时，实际节点小时未产生；新两域安排尚未授权。无合法两域授权就只交回资源缺项。

沿用冻结 CPU36 合同副本（SHA 见 SOURCE_MANIFEST.json），OMP36/MKL36/OpenBLAS1/cores/close；每个 worker 在导入 torch **前**缩到自己的 selected36。父监督器缩到两 rank selected 的并集。验证实际 torch intraop=36、线程快照全部 TID 掩码在对应 selected36 内；interop照实记录。这里不测真实36核利用率，也没有接受模型运行器的持续父线程采样/完整模型阶段证据，不能替代其验收。

## S00 命令（只在既有合法 job 内执行）

把本目录按原字节复制到当前账号自有的新隔离目录；以下 S07_RUN 为该副本绝对路径。不要修改候选代码或在本地证据目录复用旧输出。依赖环境若与历史记录不同，保留新来源证据并交回判断。下列命令自身不提交作业。

```bash
export S07_RUN="/实际新目录/S07_R1"
export S07_PY="/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3"
export PYTHONPATH="/home/share/songzhenlong/eitfm/sw/torch_kml"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
```

先核对该 Python/torch 仍为已知环境；保留实际 LD_LIBRARY_PATH 等环境来源，不注入模型、HBM 或 KML shim。该探针不依赖 shim，不通过增装软件补后端。逐条执行，任一步非预期非零就停止：

```bash
"$S07_PY" -B -c 'import hashlib,json,pathlib,sys; b=pathlib.Path(sys.argv[1]); d=json.loads((b/"SOURCE_MANIFEST.json").read_text()); bad=[x["path"] for x in d["delivery_files"] if hashlib.sha256((b/x["path"]).read_bytes()).hexdigest()!=x["sha256"]]; print({"sha_mismatches":bad}); sys.exit(bool(bad))' "$S07_RUN"
"$S07_PY" -B "$S07_RUN/tests/test_probe.py"
"$S07_PY" -B "$S07_RUN/candidate/comm_probe.py" environment --output "$S07_RUN/environment_current.json"
```

环境检查 exit0 仅说明当前 `is_available`/`is_gloo_available` 为真；exit3 为不可用，保存原件并停止。输出保存 Python/torch 路径、版本、模块/实际加载 torch 库 SHA、编译配置。环境检查显式单线程导入，不执行张量算子。

S00 将本 job 真实调度原件保存在 `scheduler_allocation.txt`，将填写后的 `allocation.template.json` **另存** `$S07_RUN/allocation.json`；不要改交付模板。核对两 rank 授权边界后执行：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

此命令内部依次执行四个 case，任何不符预期即停。每个 case 也可用以下入口独立复核，但不要在同 job 自动重试：

```bash
"$S07_PY" -B "$S07_RUN/candidate/comm_probe.py" run --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/另一个全新case目录" --case normal --pg-timeout 5 --deadline 30
```

case 可取 normal/crash/collective-timeout/watchdog。故障 case 的非零是探针预期行为；**单凭非零不算失败检查通过**，run_checks.py 同时核实已到注入点、具体终态及子进程回收。

| case | 预期证据 | 探针退出 |
|---|---|---|
| normal | 两 rank PASS、identity=[0,1]、broadcast=[1,-2,0.5,4]、SUM=[3,6,-2,1]，两个 child=0 | 0 |
| crash | rank1 已到 injected_crash，exit17；父监督停止 peer 并回收两个 child | 非零 |
| collective-timeout | rank1 到 injected_hang；rank0 在 broadcast 报实际 Gloo timeout，父监督清理 peer | 非零 |
| watchdog | 两 rank 到 injected_hang；父监督 reason=deadline，两个 child 回收 | 124 |

小张量使用 fp32、shape=[4]，所有数值二进制可精确表示，逐元素绝对差=0；不随机采样、不测带宽或吞吐。rank 身份先用 int64 all_gather 核对，随后验证实际 rank/world_size/backend、PID、run_id。所有输出目录必须不存在，rendezvous 文件必须由本次进程创建；不复用旧结果或旧 store，不自动切后端或绕过CPU36。

## 回传与接受边界

回传实际命令/来源/环境、原始调度资源与终态、allocation.json、environment_current.json、整个 checks_current_job（含 checks.json、各case manifest/commands/summary、两rank JSON和log）、逐文件 bytes/SHA/真实mtime_ns。保留失败中间文件，不改received原件、不挑选成功rank。

本地已跑的标准库检查不代表 Gloo、Linux进程组清理或数值通信通过；完整两rank通信、后端超时、崩溃、watchdog case本轮全部未运行。即使四项通过也只能接受“固定小张量通信探针检查通过”。同步训练、参数/梯度同步、optimizer、有效全局batch、学习率、schedule、短程收敛、训练性能全部未运行/待定；不据此启动4/16域或多节点。
