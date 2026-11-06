# 首次真实双域DDP：S08结果核对准备

状态仅为准备；尚无实际训练结论。输入/结果字段以S07发布的本轮接口、S00 RUN_COMPLETE.analysis_inputs和绑定原件为准，不把旧PILOT/PROFILE5/GEMM5/R12输入门禁放宽为DDP，不自行给上游定义字段。新解析只作必要适配，优先复用已有标量统计工具；无DDP接口前不编造解析结果或真实夹具。

固定交接路径及90分钟截止见WORK_STARTED.json。只读查READY文件；接口稳定后核path/bytes/SHA、协议/本卡/data/config/source与引用的02参考版本，记录精确结果来源。结果未到时只称准备完成；必要人工夹具显式LOCAL_FIXTURE，不作为C2实测。S08不SSH、不提交job、不下载或读取NPZ/权重，不写其它窗口目录或共享Git。

待核内容与报告口径：

| 项 | 核对规则 | 缺失/失败时 |
| --- | --- | --- |
| job/代码身份 | 新job、原子两rank报告、同源/数据/契约/库；绑定00分析根和具体文件SHA | 保留缺/空/旧/残报告，不凭exit0报通过 |
| 有效批量 | 每域32、全局64，原完整Encoder及heads、fp32/CKPT0/KML/native SDPA | 不用标签代替实际分片证据 |
| 更新计数 | 完成时全局25、两rank各25物理更新合计50、B64参考5，物理总上限55；分别读取实际计数 | 不由某个rank计数推算全局完成；不补齐失败rank |
| 早停 | 前5任一原门槛失败必须停止；6—25、保存/恢复及未到阶段按实记NOT_RUN | 已执行/可能执行更新和已确认同步更新分列，不把NOT_RUN写为PASS或0耗时 |
| 帧与曝光 | 原16unit/1600独特训练帧；每全局批前32/后32按原序分片，并集64无交集/重复/补齐；B64参考额外320次观察单列 | 两rank/参考的selected、load、attempt、consumed、unknown按原记录保留；额外参考帧不算新吞吐样本 |
| RNG/mask | 原seed0初始权重及模型初始化后的mask流；全局mask/原参考/两分片记录一致，构造/恢复不扰动 | 不从相同seed推断实际mask相同 |
| loss与数值门槛 | 全局两个平方误差sum/各自全局元素数；DDP平均系数/输入梯度缩放按原契约；原完整B64五步比较全部覆盖 | 原compare阈值不改，逐项保留失败，不用只看总loss替代 |
| 同步 | 逐步两rank原名参数/AdamW张量hash、step/cursor一致；有限梯度与实际PG/DDP记录 | 不比含rank元数据的checkpoint整文件SHA来判状态是否相同 |
| CPU/库 | 各真实域selected36、总76分配72实际4预留；真实job/TID与库调用，线程非空mask属于对应域 | 进程数/线程数不等于核数；不把历史通信探针通过当训练通过 |
| 终态/清理 | 两rank/parent、原退出/调度/PID清理与01本轮实际复核 | 诊断收齐、退出成功、训练门槛通过、科学接受分列 |
| 恢复 | 保存Encoder/AdamW/各rank与独立mask RNG/cursor/source身份，零额外更新核验 | 仅转述实际检查项，未核项目未知；不读取权重补验 |

耗时单列前5步（含完整B64参考/比较）与后20步，读取训练调用内同步/等待、最慢rank、诊断/壁钟和各域RSS/HWM的实际记录。两rank并行区间不能相加冒充wall；不同阶段/角色中位数不相加。参考共存阶段的process-lifetime HWM与参考释放后的采样分列：后段HWM仍可能包含早期峰值，不能称纯DDP训练峰值。缺分解字段记UNKNOWN，不补估。

本轮没有同job、同负载的单域25步对照。speedup/scaling_efficiency/steady_state_gain固定为NOT_MEASURED；不引用旧节点秒数推导提速，不把两个独立进程吞吐相加当同步训练吞吐。仅在确实完成指定更新和门槛后报告工程训练完成；无正式subject/split/val/test，不作泛化/科学或生产接受。

预定输出：DDP_SUMMARY.md/JSON、输入SHA核对、必要方法/验证、SUMMARY_READY及精确ARCHIVE_FILES。仅在收到实际RUN_COMPLETE并完成核对后绑定真实结果；若依赖等待上限到达，记录缺文件、活动job的已知范围和明确续接动作，结束会话，不声称后台监视。
