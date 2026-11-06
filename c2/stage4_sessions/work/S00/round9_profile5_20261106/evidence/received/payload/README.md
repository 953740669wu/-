# S02 R9：首次真实工程基线后的有限CPU剖析

此包仅LOCAL_PREPARED，供协调复核后另派S01专项审核和S00执行。旧job2043445的唯一执行授权已用完；此交付不构成新的提交许可，不复用旧marker/旧部署目录。本轮没有新job。

## 问题和观测口径

已有25步真实训练仅记录每步合计，不能区分attention、KML linear、反向或AdamW占比。此包把同一原始seed0训练缩至前5次连续更新，前2次预热，后3次各采集一段CPU profiler。模型、原mean损失表达式、AdamW参数及顺序、fp32/CKPT0、native SDPA/KML linear、归一化和全部数据/CPU门禁保持。

沿用原1600帧/16单元/2case清单，实际训练前320帧，无重复填充；全部1600帧仍用于原工程train归一化统计。REFERENCE_FIRST5.json来自job2043445已绑定原result/steps，包含原初始化/归一化、单元身份和前5步frame序列/ID哈希/mask/loss/KML计数。逐步frame/mask及初始化/scale必须相同，原loss比较器和阈值不改；不改变输入或划分，按原模型seed0初始化并核初始权重SHA，不读取或恢复旧远端权重。

## CPU剖析和开销

- 第1、2步无CPU事件采集；第3、4、5步各使用现有torch.profiler的CPU活动。关闭shapes/memory/stacks/FLOPs，不安装依赖。能力缺失或必要阶段事件缺失返回UNSUPPORTED_PROFILER并停止，无其它backend回退。
- 每步wall阶段：zero_grad_before、forward_loss、zero_grad_after、backward、optimizer。保留原requires_grad、两次zero_grad的参数及顺序、mean双loss/backward/step表达式。
- 第3—5步的KML Python GEMM调用加有界record_function标记；最多256次/步，原计数/库/ctypes及调用参数不变。标记包含Python/计数/分配/ctypes/原生调用，不能称精确KML内核时间。原生attention和其它Torch事件按实际可见事件交付，无硬件采样或原生栈保证。
- step_seconds为训练调用内含标记的wall；profiled_call_wall_seconds还包括profiler setup/start/stop和导出。profiler_outside_step_seconds另计这些外层开销；事件/标记在训练内部产生的扰动不能由此次非配对采样精确扣除，字段明确为null/UNKNOWN。不能把warmup当未剖析对照，也不能把3步采样速度当正式吞吐、稳态性能或加速收益。
- trace为FunctionEvent CPU时间区间，带线程/父事件ID。events摘要最多列80个self CPU key，同时保留调用数及嵌套total；它不是操作系统进程CPU消耗或全部工作线程覆盖证明。禁止相加父子total、禁止self和total重复相加，禁止把跨线程事件合计直接除wall称占比。

每个采样最多50000事件；Torch现有API不能在采集过程中逐事件取消，因此在每个单步采集结束后核事件上限，超限停止、不导出、不截断、不重试。单步采集受全入口硬时限约束。最多3份trace，各<=8MiB；3份事件摘要，各<=1MiB，合计<=27MiB。JSON在写入前核bytes，文件用独占创建，不覆盖已有输出。没有无界Chrome trace导出调用。其它result/steps/CPU/暴露证据及远端checkpoint另计。

## S00拟执行命令（需新授权与审核）

S00下一轮须新建`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_<新唯一时间>/payload`，解包并核SOURCE_SHA256.json及具体zip SHA；不能使用旧ENGINEERING_PILOT目录或旧marker。S00须重新准备原生调度身份、实际资源、唯一提交/不重试和所属后代清理包装，绑定新的S01审核SHA；原部署入口按旧协议判结果，不能原样拿来接收此包的新profile协议。

descriptor必须沿用原ENGINEERING_DESCRIPTOR.json的完整字节，SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6。可直接只读引用旧已冻结descriptor，或复制相同字节到新目录。它的runtime_exposure_ledger_path只作为旧来源元数据保留，**不作本次输出路径**；本次运行清单写入新`payload/outputs/profile_JOBID/EXPOSURE_LEDGER.json`。原EXPOSURE_LEDGER_INITIAL只读；旧运行清单及checkpoint不触碰。

以下只是计算节点中的应用入口，不是提交命令：

```bash
export S02_ENGINEERING_DESCRIPTOR=/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json
export S02_ENGINEERING_DESCRIPTOR_SHA256=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6
# 由S00将下列占位路径替换为经新审核绑定的新目录；不复用2043445。
bash /home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_NEW_REVIEWED_RUN/payload/run_profile5.sh
```

登录侧可用现有R4 Python运行inspect_engineering.py核原descriptor/manifest/固定选样和文件SHA；它不导入Torch/读取NPZ数组，不执行模型。输出须用新路径：

```bash
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B \
  /home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_NEW_REVIEWED_RUN/payload/inspect_engineering.py \
  --descriptor "$S02_ENGINEERING_DESCRIPTOR" --descriptor-sha256 "$S02_ENGINEERING_DESCRIPTOR_SHA256" \
  --output /home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_NEW_REVIEWED_RUN/metadata_gate.json
```

资源拟为单NUMA38分配/实际36物理核、预留2，DDR请求和limit均24576MB、exclusive、作业最多900秒，完整应用840+kill/cleanup30+收尾30；内部720秒停止新更新。OMP36/MKL36/OpenBLAS1/cores/close，复用R4 Python/KML/OMP/shim和同PID/全部TID守卫，调用线程可单核绑定；不设置interop=608或其它新线程默认。

## 停止与收集

成功状态PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE，更新5、320训练帧、3份采样、原AdamW step1..5、保存/恢复额外更新0。checkpoint沿用未改的工程保存函数和ENGINEERING_REAL_CORPUS_PILOT_V1标签，其identity绑定本包源码和5步配置；result的独立PROFILE5协议负责区分诊断运行。达到5步立即停，不跑余下20步、不跑满900秒。源变化/身份不符、数值超原阈值、KML/CPU异常、profiler缺失/超限、输出已存在、预算/信号任一发生即FAIL/INCOMPLETE停止；不换样、不重试、不扩资源。外层若硬终止，保留可能中断的暴露frame IDs，不能推断已全部确认使用。

收集新`outputs/profile_JOBID`全目录：result/steps/EXPOSURE_LEDGER、3份trace及3份events、CPU分配/库/命令/日志/退出/timeout和S00后代清理/调度原件。checkpoint/final.pt只留远端，收路径/bytes/SHA/恢复证据，不下载进Git。RSS仍为process-lifetime采样HWM，不作本轮训练内存测试或全job最终峰值结论。无正式split/subject/val/test，未来仍需将两case实际subject排除最终测试。

必要本地测试：使用现有S02 round2 .venv执行`python -B tests/test_profile5.py`。只用小型原生Torch36夹具，含连续5步算术/参数/AdamW/RNG精确对照、采样/限额/unsupported/身份拒绝及零额外更新恢复；不运行完整Encoder或KML。交付身份和本地证据见PROFILE_READY.json、REPORT.md、evidence/local_validation.json。
