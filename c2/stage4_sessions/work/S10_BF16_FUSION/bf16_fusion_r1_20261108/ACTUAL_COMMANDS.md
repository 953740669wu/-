# S10 执行与证据

本批以北京时间 2026-11-08 10:16:59 为保守起点，取首次记录的工作区时间 10:17:00.85 前一整秒。任务卡 SHA 与预算身份见 SOURCE_IDENTITY.json。运行全程使用原 16 电极 Encoder 工程数据描述、同一 KML/OMP/shim 和冻结 HBM 库。单域 38 分配、36 计算、2 保留，DDR request/limit 24576 MiB，实驻 HBM 3800 MiB。五次均在 cn21762 独占运行。每次提交前读取 00、09 当前短状态与作业，登录端实时校验原生队列、节点、排除项和本窗口唯一提交标记。

## 热点和实现

F 选择 CPU fused AdamW。R9 job2048959 的优化器阶段三个样本为 0.173312、0.173939、0.172542 秒，用于选择热点。S10 复用现场 Torch CPU fused kernel，无额外 profile。原比较器逐张量在第 2 步发现二阶矩绝对差 6.103515625e-5 超过 2e-6。候选配置及计时入口见 F_CANDIDATE.diff。固定配置的实际数值差足以拒绝该 fused 实现，未进一步拆分底层舍入归因。

B 只更换 QKV 权重梯度。历史 C1 的 2.4× 为该算子证据。实际输入转换、清零、KML 调用及全模型 dtype 接口见 B_DTYPE_INTERFACE.md。正式候选每个完整步骤调用 12 次 sbgemm，24 次 FP32→BF16 转换。严格门中转换、清零、调用中位分别为 53.40、2.56、64.70 毫秒，取自有数值采证的五步。B 第 1 步只有 QKV 权重的梯度、权重、增量和两个 moment 非零差。第 2 步起出现其余参数的失败。全部五步 loss 最大相对 L2 为 5.03e-5，仍由逐项参数和增量门拒绝。逐项失败见 B_FULL5_FAILURES.json。

## 准备、提交与修复

在 S10 本地目录用 python -B bind_run.py 生成包与绑定。执行时选单域及 1200 或 1800 秒墙钟。登录端在各自远端 run_id 内校验两个 SHA，unzip -n，依次运行 prepare.py、inspect_metadata.py 和 recheck_fixed_inputs.py。唯一原生提交入口为 nohup /usr/bin/python3 -B submit_once.py BINDING_SHA。每轮的实际 argv、提交记录、固定数据前后核验和调度回执已取回到 jobs/<run_id>/received。终态后运行 collect_evidence.py 收集 SHA/CRC 可复验的 ZIP。两个 F 预提交停点留在 S10_F1_SINGLE 与 S10_F1B_SINGLE，均未调用 dsub。所有 B 重试均保留原包、证据和 REPAIRS.diff。

B 的夹具用原 S04 已有 Python/Torch 环境作纯打包。调用原 common.fixture() 生成固定输入和模型初始 state_dict，把 4 个输入和 16 个参数逐张量核对原 S04 r1_block_numeric.json 后用 torch.save 写出 FROZEN_FIXTURE.pt。未运行本地模型前后向或优化步骤。导出的夹具 SHA 为 33b4dd664828da76263ae78e4f6388fa734c8ad58d2cd6971ccf3e41e23d2b2d。

B 首次计算节点的 /opt/HPCKit、/usr/include 与 /usr/local/include 搜索无 kblas.h。目标冻结库无 RPM 所属。登录端不能解析镜像域名。通过官方 HTTPS 在 S10 私有目录取 HPCKit 26.0.RC1，核官方校验值，解出 KML 子包和毕昇 SME multi 版，核库 SHA 与目标一致，再只将同发行 kblas.h 放入候选包。计算节点编译私有 wrapper，实测由 wrapper 引用的 sbgemm 地址与冻结 KML 句柄解析地址相同。头文件、官方校验链、源码和实际 wrapper SHA 见 b_run/verified_kml/PROVENANCE.json 与最终作业的 kml_abi/compiled_identity.json。发行包内的 GCC SME multi 版 SHA 不同，未用于验证。 [华为官方发行目录](https://mirrors.huaweicloud.com/kunpeng/archive/HPC/HPCKit/)

| 作业 | 原生终态 | 判定 | 排队秒 | 计入分配秒 |
|---|---|---|---:|---:|
| 2063247 | FAILED / 应用 exit 2 | F 在第 2 步二阶矩门失败 | 4 | 90 |
| 2063286 | FAILED / 应用 exit 2 | B 初次找不到头文件 | 2 | 9 |
| 2063319 | FAILED / 应用 exit 2 | wrapper 编译通过，旧 S04 控制 helper 导入失败 | 3 | 23 |
| 2063324 | FAILED / 应用 exit 2 | fp32 控制原 83 项全过，标量逐位采证失败 | 3 | 23 |
| 2063332 | FAILED / 应用 exit 2 | B 模块门通过，完整五步门拒绝 | 2 | 141 |

预算分配取原生用量与起止整秒差的较大值，原生 wallclock 合计 283 秒。所有完整更新均按实际 AdamW 计入，包含 F 候选第 2 步已更新且比较失败的一次。数据访问 1088 帧次，唯一帧为同序列前 320 帧。全部五次独占作业原生 PID 为“-”，应用所属进程清空，2020 页 HBM 池归还。最终实时队列无 S10 作业。源身份、逐步数据、精确比较和终态清理见 BF16_FUSION_RESULT.json、EVIDENCE_VERIFICATION.json 和 jobs。

## 性能与归档

| 验证 | S10 结果 |
|---|---|
| F 单域及四域 25 步整步 A/B、RSS/HBM 对照、三轮稳定性 | 严格门失败后跳过 |
| B 200 步配对 loss、梯度、漂移 | 完整模型五步门拒绝后跳过 |
| B 四域 25 步整步 A/B、RSS/HBM 对照、三轮稳定性 | 完整模型五步门拒绝后跳过 |
| 原 C 路线 16 电极 50 帧/秒/域、32 电极 5 帧/秒/域 | S10 无正式性能数据 |
| 原 F 路线非 GEMM 占比 ≤15% | S10 无有效配对阶段比例 |

沿用原验收的 fp32 HBM 配置。仅使用工程固定样本。GIT_ARCHIVE_S10_R1.tsv 给唯一 Git 窗口，列内每项均可核 SHA。TSV 自身另算一项。发行包、第三方头文件、二进制、夹具权重、运行 ZIP、源数据和其他窗口文件留在各自证据范围。
