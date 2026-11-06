# R6失败后：修复rank报告发布，再做一次完整有界通信诊断

2026-11-06，Asia/Shanghai。00/01执行与前置审核、02 R12结案、08实际A/B摘要均已结束；完成交付不等于S07通信通过。只按短状态调度，针对新失败核必要原件和写入代码。

## 已核停点与证据边界

- 唯一2050433/cn21338 FAILED/exit1，71 Linux检查零跳过及环境通过；normal固定张量通信通过。crash rank1到injected_crash并exit17，父child_failed并TERM rank0，双方回收/exit[-15,17]，但rank0.json=0bytes，原检查器JSON读取失败，整组FAIL。
- collective-timeout/watchdog及R6取栈均NOT_RUN，diagnostic_task_complete=false；不能补跑剩余两项、拼旧三过，不能把crash注入/清理已发生等同该case已经通过原检查。23份现存CPU快照可核，缺失rank0序列化证据不补造。
- 协调核RUN_COMPLETE的10个顶层绑定bytes/SHA、01绑定、原空文件SHA、crash注入/父清理/原checks、未执行项目及终态，均一致；JOB2050433_CRASH_REPORT_REVIEW_20261106.json记录原件与时间差。无SSH/新job/重跑模型。
- 原rank0最后checkpoint_end为broadcast；随后worker_error（peer reset）后6.326ms父cleanup，8.904ms发TERM。R6 checkpoint/正常结束/错误处理均用直接Path.write_text覆盖同一个rank JSON，原函数会先truncate。此前写入已完成而最终0bytes，与后续重写被TERM打断机制一致；**没有现场系统调用栈，尚不能断言精确被中断的那次write/syscall**。
- peer reset出现在故意rank1崩溃之后，不能据此另宣布正常通信有同样故障。原watchdog初始化阻塞尚未重新到达，不称已定位/修复。

## 公共修复范围与新有限执行

- 只做rank报告发布的最小修复：同目录独占临时文件→完整序列化/写入/flush及必要fsync→原子replace目标。正常更新成功后内容/字段/allow_nan=False语义保持；中断前目标仍是上一份完整已提交checkpoint，不能先截断旧目标。首次发布前中断且没有旧目标，仍应被原检查拒绝。
- 优先只改worker rank报告的3条更新路径及一个小函数；原readiness的拒绝覆盖/唯一发布语义保持，不把不可覆盖ready发布函数改成可覆盖。不顺便修改Gloo、等待、CPU、模型、时间预算、故障注入/原四case判据或run_checks解析门槛。
- 禁止通过跳过空JSON、把缺报告当PASS、用内存/父事件伪造rank报告、放宽两个rank完整性来“修好”。临时文件只属于本rank/本任务；异常清理仅处理自身临时路径，SIGTERM后残件原样收集，不把.tmp当正式rank.json读取。
- R6 frozen源/包/旧失败保持，R7在新目录新包；原run_checks.py/cpu36_contract.py/stack_observer.py原则上逐字节不变。若定向复现与上述机制不符，报告实际根因/最小方案，不能为符合预设而改证据或热改其它模块。
- **新的唯一R7条件执行安排**：07新固定包完成必要检查、00新部署、01绑定具体SHA最终PASS后，00可直接一次完整四case，免用户中转。不是重试旧2050433或单补后两项；root当前无SSH或新提交。
- 资源/判据保持：同节点2域各38分配/实际36留2，总76/72/4、DDR总24576MB同limit/exclusive/HBM0、job300/consumer270，所有前置/新旧Linux检查/四case/观测/清理共享原预算。pg5/case30/原ready/注入点/原TERM与清理时序不变；不等rank0写完再延长宽限。
- 原normal→crash→collective-timeout→watchdog同一job各一次；旧71方法+新实际方法数由07清单明确，Linux必须全过零skip且共享原270预算。失败即停，无自动重试/改判/扩预算/换包重提。观察完整度与通信判据分开，合法取消/未取到栈不伪称捕获成功。

## S07：受控复现与R7最小原子发布修复

**本轮目标**：依据2050433原件重建报告重写/TERM时序，受控复现旧写入模式会破坏旧报告，最小修复并交新R7包。

**参考文件**：自己的最新短状态/ROUND_DELTA；本卡；S00/s07_r6_resume_20261106/RUN_COMPLETE.json及analysis_inputs明确的crash/rank0.events、rank1.events、supervisor.events、原空rank0.json/checks/summary；R6 candidate/comm_probe.py、run_checks.py和原SOURCE_MANIFEST；协调JOB2050433_CRASH_REPORT_REVIEW_20261106.json。

**完成标准**：

1. 只写S07/round7_atomic_reports_20261106/及自身状态；R6/2050433原件不改。先核相关源/输入SHA，出简短TIMELINE，区分现场事实、源码支持的机制与受控复现。不要声称旧源码行号处的系统调用已被现场证明。
2. 先写确定性复现检查，再修小函数/3个rank写入点。测试临时文件在本任务目录；用自己创建的短进程/故障注入模拟“旧报告已存在、下一次写入中断”，不得故意破坏原rank0.json或操作其它PID。旧模式能暴露空/残报告，新模式同一故障点下旧报告仍完整；无需Torch/Gloo/新依赖。
3. 必要检查覆盖正常首次发布/替换、序列化失败、写/flush/replace异常与保留旧目标、子进程在commit前被终止、无旧目标的未提交发布仍拒绝、临时文件归属/残件、读方原有missing/empty/partial拒绝不变。新成功文件字段/值与原序列化一致，报告只是最后已提交checkpoint，不冒充错误处理最终完成。
4. 原四case/pg5/case30/清理宽限/reader判据和R6观察器保持；新源/最小diff、原封复用SHA、实际新旧方法计数与平台skip边界写进SOURCE_MANIFEST/INTERFACE_FOR_S00。先交INTERFACE_READY.json说明文件数/检查计数及收集临时残件，后交ATOMIC_READY.json绑定R7包/bytes/SHA/来源/契约/命令/测试。
5. 本地补必要检查，不重复模型/旧5315或宣称Windows能证明Linux实际故障处理；原71回归保持，新Linux完整检查将在唯一新job验证。发布后包冻结，S07不直接提交job、不继续改watchdog根因或扩大其它写入系统。更新短状态/六行摘要及精确归档清单。

## S00：按新R7计数部署；最终同SHA后唯一整组

**本轮目标**：R7接口先到时准备新部署，01最终审核通过后直接一次完整四case并收原报告/临时残件/诊断。

**参考文件**：自己的最新状态；本卡；07新INTERFACE_READY/ATOMIC_READY与R7具体包；旧s07_r6_resume_20261106部署和终态原件只读参考；01本轮固定审核。

**完成标准**：

- 只写S00/s07_r7_atomic_20261106/及状态，远端新S07_ATOMIC_R7_<唯一时间>；先实际队列/所有本系列marker/提交记录去重，无旧job复用。旧R6、rank0空文件/残件和历史失败全部保留。
- 依R7实际清单适配内外包/文件数/方法数、新comm源码身份及临时残件收集，旧reader/observer/CPU判据不变。源/LF/bash-n/元数据/必要包装检查后发布S00_DEPLOYMENT_READY.json，绑定07代码/manifest/实际测试数、外包/索引、资源/工作量/原判据/停止与清理。
- 等S01/s07_r7_atomic_review_20261106/S01_REVIEW.json明确PASS_FOR_S07_R7_ATOMIC、review_complete=true且所有SHA/预算一致；提交前再核同SHA/队列/独占唯一marker，才一次dsub。原300秒job/270执行包括新旧检查和所有观测，cleanup/收尾在300内，不延长case或等旧rank补报告。
- Linux全套零skip/环境通过才按normal/crash/collective-timeout/watchdog各一次；空/残/缺正式报告仍失败。临时文件不纳入rank正式读方；按原始残件收路径/bytes/SHA/mtime，记录crash前后最后已发布checkpoint及parent TERM/回收证据。
- 终态收齐原checks/4case已运行或NOT_RUN、两个rank报告/事件/ready/store、所有栈/proc/helper原件/缺项、源码/CPU/库/授权/调度/退出/清理；若初始化未卡住或定时被合法取消，报告原状态而不补造非空栈。发布RUN_COMPLETE或失败交接，失败不补case/不重试。更新短状态/六行摘要/归档清单。

## S01：原子发布语义与新部署专项复核

**本轮目标**：先核07最小修复没有降低故障检查，再核00新R7部署，给唯一整组执行的版本绑定结论。

**参考文件**：自己的最新短状态；本卡；S07 R7 TIMELINE/diff/ATOMIC_READY/必要测试原件；S00新S00_DEPLOYMENT_READY；原2050433故障证据和原reader仅按需要展开。

**完成标准**：

- 只写S01/s07_r7_atomic_review_20261106/及状态；核同目录独占临时文件/先写完再replace、异常不破坏最后已提交文件、自身临时文件归属、worker checkpoint/正常/错误三个更新点都覆盖。原readiness不可覆盖、原reader missing/empty/partial拒绝/双rank/四case/时间清理不变。
- 测试覆盖足够则核原件，具体疑点才补最小独立正负例；不能把有旧checkpoint下安全提交推成无旧目标也可接受，不能靠延长父等待或捕获JSONDecodeError跳过来通过。旧R6原件与worker错误因果假设要分明。
- 接00部署后核新实际文件/检查数、76/72/4核/DDR总24GiB/300-270共享、helper所有权/原清理及临时残件/新源/原判据收集。Linux零skip留给唯一现场job，不把本地纯标准库测试叫实际Gloo通过。
- 固定S01_REVIEW.json写PASS_FOR_S07_R7_ATOMIC或FAIL/BLOCKED，review_complete与R7包/manifest/comm/原封reader-observer-CPU/测试/外包索引/本卡/资源/工作量的具体SHA绑定；通过后00直接一次，不需用户中转。发现问题给定位，不代改冻结源/门槛。结束更新短状态/摘要/归档范围。

## 等待与其它任务

07先接口后代码、00可先准备外包、01可先审新代码，固定READY直接衔接；依赖每30—60秒只读查，累计最多90分钟，不占节点空等/不装后台服务，超时留停点。唯一提交后00跟踪原job，排队超60分钟尚未启动可取消本次自己的排队job但不重提，断线恢复先查原job/marker。

02的R12关闭结案与08的真实A/B摘要均完成，待命/精确归档，不重训、不再tile或精度搜索。03/04/05/06不扩。R6失败与空JSON原件、R7复现/修复及审核必须分别留存；活动新包不混进旧Git范围，唯一Git窗口操作，数据/权重/ZIP/环境不入Git。正常通信通过不等于整组/多域模型训练或性能已接受。
