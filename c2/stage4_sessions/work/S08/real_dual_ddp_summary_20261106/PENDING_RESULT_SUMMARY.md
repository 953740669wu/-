# 双域DDP结果槽位：尚无真实运行结果

这是一份准备模板，不是实际训练摘要。真实job ID、执行阶段和计数均未收到；不能以本文件的计划值声明已执行。只有绑定00的实际analysis_inputs并核SHA后才发布DDP_SUMMARY。

| 观察项 | 本卡完成时的计划/上限 | 当前实际 |
| --- | --- | --- |
| 新job/节点/两rank PID | 唯一job、同节点两个真实NUMA域 | UNKNOWN |
| 批量 | 各32、全局64 | NOT_RUN_NO_RESULT_RECEIVED |
| 全局完整更新 | 25 | UNKNOWN |
| 两rank optimizer物理更新 | 各25，合计50 | UNKNOWN；不由全局标签反推 |
| 完整B64参考更新 | 5 | UNKNOWN |
| 物理更新总预算 | 最多55 | UNKNOWN；须含失败更新/可能已执行范围 |
| 独特训练帧 | 1600 | UNKNOWN |
| 参考额外观察 | 首5批最多320次，不算新增训练吞吐 | UNKNOWN |
| 统计加载/探针/中断可能曝光 | 按两rank及参考原账本分项 | UNKNOWN |
| 第一批至第五批原比较器 | 原覆盖/阈值全部保持 | NOT_RUN_NO_RESULT_RECEIVED |
| 第6—25更新 | 前5全部通过后同状态继续 | NOT_RUN_NO_RESULT_RECEIVED |
| 逐步参数/AdamW同步 | 两rank原名张量字节hash核验 | NOT_RUN_NO_RESULT_RECEIVED |
| 保存/恢复 | 零额外更新；原Encoder/AdamW/RNG/mask RNG/游标身份 | NOT_RUN_NO_RESULT_RECEIVED |
| 终态/所属PID清理 | 00原调度/退出/清理证据 | UNKNOWN |
| 同job单域对照 | 本卡不安排 | NOT_MEASURED |
| 提速/扩展效率/稳态收益 | 本卡不具备对照 | NOT_MEASURED |

如失败，先记录最后完成阶段和原失败项。全局已确认完成步、各rank实际optimizer调用、参考调用、失败后可能已更新但未提交的状态必须分开；`completed_updates=0`不自动证明optimizer从未执行。后续没执行的阶段NOT_RUN，不填0耗时，不把缺失worker记录补成另一rank结果。

时间槽位：前5含参考训练/比较、后20纯DDP观测阶段、每rank训练调用/同步/等待、最慢rank、参考诊断/其它诊断、程序wall、调度节点秒分别填写。无必要时间分解则UNKNOWN，不用推算补齐。单域历史值不得参与提速计算。

内存槽位：各rank/阶段的RSS采样与process-lifetime HWM、参考共存与释放后的采样各自记录。释放后HWM可能继承早期参考峰值，不能直接称训练自身峰值；不将两进程高水位相加冒充同一时刻总驻留。

独立状态槽位：工程训练链路、原五步数值门槛、跨rank同步、恢复、清理和科学/性能接受分别报告。原R7固定张量/故障通过、进程exit0、checkpoint路径存在均不替代本轮这些检查。
