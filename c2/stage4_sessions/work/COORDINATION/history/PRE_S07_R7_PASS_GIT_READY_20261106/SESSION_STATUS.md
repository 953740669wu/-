# 总协调简短状态

- 更新/轮次：2026-11-06；S07_R6_FAILURE_R7_ATOMIC_DISPATCH，07/00/01新任务待用户转发，非新job已提交。
- 本轮依据：先读00/01/02/08短状态及07旧停点；02 R12结案和08实际A-B摘要均已结束。因S07新失败，定向核RUN_COMPLETE/AUDIT/crash原件/事件与comm_probe写入/reader代码，不通读全部历史。
- R6结果：唯一2050433/cn21338 FAILED/exit1，71 Linux全过零skip/环境过、normal固定通信过；crash rank1注入exit17、父child_failed/TERM rank0并回收[-15,17]，但rank0.json=0bytes使原checks JSONDecodeError。新增105节点秒/usage104，无重试，原件终态无活动S00 job。
- 未完成范围：collective-timeout/watchdog及Python/proc取栈NOT_RUN，整组FAIL，诊断任务未完成；不补剩余case或拼旧三过。现存23 CPU快照可核，rank0缺的序列化数据不能补造，故障清理与通信接受分开。
- 独立核验：10顶层绑定bytes/SHA、最终01审核8绑定、空文件e3b0…SHA、原checks/注入/清理/终态一致；JOB2050433_CRASH_REPORT_REVIEW_20261106.json。无SSH/新job/重跑71或模型。
- 时序/机制：rank0广播checkpoint_end先完成，随后worker_error peer reset后6.326ms父cleanup、8.904ms发TERM。三个rank报告更新点均直接Path.write_text truncate旧目标；与重写中断留下空文件一致，精确被中断syscall未捕获，不将假设当现场证明。
- 新07任务：R7独立目录先受控复现、最小同目录临时写完+flush/fsync+atomic replace，保留最后已提交checkpoint；新临时文件只归自身，缺/空/残的正式报告仍由原reader拒绝。readiness不可覆盖/四case/CPU/时间/故障/原观察器不改。
- 新执行安排：S07_R7_ATOMIC_REPORT_NEXT_20261106.md；07先INTERFACE_READY再ATOMIC_READY，00新部署、01 PASS_FOR_S07_R7_ATOMIC绑定具体SHA后00唯一新整组。仍2域76分配72实际/4预留、DDR总24GiB同limit/exclusive，job300/consumer270，新旧Linux全套零skip、原pg5/case30与清理宽限不变；异常停止无重试。
- 02/08完成：R12 CLOSED_NO_TRAINING_GAIN，完整数值过但本次后20步慢2.6123%，原基线保持；02结案和08摘要按新短摘要采信用于调度，无矛盾不重做R12数值/统计。均待命，不再tile搜索/训练。
- 修改范围：仅协调新失败核对JSON/R7任务卡/总表/状态/摘要；旧三状态存history/PRE_S07_R7_ATOMIC_DISPATCH_20261106/；作者源/旧R6失败/包/原件/共享暂存不改。
- Git/其余：R6失败与原空文件/事件、R12结案/摘要需精确归档；新R7在写文件另批，旧257清单不改，唯一Git窗口操作，数据权重ZIP环境不入Git。03/04/05/06不扩，正式split/subject UNKNOWN，无同步模型训练或性能接受。
