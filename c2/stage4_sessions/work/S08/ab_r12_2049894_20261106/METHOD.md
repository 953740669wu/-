# R12只读A/B口径

只读RUN_COMPLETE明确指定的4阶段result/steps/ledger及5份主绑定；不扫描其它job、不载入任何NPZ/权重或执行Torch。INPUT_VERIFICATION保存32项路径/bytes/SHA/收集绑定，分析前后再次核SHA。target使用其局部R12协议，strict/perf使用R12_AB协议，不放宽旧PILOT/PROFILE5/GEMM5解析门禁。

性能统计严格要求连续1—25及相同AdamW步号；sampled必须恰为step6—25。保留全部25个step_seconds，前5剔除后对20个值取中位和min/max；全25步和另外计算。百分比为(candidate median/baseline median−1)×100，正值是候选耗时增加，不写成提速。缺步、重复步、错误采样标记、非正或非有限耗时拒绝生成接受状态。

内存范围为同一25更新内rss_before/rss_after共50个时点。HWM取这些时点的peak_rss_bytes最大值，除2^20为MiB。它是各独立进程采样时刻的process-lifetime HWM，不是单步独占或整个job最终峰值；不把两个独立进程的HWM相加。

summarize_ab.py生成基础JSON和39项核对；定向阶段元数据复核另确认target1/2调用、strict两角色各5更新及149/161调用、strict与perf首次5步帧mask、strict原始log、候选导入SHA和checkpoint身份记录。结果写VALIDATION；没有重新运行target/3895 strict/原15 loss套件，均核已收记录。

两perf为同节点/同job的不同PID、顺序baseline→candidate，统计/初始化/帧/mask/环境/库一致；原计数、诊断、暴露与恢复边界保留。严格数值阶段与无profiler性能阶段分列，不把strict比较开销或旧R11包裹时间混作性能样本。分项计时和未归因差额沿用原记录，不推断未测来源。

AB_SUMMARY.json保留原25/观察20计时、HWM原bytes、源result/steps身份及恢复记录；完整原帧/CPU快照仍查绑定原件。AB_SUMMARY.md是结合协调结案处置的简短说明。不能从单对或步范围重叠推断显著性/稳态回退；数值通过与无收益分别记录。保持原基线，不集成、不搜索tile或产生新job。

LOCAL_FIXTURE仅4个统计检查：warm5/observe20及全25合计；缺步/重复/采样标记；NaN；百分比方向与无效分母。先写检查再实现，不重复旧套件。命令为`python -B -m unittest discover -s c2/stage4_sessions/work/S08/ab_r12_2049894_20261106 -p test_summarize_ab.py -v`。`python -B summarize_ab.py`只重算本轮显式绑定的元数据，拒绝覆盖已生成的AB_SUMMARY.json。
