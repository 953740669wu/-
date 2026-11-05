# 2040233 normal：事实时间线与证据缺口

节点cn21339；以下均为2026-11-05中国时间（UTC+8）。原件保存在本轮 `evidence/received/`，完整旧失败包为 `evidence/JOB_2040233_full_evidence.zip`。机读派生表为 `evidence/timeline.json`。

原始文件时间取自S00 `COLLECTION_S00.json` 的远端 `mtime_ns`，不使用Windows副本时间。mtime只表示文件元数据，不是函数入口/结束时间。以下六位小数显示微秒，原始纳秒保留在JSON中。

| 时间/时段 | 来源与可证明事实 | 不能据此证明 |
|---|---|---|
| 17:19:03—17:20:03 | 调度原件：job2040233 RUNNING→FAILED，jobExitCode=1，末态PID字段为“-” | 不能把秒级调度时点作为worker开始或清理精确时点 |
| 17:19:04.019931—09.318931 | 身份检查进程回执exit0 | 原6项Linux检查通过，不是通信通过 |
| 17:19:10.149301—18.176581 | 原probe检查回执exit0；S00原日志记录16项通过，无跳过 | 本次Linux原检查合计22项，独立于本轮本地检查 |
| 17:19:19.055227—40.920487 | environment命令回执exit0，21.865260秒；实际CPU版torch/Gloo API可用、库SHA已记录 | 该时长包含单线程导入、元数据/库SHA采集及退出监督，不是纯Torch导入时间，也不是worker CPU36配置的耗时 |
| 17:19:41.749234 | S00 run_checks命令回执started，PID2321373 | 不是两个worker的出生时刻 |
| 17:19:42.518293 / 42.561015 | normal manifest / commands原始mtime；参数pg_timeout=5秒、deadline=30秒；两个命令的rank分别0/1，使用同一新store路径 | 不是进程组初始化开始时刻 |
| 17:19:42.523398 | rank0空日志原mtime，原监督代码先打开日志再Popen | 不是Popen返回或子进程启动时刻；该值比commands的mtime早约38ms，不能用mtime推断源码执行次序反转 |
| 无绝对时间记录 | worker PID2321423/2321424；首个主TID start_ticks为389167343/389167348，相差5个原始tick | 未采SC_CLK_TCK及启动epoch，不换算秒、不声称启动精确相差0.05秒；没有双方框架入口时间 |
| 17:19:43.100332 | rank0最后有效JSON的mtime：仅before_framework快照，主TID17个累计CPU tick，掩码0—35 | 不能证明rank0在此后永久卡于import torch、没有做库SHA，或已经/没有进入初始化；累计CPU tick不是阶段墙钟时间 |
| 无阶段时间记录 | rank1 JSON保留before_framework、init_process_group两个快照；Torch intra-op=36；后者主TID掩码[38]属于selected38—73 | 未记录框架导入结束、逐库SHA开始/结束、init实际入口时刻 |
| 17:19:57.807462 | rank1错误JSON原mtime，stage=init_process_group，error=`RuntimeError: Wait timeout` | 不是init入口；不能从此倒推精确5秒的起点 |
| 17:19:58.338736 | rank1 traceback日志原mtime，924bytes；栈由dist.init_process_group进入_new_process_group_helper，再到ProcessGroupGloo构造 | 不能只凭Wait timeout判定是网络、store、启动不同步或后端不可用 |
| 17:19:58.487698 / 58.500248 | normal summary / suite checks原mtime：reason=child_failed、exits=[-15,1]、all_reaped=true；checks=FAIL/cases=[] | 无逐次发送信号的时间回执；不能由-15认定rank0自行报错或自行超时 |
| 17:20:01.941482 | S00 run_checks外层回执finished/exit1；无timed_out标记，cleanup_actions=[]、remaining_live=[] | 不是normal监督器结束时刻；含额外Python退出/外层观察开销 |

normal监督器原始monotonic墙钟差为15.916535秒，小于30秒；它以child_failed退出，而不是deadline。没有可核的绝对supervisor开始/发TERM时间，不能把summary mtime减15.916535所得值当作实测出生时间。

## Wait timeout、before_framework与清理的关系

原worker先持久化before_framework，再验证环境，调用 `backend_info()`，其中合并了Torch及distributed导入、读取maps、逐库SHA、构建配置和模块SHA。只有这些返回并检查Torch36后，才持久化init_process_group快照并调用实际初始化。

因此rank0的旧JSON缺environment/runtime/Torch36字段，也不能证明这些步骤在内存中从未执行：中间没有落盘。它最后可证明的阶段停在before_framework之后、下一个完整落盘检查点之前；确切停点、持续时间、最终是否可自行前进均未知。rank1已进入ProcessGroupGloo构造并报Wait timeout，但未记录实际rank/world/backend初始化完成字段，也未到all_gather_identity。

“一方较早进入初始化而另一方尚未就绪”与现象相容，未被这些证据确认。进程出生tick接近不能证明框架导入完成接近；单线程environment的21.865秒也不能证明rank0的纯导入耗时或5秒配置应调整。两者尚缺共同阶段时钟。

原监督逻辑一见任一非零退出即标记child_failed，随后向本任务创建的worker进程组发TERM，宽限后KILL并wait。rank1的exit1、rank0的-15、child_failed以及S00外层无清理信号，与该内层监督清理路径一致；这属于基于执行源码和终态的归因，旧包没有实际逐signal发送事件可独立定位发送时点。不能把rank0的-15列为第二个独立Gloo超时。

## 原因判断与最小观测

| 假设 | 当前证据边界 | 下一次最小观测 |
|---|---|---|
| 启动/框架准备不同步 | 首个检查点后缺时钟；尚不能定位哪段慢，也不能确认某rank已等待另一rank | 父spawn_begin/spawned，双方worker_ready与Torch/distributed导入begin/end |
| 导入后的库SHA/元数据耗时 | backend_info包含该工作；rank0缺下一落盘阶段，无法排除 | runtime_metadata begin/end、逐库SHA begin/end |
| rendezvous/loopback/Gloo构造问题 | 同一store路径、rank1到构造；缺双方init入口/出口与实际等待区间 | 双方init begin/end（含backend/rank/world/store/5秒参数）；若双方均进入仍失败，再交原始traceback按具体位置决定额外检查 |
| rank0永久死锁或rank0自主失败 | 只有被TERM前的最后JSON和空日志，没有独立异常/栈或连续状态 | 阶段轨迹先缩窄停点；不先扩展成通用堆栈/性能监控或宣布死锁 |

结论：**根因未定，不能宣布已修复。** 本轮修订仅填补已证实的阶段/清理时间观测缺口；不增大5秒通信超时、30秒监督截止或300秒job方案，不加启动barrier，不改后端、绑定、四case判据或清理策略。失败和后三case未运行均保留。
