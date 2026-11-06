# S00 S07 R7原子rank报告：唯一完整四case

R7固定内包S07_ATOMIC_REPORTS_R7.zip，44414bytes，SHA57a1f4c530ce2c9a5edcfe9cc9741129fb1ba4f90459fde459803103a362382d；17成员/16文件/15 delivery，comm SHA42424581db02b15ee8af0c65f85553dff61767979d9644b40fe954f779434608。
原reader/CPU/observer与R6逐字节不变，原缺/空/损坏正式报告仍失败。临时`.rank[01].json.*.tmp`只保留原字节，不补正式文件，也不与原ready临时文件混为一类。
资源保持总76分配/两个域各36实际共72/留4，DDR总24576MB同limit/exclusive/HBM0/job300；原生前置/新增17+原71=88 Linux检查/环境/原四case及观察，共用从START起270执行截止；所有清理封顶START+285（15秒TERM2/KILL10窗口），留15收尾。每阶段或helper不能重置预算，冻结worker TERM顺序/宽限不改。

## 实际去重、原件保留与新部署

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S07_ATOMIC_R7_20261106T073004Z_P1
djob -J
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S07_ATOMIC_R7_*/*' -name submit_once.marker -print
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S07_ATOMIC_R7_*/*' -name job_id.txt -print
djob -J -l 2050433
cat /home/share/dengqingtian/opt/stage4_sessions/S00/S07_STACK_R6_20261106T062352Z/job_id.txt
# 所有R7记录为空、原R6终态才新建；已有R7尝试只监测原job，不再提交。
test ! -e "$RUN"
mkdir "$RUN"
# 上传审核用新外包及.sha256后：
cd "$RUN"
sha256sum -c S00_S07_R7_ATOMIC_DEPLOYMENT.zip.sha256
unzip -q S00_S07_R7_ATOMIC_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v
```

登录仅15项包装/收集夹具、内外包/源码SHA/LF/Python3.9 AST/Linux bash-n；不跑实际Torch/Gloo。现场必须新增atomic17→stack27→readiness16→diagnostics6→identity6→probe16共88、零skip，之后环境和normal→crash→collective-timeout→watchdog各一次。pg5/case从spawn前起30、原注入点、原观察deadline-5及两rank共用2秒保持。失败立即停，不补旧case/不重试/不延长。

## 01绑定最新SHA后直接唯一执行

S00_DEPLOYMENT_READY发布即冻结；固定S01/s07_r7_atomic_review_20261106/S01_REVIEW.json明确PASS_FOR_S07_R7_ATOMIC/review_complete=true，并完整绑定内包/manifest/新comm/原reader-observer-CPU/新测试/接口/外包及索引/本卡全部12 SHA，resources/workload逐项一致。将审核原字节上传RUN，提交前再核全部SHA/实际队列/唯一marker。

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

程序独占x创建新marker，再唯一调用（仅展示，不再手动执行）：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=76,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=2,distribution=pack]' -T 300 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_s07_diag_job.sh" '<本轮01原件SHA>'
```

真实CCS_JOB_ID/host/affinity生成nonce/request；原login djob raw/ready交接，新鲜30秒、逐CPU sysfs/两域receipt不改。subreaper/PID-start_ticks所有权清理跨session/helper不变，不复制旧job授权或伪造PID、S07_PROC_TASK/deadline。
提交ID模糊或断线先查同一marker/job；排队60分钟未启动可核实后只取消自己的此job，不重提。依赖30—60秒查固定READY，90分钟上限，不占计算节点空等。

## 终态原始收集与接受边界

```bash
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_full_evidence.zip及bundle_receipt.json。全部rank正式报告/事件/ready/participants/store、隐藏atomic临时残件、栈/status/installed Python/proc/helper/父监督、调度/授权/退出/清理按实际bytes/SHA/远端mtime快照，读取变化另标；缺空损坏原样保留。收集日志不写入正在索引目录。
RANK_REPORT_INVENTORY单列正式JSON身份/最后已发布checkpoint/error是否存在、最后checkpoint_end和worker_error、父TERM/reap及原始临时残件；临时文件不作为正式报告。正式报告可能仅是最后提交的broadcast checkpoint，不能假称最终error报告已提交；mtime不能冒充精确commit时刻。
原run_checks决定四case，不从清理、正常单项或残件改判。事件/readiness/stack完整度独立；定时被合法取消或初始化未阻塞时忠实记录，不能补造非空栈。旧R6/2050433及0bytes原件不覆盖，不将正常小张量PASS称多域模型训练/性能接受。
