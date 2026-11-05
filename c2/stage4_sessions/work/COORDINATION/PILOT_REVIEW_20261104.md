# 环境实测与 S01/S02 小试包复核

日期：2026-11-04。依据 S00/COMPUTE_ENVIRONMENT_REPORT.md、CLUSTER_EXECUTION_PLAN.md、compute_environment_verified.json、S01 R4 补充报告，以及 S02 round2_20261104T114949Z/REPORT.md 和 numerical_summary.json。

本聊天只核对已保存证据和准备包，未连接集群、创建远程文件或提交作业。

## 结论与执行顺序

1. 接受计算节点实际导入证据及 S01 Linux 协议交接，适用范围见下文。
2. 下一项为 S01 单域真实模型启动小试；资源和时限沿 S00 已准备方案，明确排期/授权与实际分配后执行。不是自动批准未知或长期算力，也不是本聊天已经提交。
3. S02 严格数值已有真实失败。准备包在提交前还需修正 CPU 绑定，随后只做原定一组 C2/KML 数值对照；在此期间可并行定位 Windows 同配置失败原因。
4. S02 训练内存阶段保持 NOT_READY：须先解决或明确评审数值门槛，并补独立轻量测量入口。S03 仍只允许安全与观测准备，放置性能优化继续等待。

## 已接受的新增证据

- job2026223 在 cn21417 以实际分配 1CPU/4096MB 真正导入 torch2.7.1+cpu、numpy1.26.4，完成 tiny autograd/NumPy 桥接、S01 原样导入/输入/实际库映射预检。作业已经结束，不能复用为模型 allocation。
- 解释器路径：`/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3`。环境引用共享只读 torch/KML，运行前需复核其身份。
- S01 R4 已保存的 Linux 证据覆盖 3 项 shell 语法、4 项进程清理检查、8 个合成协议场景；它补上先前跳过的 Linux 进程清理，不代表完整模型启动通过。
- 独立核对两个 ZIP 的包 SHA256 与各14个条目哈希，均与 PACKAGE_MANIFEST.json 一致。此检查仅确认包身份，不意味着两个包都已获准原样运行。
- S01 ZIP SHA256：1765cce6e9b3bacbdf23e3d30191afe8db9ae5fc7c3b95273292d1a4bc9b378c。
- 当前 S02 ZIP SHA256：7127f1b1465d2868b8d27e2e139ac9426f2e438784a9bdc5dae47e6368007a0a。该包需按下述 CPU 约束修订，修订后必须有新哈希/清单，不能继续引用此哈希为新包。

## S01 下一项

仅运行 S00 准备的单域38CPU、24GiB、最多900秒、HBM0/CKPT0、16_adjacent pre+dec、B32、三轮REPS1启动小试。先核实实际 Donau 分配/内存限制、同域 CPU 集合、输入/源码/依赖身份；实际内存不足则停止，不自动扩大资源或跨域。

验收看完整 shell→runner→numactl→真实前反向/AdamW→结果/退出状态/汇总链。失败保留日志，不重复提交或扩大到更多域。仅三轮短REPS1及旧demo的结果不能作为正式性能或科学训练基线；UNSTABLE 等失败需按原规则保留。

## S02 提交前修正：保持实际分配的4核

当前 pilot_s02_equivalence.sh 先检查继承 affinity 恰好4核，但随后执行 `numactl --cpunodebind="$NUMA_NODE" --membind="$NUMA_NODE"`。该节点绑定命令按域选择 CPU，在调度器可能仅通过继承 affinity 限制核心、cgroup CPU 限制又未独立证实的情形下，不能保证启动后仍是原4核。

S00/包维护方需只修改包装层：保存原始获分配 CPU 集合，使用 `--physcpubind=<该确切集合>` 配合原内存域绑定，并在实际 checker Python 进程内验证/记录 affinity 与分配集合相等、torch线程数为4。不得使用整域总CPU数作为额度。加入可复核检查并重做包/条目 SHA 与 shell 语法验证；模型、输入、原 checker、有效批量和数值阈值不变。

这是一项提交前约束修复，不声称已在实际作业中观察到越权用核，也不要求改变科学算法。

## S02 数值失败与下一步

当前权威新增报告是 `work/S02/round2_20261104T114949Z/REPORT.md`；根 REPORT 仍是首轮准备报告，不能只看根报告判断“模型从未运行”。

Windows/native 后端已实际执行完整16-pre、有效B64对B32×2、CKPT0/fresh。严格 loss 最大绝对差3.0517578125e-5超过预定2e-5；同配置完整诊断共有194项原判据失败，其中49梯度、13更新参数、33更新增量、98 moment及1 loss。输出/输入梯度一致不能覆盖这些失败。

不能仅把失败归为 loss 的绝对阈值，也不能未经证据直接断言微批算法错误。归约舍入与 near-zero 梯度经 fresh AdamW 放大是待隔离的解释方向。

建议 S02 在同配置、相同环境先做 reference 对自身/候选对自身的重复性检查，再隔离 loss 归约方式、梯度累积顺序和 optimizer 前后差异；对首次失败参数保留足够诊断，不用无关大矩阵搜索。不得修改 eps/LR/样本/阈值求 PASS；如需改变接受判据，须提交明确的误差尺度和实验影响依据另行评审。

S01 小试交接通过且 S02 包绑核修正后，才执行一组 C2/actual_KML 对照：单域4CPU/24GiB/最多900秒，16_adjacent/pre、有效B64、microbatch32、fresh、CKPT0、原严格阈值。结果独立记账，不能覆盖 Windows FAIL。当前 diagnose_same_config.py 固定 kml=False，不能直接用作 KML 失败诊断，需 S02 提供保持实际后端的诊断路径。

任一数值失败即停止扩大；先收齐该配置的实际后端诊断。通过数值门槛后，再审核轻量训练测量入口：参考与候选各用独立进程，无对照快照常驻，固定相同有效批、预热和更新次数，分别报告DDR与HBM口径。未准备该入口时不要用 equivalence checker 的进程峰值声称内存优化收益。
