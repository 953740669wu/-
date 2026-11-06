# S01 S07 R7 原子rank报告与新部署专项复核

结论：**PASS_FOR_S07_R7_ATOMIC，review_complete=true，无前置阻断项。** 本审核只绑定R7固定代码与S00最终P1部署；S00在提交前再核同SHA、实际队列及新独占marker后，可直接唯一执行完整四case，无需用户中转。旧R6/2050433失败和空报告原件保持，不将此次安排视作补跑旧case。

## 原失败事实与复现边界

仅展开RUN_COMPLETE.analysis_inputs中必要crash原件，核COLLECTION_S00绑定SHA。旧rank0.json确为0bytes，checks整组FAIL且仅normal已通过，collective-timeout/watchdog仍NOT_RUN。rank1到injected_crash/exit17，父child_failed并TERM rank0，回收[-15,17]。rank0最后checkpoint_end为broadcast，worker_error到cleanup6.326138ms、到TERM8.903532ms；事实见BASELINE_FAILURE.json。源码的w覆盖会先truncate，符合后续重写受中断的机制；没有现场syscall栈，未将具体被中断write当成已证明事实。peer reset发生在故意崩溃之后，不据此宣布normal通信有同样故障。

S07先交INTERFACE_READY再交冻结ATOMIC_READY；核TIMELINE、红灯/绿灯与6组受控短进程原件。旧函数在目标流打开后零写/半写受终止，正式文件分别为空/30byte残JSON；新函数在同等零写/半写/replace前中断，旧133byte完整报告均逐字保留，损坏只在本次临时文件。无旧目标时，正式文件仍缺失，原reader继续拒绝。受控Windows terminate不冒充C2 Linux SIGTERM现场或旧syscall定位；未操作原故障PID/原报告。

## 最小修复、旧报告与严格reader

唯一运行源diff增加tempfile import和write_rank_report，替换worker checkpoint/正常完成/异常处理三处rank更新。先完整json.dumps(indent=2,allow_nan=False)+换行，再在同目录NamedTemporaryFile独占生成.rankN.json.<random>.tmp，写完/flush/fsync/关闭后os.replace；目标不会先被打开截断。序列化、write/flush/fsync/replace失败不破坏上一份已提交目标。finally只unlink本次创建的确切路径，不glob清理别人的残件；进程受TERM留下的临时文件交原件收集。

独立AST核验：删除新增writer/import并还原三处调用后，与R6整个模块AST完全相同。原write_json、readiness不可覆盖的publish_json、run_checks、CPU36、stack_observer和观察契约/旧五组测试均保持；9项就绪原封复用SHA一致。未延长父等待、清理宽限或修改Gloo/ready/注入点。原run_checks仍直接读取两个正式rankN.json，缺失/空/损坏照常拒绝；不捕获JSONDecodeError跳过、不用父事件或临时文件补正式报告。测试中对自建同步marker的短暂JSON重读只用于确定性故障注入，不在通信reader中。

正式报告只表示最后已replace的完整checkpoint；crash rank0可能仍为broadcast且无最终error，不声称worker_error处理已完成。只有第一次正式发布前被中断时没有旧报告，仍必须FAIL。该修复针对进程中断的发布原子性，未宣称断电/任意远端文件系统持久性已验证。

作者新增17方法覆盖首次发布/成功替换/原序列化一致、NaN和不可序列化、write/flush/fsync/replace异常、同目录独占与提交顺序、临时归属、旧空/半写复现、新零/半写/commit前中断、首次未提交拒绝、双rank缺/空/残拒绝及ready拒绝覆盖。原71回归合计88方法，本地87过1原Linux组清理跳过；隔离包收据相同。覆盖足够，S01未重复该套件、模型或旧5315；现场88必须本job零跳过。

## 最终部署与已关闭的具体问题

在发布READY之前，S01对草稿review_gate.expected()做最小只读复现：它错读S07_ALIGNED_STACK_R7.zip，而实际为S07_ATOMIC_REPORTS_R7.zip，导致FileNotFoundError。定位/当时源码SHA见DRAFT_FINDING.json。S00已在首次READY和任何job前改用prepare.ARCHIVE，补实际内包解析回归并重新打包、在新P1根重核；旧草稿保留。最终review_gate SHA=8abb04c3f2ed6a615e7bd69a5c85bdecd630038052a9529a767fe7801df7e131。S01从自身冻结副本调用实际expected(最终部署)和validate(本审核)，12绑定及resources/workload全部一致；未用额外别名ZIP绕过。此问题已关闭，不是当前阻断，也没有发生作业重试。

最终root为/home/share/dengqingtian/opt/stage4_sessions/S00/S07_ATOMIC_R7_20261106T073004Z_P1。新内包17成员/16文件/15 delivery、外包35成员/34文件/32源索引逐字核验、CRC/LF/Python3.9 AST齐全；7个R6原封helper核相同SHA。S00最终本地15/15、Linux登录15/15包装/收集检查通过，包括真实包名解析、缺空/半份正式报告旁即使有合法temp仍不补正、原ready残件保持、空/部分/未清PID原件收集。它们不替代计算job内88项，也未导入真实Torch/Gloo。

## 资源、共享截止和失败停止

同节点2个完整NUMA域各38分配/36实际留2，总76/72/4；DDR请求和limit为总24576MB、exclusive/HBM0，非每rank各24GiB。原生CCS_JOB_ID/host/affinity→nonce/request→登录实时djob raw/ready与30秒新鲜度授权保持，CPU拓扑/各rank全部TID selected36边界与实际Torch intra-op36检查保持，不能从旧JSON伪造job/PID/CPU。env-i明确转发审核SHA及原生job，无优化Python/外来KML preload。

新增17+原71=88检查（17/27/16/6/6/16）与环境、原normal→crash→collective-timeout→watchdog各一次、全部观测共享从consumer导入前START起270秒。逐步limit只会收紧全链剩余预算；所有逐步与最终cleanup最晚START+285，原TERM2/KILL10在15秒cap内，留15秒到job300，不能按helper/阶段另开时间。冻结worker原case从spawn前起30秒、pg5、TERM顺序/2秒宽限不变；新报告发布不成为延长等待的理由。

submit_once在具体审核/源核验后独占x创建新marker，一次dsub；提交前S00再查实时队列/系列记录，模糊提交只查原job，不重提。原四case判据保持：crash仍须rank1注入/exit17，collective-timeout须真实Gloo broadcast超时，watchdog仍须code124/deadline且双方injected_hang。任何检查、源/CPU/库或通信失败立即停后续；预算不足INCOMPLETE，不补剩余case、不拼旧三过、不换包/改超时/重试或扩资源。旧2050433仍是原FAIL。

## 清理、临时残件与验收层级

原subreaper/PID-start_ticks/跨session所属后代清理包含两worker及observer helper；信号前核身份、逐步和最终保存remaining/reaped，不触其它任务PID。R6 deadline−5一次Python取栈、两rank共享随后2秒proc窗口及取消/FD机制逐字不变，无新增helper等待或采样。

collect_evidence完整索引隐藏.rank[01].json.*.tmp、正式报告及checkpoint/事件、ready/store/残件、所有栈/proc/helper和调度/退出/资源/清理，记录path/bytes/SHA/远端mtime/changed_during_read。新增rank_report_inventory分列最后已发布checkpoint、worker_error和parent TERM/reap及raw残件，从不temp-to-formal恢复；readiness inventory只将原participants/ready临时文件按原规则判断，rank临时文件单独保留。空/权限/MISSED/截断或未清PID仍如实标识，不补造PASS。

诊断完整度、报告可读性与原通信判据分别保留。ARMED不等于栈已写，helper EXITED不等于proc齐；若初始化没卡住而timer合法取消，保存原状态，不能造非空栈。即使整组小张量通过也不表示同步模型训练、性能或科学接受。

## 精确绑定与实际停点

146份必要冻结输入最终无漂移，包括旧crash窄范围证据、新代码/受控复现/检查与最终P1部署；全部路径/bytes/SHA见FROZEN_INPUTS.json，专项结果见code_review.json、deployment_review.json。S01本轮0提交/0远端/0Torch-Gloo或模型运行；未现场触发R7信号故障清理，实际Linux88/CPU/TID/四case/栈proc与终态仍待唯一job。R12保持原基线无收益结案，不再tile或A/B。

| 执行绑定 | SHA256 |
|---|---|
| inner_package_sha256 | 57a1f4c530ce2c9a5edcfe9cc9741129fb1ba4f90459fde459803103a362382d |
| inner_manifest_sha256 | f9441fe47988dbb8a47365f230f2f0eb54ed59779e43fbab0d68562a19855196 |
| observer_sha256 | 5b3ad54e675a293e3eb51d292b149c6939bbdc52b68322f340eb76be3b02b875 |
| reader_sha256 | 7b7cc96edd9401981a61db5122bf785e3e2348a41cda5363ba5d2ea4b0217d07 |
| cpu_contract_sha256 | 3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d |
| atomic_tests_sha256 | 9ab4e1b49ce3a2a93ca59614753ee70d6de71c0c6cbd831ca311a495dcdd0e7f |
| interface_ready_sha256 | d0f0fc25e226066803f1290696436afbfebc3ba81e945fa567cc4e9f0c62cbba |
| comm_probe_sha256 | 42424581db02b15ee8af0c65f85553dff61767979d9644b40fe954f779434608 |
| observation_contract_sha256 | 448cad1a857165c74d0cb241e32b18480d1495ec995704f9f6c5de2208712dde |
| deployment_package_sha256 | 963ad618d09c998764342f446207d07ee29fcb95818386503ffea6e232de42e4 |
| deployment_source_manifest_sha256 | e7511b33e39f459bce6e0e56627bcce31d7db610a0f9ec00f0b4ab973915dd1e |
| task_card_sha256 | a2bdce7fad12bc8ef8e0de985c6a25dc3316bf63009568138d58c2100bccf28e |

固定S01_REVIEW.json发布后不热改。仅写S01本新目录及自身SESSION_STATUS.md/六行ROUND_DELTA.md；精确可归档清单见ARCHIVE_FILES.json，排除ZIP/frozen重复副本/数据/权重/环境。未操作共享Git暂存/提交/推送。S00直接读审核、核同SHA/实际队列/新marker后唯一执行并跟踪终态；S01本轮复核完成，不后台监控。
