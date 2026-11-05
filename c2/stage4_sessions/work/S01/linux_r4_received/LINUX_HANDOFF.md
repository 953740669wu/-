# S01 R3：Linux 验证交接

本目录不改 ROUND1_ACCEPTED_FILES.json 指向的文件。`linux_payload/candidate` 保持已接受 R2 的逐字节副本；没有重写模型、运行器、分配器或输入，也不整合 S02。

## 需要 S00 提供的环境

第一层只需已有授权的 Linux 终端、Bash、Python≥3.9及当前账号独立目录，用于短时 stdlib 子进程协议检查，不需要 torch、NPZ 或 HBM。当前 Windows 上 WSL 未安装，PATH 未发现 Docker/Podman；Git Bash 启动失败且不属于 Linux 内核环境。请提供 Linux 主机/账号、现有登录方式和可写独立目录，不把口令写入文件。

第二层实际启动前需 S00 明确：分配的 job/计算节点、授权 CPU/内存集合、时限、实际 torch+numpy Python 路径/来源、KML/OMP/shim 加载方式、legacy NPZ 原样副本与库路径。当前账号既有作业不是本任务额度；不在登录节点跑模型，不修改共享 owner 目录，不自行安装环境。

首次模型小试建议提交排期的边界是：**1个已分配节点、仅1个NUMA域、最多38线程、DDR预算32GiB、最长15分钟，HBM=0**。这是待 S00 确认的需求，未分配、未提交、没有新增节点小时。先运行16电极 pre/dec 的完整原模型训练步骤；失败不扩大到32电极、四域或HBM。

## 1. Linux 进程清理与8场景协议

将 `linux_payload/` 整体原样放到账号自有唯一目录，以下用实际绝对目录设置变量：

```bash
S01_RUN=/home/share/dengqingtian/opt/stage4_sessions/S01/<unique_run_id>
export S01_RUN
bash "$S01_RUN/run_linux_checks.sh"
```

脚本核对 SOURCE_MANIFEST，运行三个 `bash -n`（R2入口及两个本轮脚本），再运行既有套件中与Linux分支直接有关的4项：后代清理、失败同伴与独立对照进程、超时/正常退出、启动失败。最后调用既有 exercise_local.py 验证8个合成协议场景。没有新增重复的本地测试矩阵。

输出为 `evidence/LINUX_PROTOCOL_<UTC>/RESULT.json` 与逐步日志，合成原始证据在对应 SYNTHETIC 目录。`PASS` 只表示Linux进程/协议；模型执行和集群性能字段固定 NOT_RUN。Windows/MSYS会被拒绝，不能用Git Bash冒充Linux。

## 2. 真实解释器、导入、输入及动态库链

在 S00 明确分配的计算节点，先将经过核验的shim放到 `$S01_RUN/lib/libkml_sgemm_shim.so`，原样legacy输入放到 `$S01_RUN/output/cases/s0322p0/frames.npz` 与 p1同路径；不在原数据上适配或重写。

`runtime_preflight.sh` 逐字复用已接受入口中 exec 之前的环境设置，仅把最终执行目标替换为 runtime_probe.py。S00提供的实际Python须由这条命令的 `python3` 解析到；如需要PATH设置，先明确记录，不能从其他账号私有环境静默继承。

```bash
export S01_JOB_ID=<S00分配的job_id>
export S01_COMPUTE_HOST=<S00指定的精确计算节点hostname>
bash "$S01_RUN/runtime_preflight.sh"
```

job字段只是调用方声明，不能替代调度器证据。探针拒绝非Linux、主机不符及login节点，记录实际解释器、torch/numpy/kml_ops和模型导入路径、允许CPU/内存集合、相关环境变量、已加载KML/BLAS/OMP/shim库的路径与SHA。只记录相关变量，不采集凭据。原NPZ必须匹配R2固定SHA。

探针仅导入模型并核对来源，不运行模型forward/backward，也不验证OMP ABI数值兼容；输出 `evidence/RUNTIME_PREFLIGHT_<UTC>/RESULT.json`，其PASS不能改写为完整模型训练通过。

## 3. 实际模型启动链小试（待资源交接；本次未执行）

仅在上两层通过、S00确认资源/时限及库配对后运行。此命令仍执行接受的run_node16.sh→runner.main→numactl→原模型→barrier→原子JSON→状态/汇总，未替换模型为桩。

```bash
timeout --signal=TERM --kill-after=10s 900s \
  env ROUNDS=3 NDOM=1 CORES_PER_DOM=38 SKIP_BUSY=0 SAMPLE_FOREIGN=0 \
      HBM=0 MEMPOL=membind RUN_TIMEOUT=240 SYNC_TIMEOUT=300 REPS=1 \
  bash "$S01_RUN/candidate/run_node16.sh" legacy_16_startup \
      BATCH=32 BELTS=16_adjacent PARTS=pre,dec CKPT=0 \
      KML_LINEAR=1 LINEAR_DTYPE=fp32
```

保留原预热与完整encoder/decoder前反向和AdamW更新；计时REPS=1仅为有界启动检查，三轮不能作为正式性能三轮验收。SYNC_TIMEOUT沿用300秒；单域没有跨域到达差异，整轮240秒与外层900秒为停止条件，不会无限等候。外层TERM先给接受的监督器清理机会，最终KILL不改变任务边界。

退出非零、SIGBUS/OOM/超时、结果不完整或配置不一致即停止。若进程与结果完整但spread失败，保留UNSTABLE和原始值，不放宽5%门槛、不称性能通过。16电极输入仍标LEGACY_TIMING_ONLY，已知目标错配不因链路运行而得到科学接受。

需回传三类材料：Linux协议结果与进程日志、runtime预检结果、实际模型run目录的manifest/commands/逐PID状态/JSON/summary及外层退出码。只有实际模型执行后才能报告真实启动链结论；32电极、HBM、四域/整节点/第二主机仍另按门槛安排。
