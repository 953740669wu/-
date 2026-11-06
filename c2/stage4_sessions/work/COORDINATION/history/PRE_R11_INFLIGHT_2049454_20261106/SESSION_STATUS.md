# 总协调简短状态

- 更新/轮次：2026-11-06；R10_DISPOSITION_R11_GEMM_DISPATCH，待用户转发，不是已开工/提交。
- 本轮依据：先读02/08短状态/摘要；因候选价值判断定向读R10 DECISION/唯一diff/A-B提案及08实际PROFILE_SUMMARY；不重复模型/旧检查。
- R10结论：fp32反向复用gy2仅省50次重复view，R9反向reshape没有矩阵复制。作者7本地检查/115原比较差0是native替身，实际KML/完整Encoder未跑。协调CLOSED_NOT_SELECTED_LOW_BENEFIT，保留候选/原件、不集成、不提交20更新A/B；非数值FAIL。
- 08结论：三次每份KML forward50/backward99，447包裹精确归属；copy共1003次含optimizer765但约3.6ms，ViewBackward96约172—244ms、Linear前向62及其它。不能把copy全给Linear反向，也不能按调用数排耗时。
- 本轮核验：R10就绪绑定10份、08归因摘要资产11份bytes/SHA无漂移；只查必要diff与报告，不复跑7/31/23/6检查或原模型。证据R10_LOW_GAIN_AND_R9_ATTRIBUTION_REVIEW_20261106.json。
- 下一步原因：KML包裹是主要线索，但逐调用m/n/k/stride/flags、外层准备与实际ctypes调用边界仍未知；先补这个关键定位，不提交无明显搬运节省的view微改。
- R11安排：原未改baseline/同1600工程统计帧/seed0/B64前320训练帧，连续5更新，前2不采详细调用后3记录scalar元数据/两层边界时间；不跑torch.profiler、不复制tensor。每采样原149调用，上限256条/文件1MiB，共3份。ctypes span含转换/打包/调度，非纯内核。
- 执行边界：02先接口/GEMM_READY、00新部署、01 PASS_FOR_ENGINEERING_GEMM5绑定具体SHA后00直接唯一新job，38授权36实际、24GiB同limit/exclusive、900秒（840+30+30），原first5门槛/CPU/KML/保存恢复保留，异常停止无重试。固定就绪文件免用户中转；root无SSH/新job。
- 08可选：先只读现有runtime shape/flags总次数目录，分不清训练/恢复就UNKNOWN，不推断速度；R11结果90分钟内到可整理，否则明确停点，不后台假等。
- 修改范围：仅协调新处置JSON/R11任务卡/总表和自身状态；旧三状态存history/PRE_R11_GEMM_DISPATCH_20261106/；作者源码/旧候选/原件/暂存未改。旧正式split/subject UNKNOWN、无val/test，工程暴露范围不扩。
- Git/其余：R10本地候选及低收益不选用结论、08完整归因可下批精确归档；活动R11不混入、旧257清单不改，数据权重ZIP不进Git；唯一Git窗口操作。03—07不扩。
