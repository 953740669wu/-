# S08 DDP结果读取：准备阶段

读取格式依据S07初步INTERFACE及候选train_ddp.py中的原子rank报告、manifest、participants、逐步/数值门槛/曝光/事件。PROVISIONAL_SOURCE_INPUTS保存当时的字段来源SHA；这不是冻结训练包审核。07最终TRAINING_READY到位后重新核具体来源/绑定，00实际RUN_COMPLETE到位后先核analysis_inputs和收集索引，才生成INPUT_VERIFICATION并允许实际CLI运行。代码不会扫描其它job或读取权重/NPZ。

只复用旧S08 summarize.py的distribution/clean/非负有限数判断，先核原SHA ff0f31...、禁止写bytecode，旧PILOT解析入口不执行或改门禁。新增适配显式只认REAL_DUAL_DOMAIN_DDP_V1。

按来源区分：rank.completed_updates是在optimizer之后、strict之前持久化的计数，记为“rank已执行optimizer计数”；rank.steps/steps.jsonl在门槛之后发布，记为“完整日志步”。parent.global_updates只在实际存在时转述，不由min(rank计数)推算全局完成。参考更新单列，缺rank/reference字段保持UNKNOWN；后5门槛未过且两rank报告计数均不超过5时，6—25阶段NOT_RUN。超过预算或父/子报告矛盾按原件列出，不修成完整结果。

完整成对step核局部32/全局64、原先后顺序和并集、跨step不重复；合并两个局部frame IDs按原compact/sort_keys JSON方式核全局帧SHA，两rank全局mask哈希一致。不能从相同seed推断mask或重算未记录的tensor。状态只比state_identity原名参数/AdamW摘要，不比整checkpoint文件SHA；原数值是否通过直接看gate_metrics与两rank原strict计数/错误，不引入或放宽比较阈值。

曝光按rank0/rank1/reference保留原选中单位元数据、确认观察次数/独特帧与in_flight；统计加载/参考/探针/训练重复观察不自动合成“新训练吞吐”。完整逐步日志覆盖不等于失败时全部实际曝光。来源细节及未确认范围保留，后续正式test仍须按真实subject追溯排除。

前5共存参考与后20各自汇总每rank训练/forward/backward(含DDP同步)/optimizer、分母/日志状态collective、参考gate等待/参考/诊断。范围可能嵌套，不相加冒充wall；成对step的最大本地调用耗时也不是精确对齐的全局step wall。监督器首尾单调时间仅为含清理窗口，不是纯训练或完整调度壁钟。DDP原始reducer平均采样计时不当独立网络延迟。

RSS与process-lifetime HWM按rank/阶段分列，KiB转bytes；后段高水位可能继承参考共存峰值，不称纯DDP自身峰值。不将两进程高水位相加。缺时间/内存数据为UNKNOWN/无有效观察，不填0。speedup/scaling_efficiency/steady_state_gain固定NOT_MEASURED，不使用旧单域运行作对照。

当前仅5个LOCAL_FIXTURE：首步门槛失败保留物理2+参考1；缺rank未知；完整25/50/5/55计数；分片与状态冲突；缺日志/旧PILOT协议拒绝。未执行真实DDP、模型或大矩阵。运行`python -B -m unittest discover -s c2/stage4_sessions/work/S08/real_dual_ddp_summary_20261106 -p test_ddp_summary.py -v`。

实际CLI为`python -B summarize_ddp.py`，必须先有本轮已核的INPUT_VERIFICATION.json（all_passed、job_id、run_directory、精确资产身份），拒绝旧/漂移数据或覆盖DDP_SUMMARY.json。上游未冻结或真实结果未到时只发布准备记录；等待上限见WORK_STARTED，不安装服务或在会话结束后继续监视。
