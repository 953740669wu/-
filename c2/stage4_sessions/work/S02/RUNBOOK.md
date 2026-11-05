# S02 复核与后续运行

所有本地命令从项目根 `E:\eitfm_c2_stages2-4_2026-11-03` 执行。仅写 `c2/stage4_sessions/work/S02`。不调用 SSH、不修改共享代码/运行器/库，不安装 torch。

本轮按S00_REMOTE_REVIEW补充`INPUT_PAIRING_PROTOCOL.md`。先前交付已逐文件校验并归档到`history/before_pairing_20261104T092345Z`，当前REPORT为新增配对任务后的版本。现有训练步源码不变，新增只读配对loader和合成输入检查；未执行真实输入适配。

## 已运行的本地检查

```powershell
python -B c2\stage4_sessions\work\S02\tests\test_contracts.py
& 'E:\Codex\home\cache\phase4-speed-venv\Scripts\python.exe' -B c2\stage4_sessions\work\S02\tests\test_paired_inputs.py
python -B c2\stage4_sessions\work\S02\tests\check_equivalence.py --belt 32_skip4 --part pre --microbatch 16 --checkpoint --output c2\stage4_sessions\work\S02\evidence\numerical_not_run.json
```

第一条4项stdlib检查通过（精确分数代数/源码AST/副本字节）；第二条使用已有NumPy环境，10项真实数组配对检查通过，两者均不执行模型。第三条检查torch/numpy依赖，缺任一项退出2并写NOT_RUN；当前默认Python缺二者，NumPy环境缺torch。不要把退出2当通过，也不要用 `|| true` 隐藏它。该JSON只是依赖门检查，不是完整48组中的一项数值结果。

`prepare_evidence.py` 本轮开始时核验S00的108个原文件及最新87个交付物、复制两份字节相同的模型源、核验四个解释器、输出解析内存和本轮依赖快照。首次52项交接时的证据保留在history，不覆盖归档。准备已完成，不必重复执行覆盖本轮开始证据。

```powershell
python -B c2\stage4_sessions\work\S02\prepare_evidence.py --final
```

末次命令重新核验共享原文件/S00、比较协调依赖变更、仅编译语法（不导入torch）、生成训练步新增diff、配对loader新增diff、完整数值脚本相对归档的最小diff及SHA256索引。不会运行数值或远程计算。

## 有真实 torch 后的完整数值检查（本次未运行）

**先读VALIDATION_PLAN.md、INPUT_PAIRING_PROTOCOL.md和MEMORY_REVIEW.md。** 需要真实torch和numpy。此脚本默认使用原生CPU torch，支持Windows；只执行冻结源码中的原始Encoder/Block/UNet/protocol_angles定义，避开原CLI顶层resource/argv/NPZ加载。合成NPZ/sidecar经配对loader进入模型，读取后清理临时文件；所有固定张量、idx、帧ID及初始权重哈希写入结果。没有替换或缩小模型，没有模拟torch。只有实际KML可加载且显式--kml时才调用KML，不将torch.mm fallback叫作KML验证。

单个配置模板：

```powershell
# 将真实 torch 环境的解释器填入 $torchPython；不要把当前无 torch 的解释器当作准备就绪。
& $torchPython -B c2\stage4_sessions\work\S02\tests\check_equivalence.py --belt 32_skip4 --part pre --microbatch 16 --checkpoint --history seeded --threads 4 --output c2\stage4_sessions\work\S02\evidence\future_run_unique_id\32_pre_m16_ck1_seeded.json
```

`$torchPython` 是待现场确认的解释器路径，不在本次替用户指定环境。完整矩阵为 belt=16_adjacent/32_skip4 × part=pre/dec × microbatch=64/32/16 × checkpoint=off/on × history=fresh/seeded，共48配置，定义见 `evidence/planned_matrix.json`。每个配置独立进程，reference始终为原始mean损失、B64、CKPT0；candidate包括B64×1本身，避免仅对比两个同样错误的候选。history seeded为合成AdamW历史状态，不是训练过的checkpoint。

每项退出0仅表示该配置的**合成输入完整模型等价检查通过**；退出1为失败，保留JSON首个失败及已测指标；退出2为依赖缺失/未运行。容差不能随运行结果自动放宽。脚本需要同时保留参考参数/梯度/输出/state快照，内存高于训练步；B64 baseline可能需要数十GB，只在已确认资源的环境执行，不能拿这套脚本量4GB目标。

未来C2单配置命令形式（仅准备；需S00环境、S01运行器及协调排期，不在登录节点执行）：

```bash
LINEAR_DTYPE=fp32 KML_BLAS_LIB=<S00核实的绝对库路径> \
  <S00核实的python> -B <隔离S02根>/tests/check_equivalence.py \
  --belt 32_skip4 --part pre --microbatch 16 --checkpoint --history seeded \
  --threads <本域实际授权线程数> --kml --output <隔离S02根>/evidence/<unique_run_id>/32_pre_m16_ck1_seeded.json
```

占位符不是可直接执行的集群配置；库路径、CPU/NUMA绑定和输入哈希由S00确认，运行完整性沿用S01接受版本。这个独立程序不是已接入run_node16的计时入口，没有现成生产部署命令。

## 给后续任务的接口

`candidate/training_step.py::training_step(enc, dec, opt, v, angles, belt, y0, *, part, microbatch, mask=None, t=None, noise=None, abar=None)`：输入是已经固定并完成原入口归一化的整批张量；一次调用完成一个有效批的一次更新，返回detach的整批loss。pre使用整批mask分母，dec使用整批图像元素数。该函数不抽样、不改LR、不加载数据、不做barrier/all-reduce。`enable_checkpoint(enc)`在模型建立后调用一次，保持参数与state_dict键不变。

S07后续接DDP时，先明确跨rank mask分母与DDP默认梯度平均的补偿、末微批同步及全局batch，再做多rank等价检查。本任务只保证接口准备，不声称当前本地分母可以直接代表不同rank样本/掩码数量的全局归一化。

配对loader接口及真实输入前置见INPUT_PAIRING_PROTOCOL.md。当前没有命令把远程worker_test或corpus自动下载/改写；将来真实源descriptor必须包含可信冻结NPZ和sidecar SHA。各belt单独准备，不能把legacy共享images交给两种belt。候选若在C2运行，路径须放当前账号自有目录，具体路径由S00核实。

回退：停止导入独立candidate即可；共享源、正式入口和manifest从未改写。没有上传、部署、调度作业或commit。审查索引见 REPORT.md 与 ARTIFACT_SHA256.txt。
