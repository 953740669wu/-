# R10唯一候选的同节点有限A/B提案（尚未授权执行）

候选只有fp32线性反向复用gy2；旧R9反向reshape不发生数据复制，预计只可能省很少的视图构造开销，不能称解决copy_热点。本提案用于淘汰或保留这一个候选，不预设提速；若协调认为收益空间不足，可不安排作业并关闭候选，不转入其它方案。

须先协调复核、再另派S01绑定具体包SHA和S00新部署/唯一marker/授权。旧2043445/2048959授权均已用完。无提交命令；下面仅为新分配计算节点中的命令。包不替代S00真实调度身份、资源/DDR/NUMA门禁、所属后代清理和终态收集。

S00拟新建`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_LINEAR_R10_<唯一时间>/payload`，解包核源码/候选/包SHA；原baseline文件和原工程/R9目录不写、不覆盖。descriptor仍引用原冻结字节SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6。原runtime ledger路径只读，本次每阶段独立outputs目录写自己的暴露清单。

```bash
export S02_ENGINEERING_DESCRIPTOR=/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json
export S02_ENGINEERING_DESCRIPTOR_SHA256=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6
# 占位目录须由S00替换为新审核绑定的实际路径。
bash /home/share/dengqingtian/opt/stage4_sessions/S00/S02_LINEAR_R10_NEW_REVIEWED_RUN/payload/run_ab_proposal.sh
```

包装仅顺序执行一次以下链路，某阶段非零立刻停止，后续不运行：

1. `screen_linear.py`：实际KML、fp32、CPU36的局部数值/alias筛选。与native本地替身严格区别；此PASS只代表线性单元，不放行直接性能测时。
2. `train_linear_ab.py --phase strict`：完整Encoder、原1600帧统计、seed0/B64前5次连续更新；baseline/candidate各独立模型/AdamW，切换F.linear角色后逐步运行，使用相同frame顺序/mask。比较h/voltage/coarse输出、loss分量及total、输入梯度、全部参数梯度/参数/相对初始化delta、AdamW step/一二矩和buffers。原冻结比较器：tensor最大绝差2e-5且相对L2<=2e-6（原near-zero例外保留），state绝差2e-6且同相对门槛，step exact。任一失败保留原失败、关闭候选，不放宽、不继续测时。
3. 仅收到`PASS_STRICT_ENCODER5`后，分别新进程运行`--phase perf --variant baseline`和`--variant candidate`；两侧receipt必须同源码清单SHA/descriptor SHA/节点/job/selected36。各重新按原seed0初始化，保持连续5更新，前2预热、后3观察，无profiler、无输出hook、同诊断/日志/暴露记录。两个role的实际导入路径/SHA、dtype/真实KML状态写result，不能只凭目录名认候选。

完整gate及性能入口本轮未在C2运行；本地只以小型夹具验证比较/拒绝分支并做AST/LF/bash语法检查，不称运行器真实路径已验收。严格gate的双模型/输出hook仅用于数值，不用其耗时或HWM评性能。性能两侧在独立新进程，RSS/HWM仍是各进程生命周期中采样的峰值，不是单步独占峰值，也不是最终restore后全job峰值；禁止reset或从严格gate遗留峰值做角色比较。

## 保持及预算

完整Encoder37995777、fp32/CKPT0、有效B64、原mean双loss/AdamW（lr1e-4/betas.9,.999/eps1e-8/wd.01）、原native SDPA/KML/库/线程路径。固定s0285/s0593的16unit/1600帧（每阶段train-only统计同一1600帧，训练只走原前320帧）。全部CPU/TID和KML计数/数值有限性检查保留，不通过删日志/检查制造提速。原初始化SHA/scale/frame IDs/mask与KML149调用/步也按旧参考核。

拟单节点单NUMA38分配/实际36、预留2；DDR请求和limit均24576MB、exclusive；900秒以内完成全部局部筛选+严格gate+一对性能运行。全入口840秒，清理30秒、收尾30秒，任何训练入口720秒后不再新步；S00须以总截止时间控制全链，不能每阶段各占900秒。最多完整Encoder20次更新（严格A/B各5、性能A/B各5），不做ABBA/多种子/多belt矩阵，不跑满时间，不重试。新源码/输入/资源/CPU/KML变化、数值FAIL、超时或信号立即停止；若24GiB下双模型gate超限就保留FAIL，不扩资源或改拆批。

## 输出/解释

收集`outputs/ab_JOBID`、`linear_screen_JOBID`、`strict_JOBID`、`perf_baseline_JOBID`、`perf_candidate_JOBID`各原件，含退出/命令/CPU/实际导入/库SHA、全部数值metrics、frames/masks、暴露清单、step耗时/RSS、诊断及setup/data/save-restore/未归属计时。checkpoint仅远端保存，收bytes/SHA/零额外更新恢复，数据/权重/ZIP/环境不进Git。

仅在完整gate通过、实际同节点/同线程/同库/同数据身份确认后，比较两性能侧后3步step_seconds的中位/范围和同范围RSS/HWM；同时列全部5步、诊断/账本/保存恢复及wall，不能用旧cn21341/cn21338结果当对照。单对3个样本仅为探索，不能给稳态或生产加速验收；若持平/慢或结果不稳，关闭本候选而不归咎阈值。正式split/subject UNKNOWN，无val/test或科学接受。
