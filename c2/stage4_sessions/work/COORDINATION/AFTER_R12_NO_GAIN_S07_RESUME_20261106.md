# R12无训练收益结案；恢复S07多域通信阻塞定位

2026-11-06，Asia/Shanghai。依据用户要求核是否提速并安排下一步：保留原fp32基线，结束固定分块路线，下一轮资源转到多域训练所需的通信前置。只读短状态优先，验收或新部署时再展开必要证据。

## R12结论（已核原始测时）

- 唯一2049894/cn21338成功/exit0，实际target→两侧strict5→两独立perf25，最多60完整更新全部完成，无重试/缩步，进程清理完成。实际target输出、strict3895项比较、两侧perf首次5步各15项原loss比较均差0。
- 两侧同节点/同job/库/环境/数据/init/frame/mask一致，均完整25步，前5预热、后20观察。训练调用中位baseline4.5102391038秒、candidate4.6280611481秒，候选本次中位增加2.6123237%；范围4.320208—4.618458与4.481312—4.926456秒。
- 原25步训练合计113.435457/117.833010秒，程序wall167.404845/170.552771秒；同范围采样process-lifetime HWM最大6820.117/6923.133MiB，不能称单步独占或全job最终峰值。当前没有训练收益或内存下降证据。
- 这是单对探索，无需把2.61%推广为所有运行稳定回退；但没有依据集成该候选。协调处置R12_CLOSED_NO_TRAINING_GAIN：保留候选、通过和无收益原件，不默认集成、不换块宽/精度、不追加A/B或回滚原基线。
- 协调独立核5主绑定/全部阶段原件、3895比较、完整60更新、139 CPU快照、同机初始化/源/帧mask/计数/双恢复、原始后20步统计，均一致；记录JOB2049894_R12_NO_GAIN_REVIEW_20261106.json。无SSH/新模型运行/权重读取。

## 下一主线：S07 R6有限通信诊断

单域真实训练已跑通；两个局部候选尚无可接受加速。多域同步训练仍受S07 watchdog初始化阻塞。恢复已有R6取栈包，目的是取得具体停点并推进通信适配，不宣称此次就得到多域训练加速，不把独立进程吞吐当同步训练吞吐。

- 固定原包work/S07/round6_aligned_stack_20261105/package/S07_ALIGNED_STACK_R6.zip，43727bytes，SHA=32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1；16成员/15文件/14 delivery。协调核delivery/manifest原字节及CRC/3.9 AST无漂移，未重复原本地71项；见S07_R6_RESUME_METADATA_REVIEW_20261106.json。作者本地70过1 Linux跳过，实际C2新包未执行。
- 新的唯一诊断作业：同节点两个完整NUMA域，每域38分配/实际36留2，总76分配/实际72/预留4，DDR请求/limit总24576MB（不是每rank各24GiB）、exclusive、HBM0、job300秒/consumer270秒，全部前置/检查/四case/观测/清理共享原预算，不能叠加helper或新测试的时间。
- 原case顺序normal/crash/collective-timeout/watchdog，同一job各一次；pg_timeout5秒、case从原spawn前起30秒、ready/注入点/原四case判据保持。不单跑watchdog后拼旧三项，不延长case，不扩大CPU，不重试或修源码后在同一卡中再提job。
- 新Linux检查总数71，必须无跳过；新增27 observer检查与旧四组16/6/6/16都在同一consumer预算。准备/本地检查通过不是通信接受；现场失败保留具体阶段，后续停止。
- watchdog在原deadline-5秒一次dump，repeat=False/exit=False，目标+2秒为两个rank共用proc窗口；worker原TERM顺序和原清理宽限保持。helper必须属于本job/父/独立session/start_ticks/授权CPU，不能追踪其它PID或安装/提权取栈。
- 诊断完整度与通信判据分开：ARMED不等于栈已写，进程EXITED不等于proc字段齐，若未到injected_hang则整组仍FAIL；权限/空文件/MISSED/超时/部分写入如实保留，不补造或改判。即使全部通信通过也不是实际同步模型训练或性能验收。
- **本卡是新的有限S07执行安排**：01对R6代码/00新部署/资源给具体SHA绑定最终PASS后00可直接唯一执行，无需用户中转。旧2041919失败、R6发布时未授权字段及R12原件都不改，旧job/marker不复用；root无SSH/提交。

## S00：新R6部署、同SHA放行后唯一诊断

**本轮目标**：使用已冻结S07 R6内包，准备新部署并交01审核；通过后唯一运行、收齐现场停点/原四case与清理证据。

**参考文件**：自己的最新短状态；本卡；S07/round6_aligned_stack_20261105/{SOURCE_MANIFEST.json,INTERFACE_FOR_S00.md,OBSERVATION_CONTRACT.md,package}；原s07_wrapper_r5_ready_20261105及已核原生job/CPU/后代清理仅只读参考。

**完成标准**：

1. 只写S00/s07_r6_resume_20261106/及自身状态，远端新S07_STACK_R6_<唯一时间>。先核实际队列/原目录/marker/提交记录，无重复才继续，不操作其它任务。R12和原25步/采样权重全部留存，不再训练或提交R12。
2. 精确适配R6的15实际payload文件/14 delivery、71测试和stack_observer新源码身份、helper所属独立session/清理；原R5外包不覆盖，不沿用旧bytes/SHA/文件数/旧44项检查。CPU授权/原生CCS_JOB_ID/nonce/raw/request/ready仍真实生成，不从JSON伪造身份。
3. 新S00_DEPLOYMENT_READY.json锚定R6内包/manifest/observer、外包/索引/命令、资源/工作量/停止条件及必要LF/bash-n/源SHA/包装层检查。所有前置与270秒consumer/300秒job共用截止，清理和收尾必须在300内；不把新27检查额外加在预算外。登录节点不运行真实Gloo。
4. 等S01/s07_r6_resume_review_20261106/S01_REVIEW.json明确PASS_FOR_S07_R6_DIAGNOSTIC、review_complete=true并绑定全部SHA/76-72核/24GiB总量/预算/原判据。提交前再核同SHA/实际队列/唯一marker，才一次dsub。审核或身份不一致则停，不修成另一个包后自行重试。
5. Linux71/环境通过才依原四case顺序一次执行；源/CPU/库、通信或观测失败均保留原字段，不把清理成功等同注入通过。跟踪本job终态/所属PID，未完成或残留如实报，不继续占节点等待后续任务。
6. 原样收两rank的python_stack.txt、stack_status.json、installed_python.json、proc_identity/fields/summary/helper.log、父helper PID/kill/returncode/reaped，以及原events/summary/participants/ready/store/全部残件/调度/退出/资源/清理；索引path/bytes/SHA/远端mtime，缺空/权限/截断明确列出，不补PASS。发布RUN_COMPLETE或终态失败交接，供S07后续定向分析。
7. 更新短状态、六行摘要及精确归档清单。依赖可每30—60秒只读查固定文件，累计等候最多90分钟，不占节点空等或安装常驻服务；排队超60分钟未启动可取消自己本轮排队job、不重提。断线恢复先查原job，不额外提交。

## S01：R6新观测/新部署专项复核

**本轮目标**：核已有R6取栈/进程观测和00新包装的具体执行边界，绑定SHA给一次有限诊断放行结论。

**参考文件**：自己的最新短状态；本卡；S07 R6 minimal.diff、candidate/comm_probe.py/stack_observer.py、OBSERVATION_CONTRACT/INTERFACE、作者检查原件；00新S00_DEPLOYMENT_READY。只按变更需要读原R5，不重做无关R12数值或原旧审核。

**完成标准**：

1. 只写S01/s07_r6_resume_review_20261106/及自身状态；核deadline-5一次计时的绑定/取消先于关闭/FD保留，MISSED不重置；proc helper的原生job/父/session/start_ticks/CPU边界、两rank共用2秒窗口、父不无界wait与原cleanup时序。原case判据/ready/注入点不变。
2. 核00新15文件/14 delivery/71 Linux检查、76授权72实际/4预留/DDR总24GiB、300秒全链及270 consumer共享、helper后代覆盖与新原件收集；权限或采样不完整不能被后处理改成成功，未触发的真实故障清理仍不声称已测。
3. 作者本地70过1跳过仅用于覆盖判断；现场Linux71仍须本job执行，不能用Windows替代。具体疑点才补最小独立检查，不重复模型/旧5315。发现问题给定位，不代改作者源/改超时或门槛。
4. 固定S01_REVIEW.json写PASS_FOR_S07_R6_DIAGNOSTIC或FAIL/BLOCKED，review_complete及内包/manifest/observer/外包/索引/本卡/资源/工作量与判据精确绑定；PASS后00直接唯一执行，不等用户中转。保持旧冻结审核，结束更新短状态/摘要/归档范围。

## S02：R12无收益结案（不重跑）

**本轮目标**：将实际数值通过但本次训练无收益的结论落入自己的短交接，结束该固定候选。

**参考文件**：自己的短状态；本卡；S00/round12_dw_ab_20261106/RUN_COMPLETE.json及绑定perf/strict原件；协调JOB2049894_R12_NO_GAIN_REVIEW_20261106.json。

**完成标准**：只写自己的新closeout记录/状态，不改原R12_READY/候选/阈值或生产默认。记录target/3895 strict/各15比较通过、同机25步完整、本次后20步慢2.6123%，标CLOSED_NO_TRAINING_GAIN、非数值FAIL、不集成/不换tile/不再提job；若引用数据不一致就指出，不重训。更新六行摘要及精确待归档清单后待命。

## S08：真实A/B摘要与失败/无收益边界

**本轮目标**：只读整理唯一R12实际对照结果，供归档和后续比较；不产生新实验。

**参考文件**：自己的短状态；本卡；S00 R12 RUN_COMPLETE及全部阶段result/steps/原审计；协调JOB2049894_R12_NO_GAIN_REVIEW_20261106.json。

**完成标准**：在S08新ab_r12_2049894_20261106/核绑定/同机角色/25步与warm5-observe20、计数/数值/恢复后，输出简短AB_SUMMARY.md/JSON，复算4.510239/4.628061秒及+2.6123%、全部25步/分项wall/同范围采样HWM；保留范围重叠和单对限制，不称稳定回退或科学/生产接受。原件/权重不读写，不重跑原套件；新解析仅针对必要逻辑做最小检查。更新短状态/六行摘要/归档范围后待命。

## 其余与Git

S07原窗口暂保留冻结包，无需先改代码或重复旧本地检查；新R6现场结果返回后再把栈/时间线交原S07分析。03/04/05/06不扩。已核R12通过/无收益原件、08已完成摘要及后续结案可下一批精确Git归档，活动S07新部署不混入、旧257清单不改，唯一Git窗口操作；数据/权重/ZIP/环境不入Git。
