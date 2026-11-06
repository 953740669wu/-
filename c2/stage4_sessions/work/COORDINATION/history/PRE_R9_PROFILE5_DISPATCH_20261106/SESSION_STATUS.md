# 总协调简短状态

- 更新/轮次：2026-11-06；JOB2043445_ENGINEERING_REVIEW，后续02/08待转发。
- 当前目标/结果：首次真实工程训练链路已完成并核收集原件；非正式质量/性能接受。00成功实跑，01前置审核/02冻结入口/08工具准备各完成，01/08结束时结果未到属时间先后。
- 真实运行：2043445/cn21341 SUCCEEDED/exit0，1600帧/16unit/25次连续AdamW/1epoch，38授权36实际、DDR24GiB同limit/exclusive，fp32/CKPT0/KML/完整Encoder；无重试，按已收终态无活动S00 job。
- 性能观察：程序86.6905秒、训练步骤58.4772秒、中位2.32994秒；采样process-lifetime HWM最大7258705920bytes，不能称整job最终峰值；调度96节点秒/usage95分列。
- 模型保存：checkpoint456135327bytes留远端，SHA=ec491c46c06f94a7fac54d5f80010866311743e1f722947cb680cdaf3579e403；恢复记录参数/AdamW/RNG/cursor/身份一致、固定前向差0、extra_updates0。协调未下载/重哈希权重。
- 数据/暴露：14300版manifest固定SHA前后未变；s0285/s0593各8unit，同belt/row/源SHA。1600帧无重复填充，25mask不同，暴露清单完全对账；subject未知，不称2受试者。以后按真实subject映射排除最终test，旧正式门禁仍DATA_NOT_READY。
- 本轮独立核对：RUN_COMPLETE绑定7原件大小/SHA、前置review绑定、调度成功/退出、25步/1600帧/16unit覆盖、finite/mask/KML、暴露账本、59 CPU快照及恢复记录一致；无SSH、无重跑模型/原19检查。证据JOB2043445_ENGINEERING_REVIEW_20261106.json。
- 修改范围：仅协调新核对JSON/AFTER_ENGINEERING_PILOT_20261106.md/总表和自身状态；旧三状态归档history/PRE_JOB2043445_REVIEW_20261106/；作者源码/原证据/暂存未改。
- 下一步：08只读整理实际2043445结果；02分析现有时间分解，准备2预热+3采样的有限CPU剖析包，不改算术/默认参数、不扩数据、不直接提交job。包核后另派01审核/00执行，原一次授权已用完。
- 其余/Git：00/01及03—07待命，避免重复审核/探针。提醒唯一Git窗口按新明确范围归档已核工程交付及原件，数据/权重/ZIP/环境不进Git；历史716文件批次保持，不blind add全部工作区。
- Git本轮：用户询问可推送范围；以首次真实工程运行00/01/02冻结交付加协调记录生成精确TSV，排除02/08正在写的新任务及共享短状态、S02 ZIP与数据权重；唯一Git窗口执行，本协调不stage/commit/push。
